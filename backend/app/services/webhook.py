import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from app.core.config import settings
from app.schemas.deals import DealSchema

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Сервіс для відправки результатів парсингу у webhook
    
    Основні можливості:
    - POST запити до webhook API
    - Retry logic: 3 спроби з exponential backoff
    - Підтримка Bearer token автентифікації
    - Детальне логування успішних/неуспішних відправок
    - Batch відправка (кілька угод за раз)
    """
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        webhook_token: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        Ініціалізація WebhookService
        
        Args:
            webhook_url: URL webhook (якщо None - береться з settings)
            webhook_token: Bearer token (якщо None - береться з settings)
            max_retries: Максимальна кількість спроб
            timeout: Таймаут запиту в секундах
        """
        self.webhook_url = webhook_url or settings.WEBHOOK_URL
        self.webhook_token = webhook_token or settings.WEBHOOK_TOKEN
        self.max_retries = max_retries
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        
        # Лічильники для статистики
        self.stats = {
            "total_sent": 0,
            "successful": 0,
            "failed": 0
        }
        
        if not self.webhook_url:
            logger.warning("Webhook URL не налаштовано! Відправка буде пропущена.")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Отримати headers для запиту
        
        Returns:
            Dict з headers
        """
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'WebScraper-Gemini/1.0'
        }
        
        if self.webhook_token:
            headers['Authorization'] = f'Bearer {self.webhook_token}'
        
        return headers
    
    async def send_deal(
        self,
        deal: DealSchema,
        domain: str,
        session_id: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Відправити одну угоду в webhook
        
        Args:
            deal: DealSchema об'єкт з даними угоди
            domain: Домен з якого отримано угоду
            session_id: ID сесії парсингу (опціонально)
        
        Returns:
            Tuple[success, error_message]
        """
        if not self.webhook_url:
            logger.warning("Webhook URL не налаштовано, пропускаємо відправку")
            return False, "Webhook URL not configured"
        
        # Підготовка даних
        payload = deal.dict()
        payload['_metadata'] = {
            'source': 'web-scraper-gemini',
            'domain': domain,
            'session_id': session_id,
            'sent_at': datetime.utcnow().isoformat()
        }
        
        # Спроби відправки з retry logic
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Спроба {attempt}/{self.max_retries}: Відправка угоди в webhook "
                    f"(shop: {deal.shop}, code: {deal.code})"
                )
                
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(
                        self.webhook_url,
                        json=payload,
                        headers=self._get_headers()
                    ) as response:
                        
                        response_text = await response.text()
                        
                        if response.status in [200, 201, 202]:
                            logger.info(
                                f"✓ Угода успішно відправлена в webhook "
                                f"(status: {response.status}, shop: {deal.shop})"
                            )
                            self.stats['successful'] += 1
                            self.stats['total_sent'] += 1
                            return True, None
                        
                        else:
                            error_msg = (
                                f"Webhook відповів з статусом {response.status}: "
                                f"{response_text[:200]}"
                            )
                            logger.warning(f"✗ {error_msg}")
                            
                            # Якщо клієнтська помилка (4xx) - не повторюємо
                            if 400 <= response.status < 500:
                                self.stats['failed'] += 1
                                self.stats['total_sent'] += 1
                                return False, error_msg
                            
                            # Для серверних помилок (5xx) - повторюємо
                            if attempt < self.max_retries:
                                wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                                logger.info(f"Чекаємо {wait_time}с перед наступною спробою...")
                                await asyncio.sleep(wait_time)
            
            except asyncio.TimeoutError:
                error_msg = f"Timeout після {self.timeout.total} секунд"
                logger.warning(f"✗ {error_msg}")
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Чекаємо {wait_time}с перед наступною спробою...")
                    await asyncio.sleep(wait_time)
            
            except aiohttp.ClientError as e:
                error_msg = f"HTTP помилка: {str(e)}"
                logger.warning(f"✗ {error_msg}")
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Чекаємо {wait_time}с перед наступною спробою...")
                    await asyncio.sleep(wait_time)
            
            except Exception as e:
                error_msg = f"Неочікувана помилка: {str(e)}"
                logger.error(f"✗ {error_msg}", exc_info=True)
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
        
        # Якщо всі спроби не вдалися
        final_error = f"Не вдалося відправити після {self.max_retries} спроб"
        logger.error(f"✗ {final_error} (shop: {deal.shop})")
        self.stats['failed'] += 1
        self.stats['total_sent'] += 1
        return False, final_error
    
    async def send_deals_batch(
        self,
        deals: List[DealSchema],
        domain: str,
        session_id: Optional[int] = None
    ) -> Dict:
        """
        Відправити кілька угод пакетом
        
        Args:
            deals: Список DealSchema об'єктів
            domain: Домен з якого отримано угоди
            session_id: ID сесії парсингу
        
        Returns:
            Dict зі статистикою відправки
        """
        if not deals:
            logger.warning("Немає угод для відправки")
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "errors": []
            }
        
        logger.info(f"Початок відправки {len(deals)} угод для {domain}")
        
        result = {
            "total": len(deals),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        # Відправляємо кожну угоду окремо (можна змінити на пакетну відправку)
        for idx, deal in enumerate(deals, 1):
            logger.info(f"Відправка угоди {idx}/{len(deals)}...")
            
            success, error = await self.send_deal(deal, domain, session_id)
            
            if success:
                result['successful'] += 1
            else:
                result['failed'] += 1
                result['errors'].append({
                    "deal_index": idx,
                    "shop": deal.shop,
                    "code": deal.code,
                    "error": error
                })
            
            # Невелика затримка між відправками щоб не перевантажити webhook
            if idx < len(deals):
                await asyncio.sleep(0.5)
        
        logger.info(
            f"Завершено відправку для {domain}: "
            f"{result['successful']}/{result['total']} успішних"
        )
        
        return result
    
    async def send_deals_from_scraping_result(
        self,
        scraping_result: Dict,
        session_id: Optional[int] = None
    ) -> Dict:
        """
        Відправити угоди з результату парсингу
        
        Args:
            scraping_result: Результат від scrape_domain_task
            session_id: ID сесії
        
        Returns:
            Dict зі статистикою відправки
        """
        if not scraping_result.get('success'):
            logger.warning(
                f"Парсинг не був успішним для {scraping_result.get('domain')}, "
                "пропускаємо відправку"
            )
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "errors": ["Scraping was not successful"]
            }
        
        deals_data = scraping_result.get('deals', [])
        if not deals_data:
            logger.info(
                f"Немає угод для відправки з {scraping_result.get('domain')}"
            )
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "errors": []
            }
        
        # Конвертуємо dict у DealSchema
        deals = []
        for deal_dict in deals_data:
            try:
                deal = DealSchema(**deal_dict)
                deals.append(deal)
            except Exception as e:
                logger.error(f"Помилка конвертації угоди: {e}")
        
        # Відправляємо пакет
        return await self.send_deals_batch(
            deals,
            scraping_result.get('domain'),
            session_id
        )
    
    def get_stats(self) -> Dict:
        """
        Отримати статистику відправок
        
        Returns:
            Dict зі статистикою
        """
        return {
            **self.stats,
            "success_rate": (
                (self.stats['successful'] / self.stats['total_sent'] * 100)
                if self.stats['total_sent'] > 0
                else 0
            )
        }
    
    def reset_stats(self):
        """Скинути статистику"""
        self.stats = {
            "total_sent": 0,
            "successful": 0,
            "failed": 0
        }
    
    @classmethod
    def create_from_config(cls, config: Optional[Dict] = None) -> "WebhookService":
        """
        Створити WebhookService з конфігурації
        
        Args:
            config: Dict з webhook_url та webhook_token
        
        Returns:
            WebhookService instance
        """
        if not config:
            return cls()
        url = config.get('webhook_url') or config.get('url')
        token = config.get('webhook_token') or config.get('token')
        return cls(
            webhook_url=url,
            webhook_token=token,
            max_retries=config.get('max_retries', 3),
            timeout=config.get('timeout', 30)
        )
