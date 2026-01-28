import google.generativeai as genai
import json
import logging
import asyncio
from typing import List, Dict, Optional, Tuple
from app.schemas.deals import DealSchema
from app.core.config import settings
from app.prompts import EMAIL_DEALS_PROMPT
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Сервіс для інтеграції з Gemini AI
    
    Основні можливості:
    - Аналіз HTML контенту для пошуку промокодів та акцій
    - Витягування структурованих даних з банерів та акційних блоків
    - Валідація JSON відповіді
    - Retry logic з exponential backoff при помилках API
    """
    
    DEFAULT_PROMPT = """
Ти - експерт з аналізу вебсайтів та витягування інформації про промокоди та акції.

Проаналізуй наданий HTML контент сайту та знайди ВСІ промокоди, акції, знижки та спеціальні пропозиції.

ВАЖЛИВО:
- Шукай промокоди в банерах, popup вікнах, акційних блоках, футері, хедері
- Витягуй ТОЧНУ інформацію (не вигадуй!)
- Якщо щось не знайдено - використовуй "Не знайдено"
- Для дат використовуй формат: "YYYY-MM-DD HH:MM"
- Для offer_type: 1=промокод, 2=розпродаж, 3=безкоштовна доставка, 4=подарунок

СТРУКТУРА відповіді (ОБОВ'ЯЗКОВО JSON):
[
  {
    "shop": "Назва магазину з сайту",
    "domain": "{domain}",
    "description": "Короткий опис акції (макс 60 символів)",
    "full_description": "Детальний опис умов акції (макс 160 символів)",
    "code": "PROMOCODE або Не знайдено",
    "date_start": "2026-01-24 12:00 або null",
    "date_end": "2026-02-24 23:59 або null",
    "offer_type": 1,
    "target_url": "Пряме посилання на акцію або головна сторінка",
    "click_url": "Не знайдено",
    "discount": "20% або Не знайдено",
    "categories": ["3", "11"]
  }
]

HTML контент сайту {domain}:
{html_content}

Поверни ТІЛЬКИ валідний JSON масив з усіма знайденими акціями. Якщо акцій немає - поверни порожній масив [].
"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        prompt_template: Optional[str] = None,
        model_name: str = "gemini-1.5-flash"
    ):
        """
        Ініціалізація GeminiService
        
        Args:
            api_key: Gemini API ключ (якщо None - береться з settings)
            prompt_template: Кастомний промпт (якщо None - використовується DEFAULT_PROMPT)
            model_name: Назва моделі Gemini
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.prompt_template = prompt_template or self.DEFAULT_PROMPT
        self.model_name = model_name
        self.max_retries = 3
        
        # Конфігуруємо Gemini
        genai.configure(api_key=self.api_key)
        
        # Налаштування генерації
        self.generation_config = {
            "temperature": 0.3,  # Низька температура для точності
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
        
        # Налаштування безпеки (дозволяємо весь контент для парсингу)
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        # Ініціалізуємо модель
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
        
        logger.info(f"GeminiService ініціалізовано з моделлю {self.model_name}")
    
    def _prepare_prompt(self, html_content: str, domain: str) -> str:
        """
        Підготувати промпт з HTML контентом
        
        Args:
            html_content: Очищений HTML контент
            domain: Домен сайту
        
        Returns:
            Готовий промпт
        """
        max_len = getattr(settings, "GEMINI_MAX_CONTENT_LENGTH", 80000) or 0
        if max_len and len(html_content) > max_len:
            orig_len = len(html_content)
            html_content = html_content[:max_len] + "\n...(контент обрізано)"
            logger.warning(
                f"[Gemini] HTML обрізано для {domain!r}: orig={orig_len} max={max_len} (GEMINI_MAX_CONTENT_LENGTH)"
            )
        
        return self.prompt_template.format(
            domain=domain,
            html_content=html_content
        )

    def _prepare_email_prompt(self, email_body: str, domain: str) -> str:
        """
        Підготувати промпт для листа (email); placeholder [EMAIL], {domain}.
        Обрізає тіло листа до GEMINI_MAX_CONTENT_LENGTH при потребі.
        """
        max_len = getattr(settings, "GEMINI_MAX_CONTENT_LENGTH", 80000) or 0
        body = email_body
        if max_len and len(body) > max_len:
            orig_len = len(body)
            body = body[:max_len] + "\n...(контент обрізано)"
            logger.warning(
                f"[Gemini] Тіло листа обрізано для {domain!r}: orig={orig_len} max={max_len} (GEMINI_MAX_CONTENT_LENGTH)"
            )
        return EMAIL_DEALS_PROMPT.replace("[EMAIL]", body).replace("{domain}", domain)
    
    def _get_response_text(self, response) -> str:
        """Безпечно отримати текст з відповіді Gemini (SDK іноді кидає при .text)."""
        if response is None:
            return ""
        try:
            if hasattr(response, "text") and response.text is not None:
                return str(response.text).strip()
        except Exception as e:
            logger.debug(f"response.text виняток: {type(e).__name__}: {e}")
        try:
            if hasattr(response, "candidates") and response.candidates:
                c = response.candidates[0]
                if hasattr(c, "content") and c.content and hasattr(c.content, "parts") and c.content.parts:
                    parts = c.content.parts
                    texts = [getattr(p, "text", None) or getattr(p, "inline_data", str(p)) for p in parts]
                    return (" ".join(str(t) for t in texts if t)).strip()
        except Exception as e:
            logger.debug(f"candidates/parts виняток: {type(e).__name__}: {e}")
        return ""

    def _log_response_diagnostics(self, response, domain: str, response_text: str, context: str = "empty_or_blocked"):
        """Логувати діагностику відповіді Gemini без PII (при порожньому тексті / блоці)."""
        try:
            parts = []
            parts.append(f"[Gemini diag] domain={domain!r} context={context!r} text_len={len(response_text or '')}")
            if response is None:
                parts.append("response=None")
                logger.warning(" ".join(parts))
                return
            if hasattr(response, "prompt_feedback"):
                pf = response.prompt_feedback
                if pf is not None:
                    block = getattr(pf, "block_reason", None)
                    parts.append(f"prompt_feedback.block_reason={block}")
            if hasattr(response, "candidates") and response.candidates:
                for i, c in enumerate(response.candidates[:2]):
                    fr = getattr(c, "finish_reason", None)
                    parts.append(f"candidates[{i}].finish_reason={fr}")
                    if hasattr(c, "safety_ratings") and c.safety_ratings:
                        parts.append(f"candidates[{i}].safety_ratings={list(c.safety_ratings)[:4]!r}")
            raw_preview = (response_text or "")[:300].replace("\n", " ").strip()
            if not raw_preview:
                raw_preview = "[empty]"
            parts.append(f"raw_preview={raw_preview!r}")
            logger.warning(" ".join(parts))
        except Exception as e:
            logger.warning(f"[Gemini diag] domain={domain!r} diagnostic failed: {type(e).__name__}: {e}")
    
    def _parse_json_response(self, response_text: str) -> List[Dict]:
        """
        Розпарсити JSON відповідь від Gemini.
        Підтримує масив [...], об'єкт {"deals": [...]} / {"data": [...]}, markdown блоки.
        """
        import re
        if not response_text or not isinstance(response_text, str):
            return []
        raw = response_text.strip()
        # Прибираємо markdown
        for prefix in ("```json", "```"):
            if raw.startswith(prefix):
                raw = raw[len(prefix):].strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
        raw = raw.strip()
        if not raw:
            return []

        def as_list(obj) -> List[Dict]:
            if isinstance(obj, list):
                return [x for x in obj if isinstance(x, dict)]
            if isinstance(obj, dict):
                for key in ("deals", "data", "items", "results"):
                    if key in obj and isinstance(obj[key], list):
                        return [x for x in obj[key] if isinstance(x, dict)]
                return []
            return []

        # Спочатку шукаємо масив [...]
        m = re.search(r'\[[\s\S]*\]', raw)
        if m:
            try:
                data = json.loads(m.group(0))
                out = as_list(data)
                if out:
                    return out
            except json.JSONDecodeError:
                pass
        # Потім об'єкт {...}
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            try:
                data = json.loads(m.group(0))
                out = as_list(data)
                if out:
                    return out
            except json.JSONDecodeError:
                pass
        # Прямий парс
        try:
            data = json.loads(raw)
            return as_list(data)
        except json.JSONDecodeError:
            return []
    
    def _validate_deals(self, deals_data: List[Dict]) -> Tuple[List[DealSchema], List[Dict]]:
        """
        Валідувати дані через Pydantic схему.
        Ігнорує не-словники, ловить будь-які помилки валідації.
        """
        valid_deals = []
        invalid_deals = []
        for idx, deal_dict in enumerate(deals_data):
            if not isinstance(deal_dict, dict):
                invalid_deals.append({"data": deal_dict, "error": "не словник"})
                continue
            try:
                deal = DealSchema(**deal_dict)
                valid_deals.append(deal)
            except (ValidationError, TypeError, ValueError, KeyError) as e:
                logger.warning(f"Невалідна угода #{idx}: {e}")
                invalid_deals.append({"data": deal_dict, "error": str(e)})
            except Exception as e:
                logger.warning(f"Угода #{idx} — неочікувана помилка: {e}")
                invalid_deals.append({"data": deal_dict, "error": str(e)})
        return valid_deals, invalid_deals
    
    async def extract_deals(
        self,
        html_content: str,
        domain: str
    ) -> Tuple[List[DealSchema], Optional[str], Dict]:
        """
        Витягнути промокоди та акції з HTML контенту
        
        Args:
            html_content: Очищений HTML контент
            domain: Домен сайту
        
        Returns:
            Tuple[deals, error_message, metadata]:
            - deals: Список валідних DealSchema об'єктів
            - error_message: Повідомлення про помилку або None
            - metadata: Додаткова інформація (кількість спроб, raw response тощо)
        """
        metadata = {
            "attempts": 0,
            "raw_response": None,
            "invalid_deals_count": 0,
            "parse_error": None
        }
        _friendly_shop_msg = "Gemini: відповідь порожня або заблокована (немає тексту в parts)"

        try:
            prompt = self._prepare_prompt(html_content, domain)
        except Exception as e:
            if "shop" in str(e).lower() or '"shop"' in str(e):
                return [], _friendly_shop_msg, metadata
            raise
        return await self._extract_deals_core(prompt, domain)

    async def _extract_deals_core(
        self, prompt: str, domain: str
    ) -> Tuple[List[DealSchema], Optional[str], Dict]:
        """Спільна логіка: запит до Gemini, парсинг JSON, валідація угод (для HTML та email)."""
        metadata = {
            "attempts": 0,
            "raw_response": None,
            "invalid_deals_count": 0,
            "parse_error": None,
        }
        _friendly_shop_msg = "Gemini: відповідь порожня або заблокована (немає тексту в parts)"

        for attempt in range(1, self.max_retries + 1):
            metadata["attempts"] = attempt
            try:
                logger.info(f"Спроба {attempt}/{self.max_retries}: Відправка запиту до Gemini для {domain}")
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self.model.generate_content, prompt)
                response_text = self._get_response_text(response)
                metadata["raw_response"] = (response_text or "")[:2000]

                if not (response_text or "").strip():
                    self._log_response_diagnostics(response, domain, response_text or "", "empty_or_blocked")
                logger.info(f"✓ Отримано відповідь від Gemini ({len(response_text)} символів)")
                if response_text:
                    logger.debug(f"Перші 500 символів відповіді: {response_text[:500]}")

                deals_data = self._parse_json_response(response_text)
                if not deals_data:
                    logger.info(f"Gemini не знайшов жодної акції на {domain}")
                    return [], None, metadata
                valid_deals, invalid_deals = self._validate_deals(deals_data)
                metadata["invalid_deals_count"] = len(invalid_deals)
                if invalid_deals:
                    logger.warning(f"Відкинуто {len(invalid_deals)} невалідних угод")
                logger.info(f"✓ Успішно витягнуто {len(valid_deals)} валідних угод з {domain}")
                return valid_deals, None, metadata

            except (ValueError, KeyError, AttributeError) as e:
                err = str(e).strip()
                error_msg = _friendly_shop_msg if ('"shop"' in err or err in ('\n    "shop"', '"shop"', "'shop'")) else f"Gemini SDK: {type(e).__name__}: {err[:200]}"
                logger.error(error_msg)
                metadata["parse_error"] = error_msg
                if attempt >= self.max_retries:
                    return [], error_msg, metadata
                await asyncio.sleep(2 ** attempt)
                logger.info(f"Чекаємо {2 ** attempt}с перед повтором...")
            except json.JSONDecodeError as e:
                error_msg = f"Помилка парсингу JSON: {str(e)}"
                logger.error(error_msg)
                metadata["parse_error"] = error_msg
                if attempt >= self.max_retries:
                    return [], error_msg, metadata
                await asyncio.sleep(2 ** attempt)
                logger.info(f"Чекаємо {2 ** attempt}с перед наступною спробою...")
            except Exception as e:
                s = str(e).strip()
                error_msg = "Gemini: відповідь порожня або заблокована (немає тексту в parts)" if ('"shop"' in s or (s and "shop" in s and len(s) < 30)) else f"Gemini API: {type(e).__name__}: {s[:180]}"
                logger.error(error_msg, exc_info=True)
                metadata["parse_error"] = error_msg
                if attempt >= self.max_retries:
                    return [], error_msg, metadata
                await asyncio.sleep(2 ** attempt)
                logger.info(f"Чекаємо {2 ** attempt}с перед повтором...")

        return [], "Не вдалося витягнути дані після всіх спроб", metadata

    async def extract_deals_from_email(
        self, email_body: str, domain: str
    ) -> Tuple[List[DealSchema], Optional[str], Dict]:
        """
        Витягнути угоди з тіла листа (email) за промптом для coupon website (French).
        Використовує DEFAULT_EMAIL_PROMPT з плейсхолдерами [EMAIL] та {domain}.
        """
        prompt = self._prepare_email_prompt(email_body, domain)
        return await self._extract_deals_core(prompt, domain)
    
    async def extract_deals_from_scraped_data(
        self,
        scraped_data: Dict
    ) -> Tuple[List[DealSchema], Optional[str], Dict]:
        """
        Витягнути промокоди з даних, отриманих від WebScraper
        
        Args:
            scraped_data: Дані від WebScraper (результат scrape_domain)
        
        Returns:
            Tuple[deals, error_message, metadata]
        """
        if not scraped_data.get('success'):
            return [], scraped_data.get('error', "Scraping failed"), {}
        
        content = scraped_data.get('content', {})
        clean_html = content.get('clean_html', '')
        domain = scraped_data.get('domain', '')
        
        if not clean_html:
            return [], "Немає HTML контенту для аналізу", {}

        _friendly = "Gemini: відповідь порожня або заблокована (немає тексту в parts)"
        try:
            return await self.extract_deals(clean_html, domain)
        except Exception as e:
            s = str(e).strip()
            if '"shop"' in s or s in ('\n    "shop"', '"shop"', "'shop'") or ("shop" in s and len(s) < 50):
                return [], _friendly, {"parse_error": _friendly}
            raise
