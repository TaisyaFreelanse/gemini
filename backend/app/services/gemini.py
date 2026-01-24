import google.generativeai as genai
import json
import logging
import asyncio
from typing import List, Dict, Optional, Tuple
from app.schemas.deals import DealSchema
from app.core.config import settings
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
        # Обмежуємо розмір HTML (Gemini має ліміт токенів)
        max_html_length = 50000
        if len(html_content) > max_html_length:
            html_content = html_content[:max_html_length] + "\n...(контент обрізано)"
        
        return self.prompt_template.format(
            domain=domain,
            html_content=html_content
        )
    
    def _parse_json_response(self, response_text: str) -> List[Dict]:
        """
        Розпарсити JSON відповідь від Gemini
        
        Args:
            response_text: Текст відповіді від Gemini
        
        Returns:
            Список словників з даними про акції
        """
        # Видаляємо можливі markdown блоки
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        try:
            data = json.loads(response_text)
            
            # Перевіряємо що це список
            if not isinstance(data, list):
                logger.warning("Відповідь від Gemini не є масивом, загортаємо в масив")
                data = [data] if data else []
            
            return data
        
        except json.JSONDecodeError as e:
            logger.error(f"Помилка парсингу JSON: {e}")
            logger.debug(f"Сира відповідь: {response_text[:500]}...")
            return []
    
    def _validate_deals(self, deals_data: List[Dict]) -> Tuple[List[DealSchema], List[Dict]]:
        """
        Валідувати дані через Pydantic схему
        
        Args:
            deals_data: Список словників з даними
        
        Returns:
            Tuple[valid_deals, invalid_deals]
        """
        valid_deals = []
        invalid_deals = []
        
        for idx, deal_dict in enumerate(deals_data):
            try:
                deal = DealSchema(**deal_dict)
                valid_deals.append(deal)
            except ValidationError as e:
                logger.warning(f"Невалідна угода #{idx}: {e}")
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
        
        # Підготовка промпту
        prompt = self._prepare_prompt(html_content, domain)
        
        # Спроби з retry logic
        for attempt in range(1, self.max_retries + 1):
            metadata["attempts"] = attempt
            
            try:
                logger.info(f"Спроба {attempt}/{self.max_retries}: Відправка запиту до Gemini для {domain}")
                
                # Відправляємо запит до Gemini (синхронний API)
                # Використовуємо run_in_executor для асинхронності
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    self.model.generate_content,
                    prompt
                )
                
                # Отримуємо текст відповіді
                response_text = response.text
                metadata["raw_response"] = response_text[:1000]  # Зберігаємо перші 1000 символів
                
                logger.info(f"✓ Отримано відповідь від Gemini ({len(response_text)} символів)")
                
                # Парсимо JSON
                deals_data = self._parse_json_response(response_text)
                
                if not deals_data:
                    logger.info(f"Gemini не знайшов жодної акції на {domain}")
                    return [], None, metadata
                
                # Валідуємо дані
                valid_deals, invalid_deals = self._validate_deals(deals_data)
                metadata["invalid_deals_count"] = len(invalid_deals)
                
                if invalid_deals:
                    logger.warning(f"Відкинуто {len(invalid_deals)} невалідних угод")
                
                logger.info(f"✓ Успішно витягнуто {len(valid_deals)} валідних угод з {domain}")
                return valid_deals, None, metadata
            
            except json.JSONDecodeError as e:
                error_msg = f"Помилка парсингу JSON: {str(e)}"
                logger.error(error_msg)
                metadata["parse_error"] = error_msg
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                    logger.info(f"Чекаємо {wait_time}с перед наступною спробою...")
                    await asyncio.sleep(wait_time)
                else:
                    return [], error_msg, metadata
            
            except Exception as e:
                error_msg = f"Помилка Gemini API: {str(e)}"
                logger.error(error_msg, exc_info=True)
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Чекаємо {wait_time}с перед наступною спробою...")
                    await asyncio.sleep(wait_time)
                else:
                    return [], error_msg, metadata
        
        return [], "Не вдалося витягнути дані після всіх спроб", metadata
    
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
        
        return await self.extract_deals(clean_html, domain)
