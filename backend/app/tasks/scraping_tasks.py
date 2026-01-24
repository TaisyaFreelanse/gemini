import asyncio
import logging
from typing import Dict, List, Optional
from celery import Task
from app.tasks.celery_app import celery_app
from app.services.scraper import WebScraper
from app.services.gemini import GeminiService
from app.services.proxy import ProxyRotator
import redis
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Redis клієнт для збереження прогресу
from app.core.config import settings
redis_client = redis.from_url(settings.REDIS_URL)


class CallbackTask(Task):
    """Базовий клас для задач з callback"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Викликається при помилці задачі"""
        logger.error(f"Задача {task_id} не виконана: {exc}")
        # Тут можна додати логіку відправки в webhook про помилку


@celery_app.task(bind=True, base=CallbackTask, name='scrape_domain_task')
def scrape_domain_task(self, domain: str, session_id: int, config: Optional[Dict] = None) -> Dict:
    """
    Celery задача для парсингу одного домену
    
    Args:
        domain: Домен для парсингу
        session_id: ID сесії парсингу
        config: Додаткова конфігурація (proxy, gemini key тощо)
    
    Returns:
        Dict з результатами парсингу
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Початок парсингу домену: {domain}")
    
    # Оновлюємо статус в Redis
    _update_task_status(task_id, domain, "running", session_id)
    
    try:
        # Запускаємо асинхронну обробку
        result = asyncio.run(_scrape_domain_async(domain, session_id, config or {}))
        
        # Оновлюємо статус
        _update_task_status(task_id, domain, "completed", session_id, result)
        
        logger.info(f"[Task {task_id}] ✓ Завершено парсинг {domain}: {result.get('deals_count', 0)} угод")
        return result
    
    except Exception as e:
        logger.error(f"[Task {task_id}] ✗ Помилка парсингу {domain}: {str(e)}", exc_info=True)
        
        error_result = {
            "success": False,
            "domain": domain,
            "error": str(e),
            "deals_count": 0
        }
        
        _update_task_status(task_id, domain, "failed", session_id, error_result)
        return error_result


async def _scrape_domain_async(domain: str, session_id: int, config: Dict) -> Dict:
    """
    Асинхронна функція для парсингу домену
    
    Повний цикл: WebScraper → GeminiService → збереження результату
    """
    result = {
        "success": False,
        "domain": domain,
        "session_id": session_id,
        "deals_count": 0,
        "deals": [],
        "error": None,
        "scraped_at": datetime.utcnow().isoformat(),
        "metadata": {}
    }
    
    # Крок 1: Завантажуємо HTML через WebScraper
    try:
        # Створюємо scraper з проксі якщо є конфігурація
        proxy_config = config.get('proxy')
        scraper = WebScraper.create_with_config(proxy_config) if proxy_config else WebScraper()
        
        logger.info(f"Завантаження HTML для {domain}...")
        scraped_data = await scraper.scrape_domain(domain, use_proxy=bool(proxy_config))
        
        if not scraped_data['success']:
            result['error'] = scraped_data.get('error', 'Scraping failed')
            return result
        
        result['metadata']['html_length'] = len(scraped_data.get('html_raw', ''))
        
    except Exception as e:
        logger.error(f"Помилка WebScraper для {domain}: {e}")
        result['error'] = f"WebScraper error: {str(e)}"
        return result
    
    # Крок 2: Аналізуємо через Gemini AI
    try:
        gemini_key = config.get('gemini_key')
        gemini = GeminiService(api_key=gemini_key) if gemini_key else GeminiService()
        
        logger.info(f"Аналіз через Gemini AI для {domain}...")
        deals, error, metadata = await gemini.extract_deals_from_scraped_data(scraped_data)
        
        if error:
            result['error'] = error
            result['metadata']['gemini'] = metadata
            return result
        
        result['success'] = True
        result['deals_count'] = len(deals)
        result['deals'] = [deal.dict() for deal in deals]
        result['metadata']['gemini'] = metadata
        
        logger.info(f"✓ Знайдено {len(deals)} угод для {domain}")
        
    except Exception as e:
        logger.error(f"Помилка Gemini для {domain}: {e}")
        result['error'] = f"Gemini error: {str(e)}"
        return result
    
    # Крок 3: Зберігаємо результат в Redis (тимчасово, поки немає БД)
    try:
        _save_scraping_result(session_id, domain, result)
    except Exception as e:
        logger.warning(f"Не вдалося зберегти результат в Redis: {e}")
    
    # Крок 4: Відправляємо результати в webhook
    if result['success'] and result['deals_count'] > 0:
        try:
            from app.services.webhook import WebhookService
            
            webhook_config = config.get('webhook', {})
            webhook = WebhookService.create_from_config(webhook_config)
            
            logger.info(f"Відправка {result['deals_count']} угод в webhook...")
            webhook_result = await webhook.send_deals_from_scraping_result(result, session_id)
            
            result['webhook_sent'] = webhook_result['successful'] > 0
            result['webhook_stats'] = webhook_result
            
            logger.info(
                f"Webhook: {webhook_result['successful']}/{webhook_result['total']} успішних"
            )
        except Exception as e:
            logger.error(f"Помилка відправки в webhook: {e}")
            result['webhook_sent'] = False
            result['webhook_error'] = str(e)
    
    return result


def _update_task_status(task_id: str, domain: str, status: str, session_id: int, result: Optional[Dict] = None):
    """Оновити статус задачі в Redis"""
    try:
        key = f"task:{task_id}"
        data = {
            "task_id": task_id,
            "domain": domain,
            "status": status,
            "session_id": session_id,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if result:
            data['result'] = result
        
        redis_client.setex(key, 3600, json.dumps(data))  # TTL 1 година
        
        # Також оновлюємо загальний прогрес сесії
        _update_session_progress(session_id, status, domain)
        
    except Exception as e:
        logger.error(f"Помилка оновлення статусу задачі: {e}")


def _update_session_progress(session_id: int, status: str, domain: str):
    """Оновити прогрес сесії парсингу"""
    try:
        key = f"session:{session_id}:progress"
        
        # Отримуємо поточний прогрес
        progress_data = redis_client.get(key)
        if progress_data:
            progress = json.loads(progress_data)
        else:
            progress = {
                "session_id": session_id,
                "total": 0,
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "running": 0,
                "domains": {}
            }
        
        # Оновлюємо статус домену
        old_status = progress['domains'].get(domain)
        progress['domains'][domain] = status
        
        # Оновлюємо лічильники
        if old_status:
            if old_status == "running":
                progress['running'] -= 1
        
        if status == "running":
            progress['running'] += 1
        elif status == "completed":
            progress['processed'] += 1
            progress['successful'] += 1
        elif status == "failed":
            progress['processed'] += 1
            progress['failed'] += 1
        
        progress['updated_at'] = datetime.utcnow().isoformat()
        
        # Зберігаємо назад
        redis_client.setex(key, 7200, json.dumps(progress))  # TTL 2 години
        
    except Exception as e:
        logger.error(f"Помилка оновлення прогресу сесії: {e}")


def _save_scraping_result(session_id: int, domain: str, result: Dict):
    """Зберегти результат парсингу в Redis"""
    try:
        key = f"session:{session_id}:results:{domain}"
        redis_client.setex(key, 7200, json.dumps(result))  # TTL 2 години
        
        # Додаємо домен до списку результатів сесії
        list_key = f"session:{session_id}:domains"
        redis_client.sadd(list_key, domain)
        redis_client.expire(list_key, 7200)
        
    except Exception as e:
        logger.error(f"Помилка збереження результату: {e}")


@celery_app.task(name='start_batch_scraping')
def start_batch_scraping(domains: List[str], session_id: int, config: Optional[Dict] = None) -> Dict:
    """
    Запустити пакетний парсинг доменів
    
    Args:
        domains: Список доменів для парсингу
        session_id: ID сесії парсингу
        config: Конфігурація для всіх задач
    
    Returns:
        Dict з інформацією про запущені задачі
    """
    logger.info(f"Запуск пакетного парсингу: {len(domains)} доменів, сесія {session_id}")
    
    # Ініціалізуємо прогрес сесії
    _init_session_progress(session_id, domains)
    
    # Запускаємо задачі для кожного домену
    task_ids = []
    for domain in domains:
        task = scrape_domain_task.delay(domain, session_id, config)
        task_ids.append({
            "task_id": task.id,
            "domain": domain
        })
    
    logger.info(f"Запущено {len(task_ids)} задач для сесії {session_id}")
    
    return {
        "session_id": session_id,
        "total_domains": len(domains),
        "task_ids": task_ids,
        "started_at": datetime.utcnow().isoformat()
    }


def _init_session_progress(session_id: int, domains: List[str]):
    """Ініціалізувати прогрес сесії"""
    try:
        key = f"session:{session_id}:progress"
        progress = {
            "session_id": session_id,
            "total": len(domains),
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "running": 0,
            "domains": {domain: "pending" for domain in domains},
            "started_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        redis_client.setex(key, 7200, json.dumps(progress))
        
        # Зберігаємо статус сесії
        redis_client.set(f"scraping:status", "running")
        redis_client.set(f"scraping:session_id", session_id)
        
    except Exception as e:
        logger.error(f"Помилка ініціалізації прогресу: {e}")


@celery_app.task(name='get_session_progress')
def get_session_progress(session_id: int) -> Optional[Dict]:
    """
    Отримати прогрес сесії парсингу
    
    Args:
        session_id: ID сесії
    
    Returns:
        Dict з прогресом або None
    """
    try:
        key = f"session:{session_id}:progress"
        data = redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.error(f"Помилка отримання прогресу: {e}")
        return None


@celery_app.task(name='cleanup_old_sessions')
def cleanup_old_sessions():
    """
    Очистити старі дані сесій з Redis
    
    Періодична задача для Celery Beat
    """
    logger.info("Очищення старих сесій...")
    # TODO: Реалізувати логіку очищення
    pass
