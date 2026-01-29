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


def _add_ui_log(level: str, message: str, domain: str = None, extra: dict = None):
    """Додати лог для UI (в Redis)"""
    try:
        from app.api.endpoints.logs import add_log
        add_log(level, message, domain, extra)
    except Exception:
        pass  # Не блокувати основний процес


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
    _add_ui_log("INFO", f"Початок парсингу домену: {domain}", domain)
    
    # Оновлюємо статус в Redis
    _update_task_status(task_id, domain, "running", session_id)
    
    try:
        # Запускаємо асинхронну обробку
        result = asyncio.run(_scrape_domain_async(domain, session_id, config or {}))
        
        # Оновлюємо статус
        _update_task_status(task_id, domain, "completed", session_id, result)
        
        # Оновлюємо сесію в БД
        _update_session_in_db(session_id, result)
        
        deals_count = result.get('deals_count', 0)
        if result.get('success'):
            logger.info(f"[Task {task_id}] ✓ Завершено парсинг {domain}: {deals_count} угод")
            _add_ui_log("INFO", f"✓ Завершено парсинг {domain}: {deals_count} угод", domain, {"deals_count": deals_count})
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.warning(f"[Task {task_id}] ⚠ Парсинг {domain} завершено з помилкою: {error_msg}")
            _add_ui_log("WARNING", f"⚠ Парсинг {domain}: {error_msg[:100]}", domain)
        
        return result
    
    except Exception as e:
        logger.error(f"[Task {task_id}] ✗ Помилка парсингу {domain}: {str(e)}", exc_info=True)
        _add_ui_log("ERROR", f"✗ Критична помилка парсингу {domain}: {str(e)[:100]}", domain)
        
        error_result = {
            "success": False,
            "domain": domain,
            "error": str(e),
            "deals_count": 0
        }
        
        _update_task_status(task_id, domain, "failed", session_id, error_result)
        
        # Оновлюємо сесію в БД
        _update_session_in_db(session_id, error_result)
        
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
        _add_ui_log("DEBUG", f"Завантаження HTML для {domain}...", domain)
        
        # use_cache=False — async Redis кеш дає "Event loop is closed" у Celery
        scraped_data = await scraper.scrape_domain(domain, use_proxy=bool(proxy_config), use_cache=False)
        
        if not scraped_data['success']:
            error_msg = scraped_data.get('error', 'Scraping failed')
            result['error'] = error_msg
            _add_ui_log("ERROR", f"Помилка завантаження {domain}: {error_msg[:100]}", domain)
            return result
        
        html_len = len(scraped_data.get('html_raw', ''))
        result['metadata']['html_length'] = html_len
        _add_ui_log("INFO", f"✓ Завантажено HTML для {domain} ({html_len} байт)", domain, {"html_length": html_len})
        
    except Exception as e:
        logger.error(f"Помилка WebScraper для {domain}: {e}")
        _add_ui_log("ERROR", f"WebScraper помилка для {domain}: {str(e)[:100]}", domain)
        result['error'] = f"WebScraper error: {str(e)}"
        return result
    
    # Крок 2: Аналізуємо через Gemini AI
    try:
        gemini_key = config.get('gemini_key')
        prompt_template = config.get('prompt')
        gemini = GeminiService(
            api_key=gemini_key or None,
            prompt_template=prompt_template
        )
        
        logger.info(f"Аналіз через Gemini AI для {domain}...")
        _add_ui_log("DEBUG", f"Аналіз через Gemini AI для {domain}...", domain)
        
        deals, error, metadata = await gemini.extract_deals_from_scraped_data(scraped_data)
        
        if error:
            result['error'] = error
            result['metadata']['gemini'] = metadata
            _add_ui_log("WARNING", f"Gemini помилка для {domain}: {error[:100]}", domain)
            return result
        
        result['success'] = True
        result['deals_count'] = len(deals)
        result['deals'] = [deal.dict() for deal in deals]
        result['metadata']['gemini'] = metadata
        
        logger.info(f"✓ Знайдено {len(deals)} угод для {domain}")
        _add_ui_log("INFO", f"✓ Gemini знайшов {len(deals)} угод для {domain}", domain, {"deals_count": len(deals)})
        
    except Exception as e:
        err_s = str(e).strip()
        if '"shop"' in err_s or err_s in ('\n    "shop"', '"shop"', "'shop'"):
            msg = "Gemini: відповідь порожня або заблокована (немає тексту в parts)"
        else:
            msg = f"Gemini error: {err_s[:200]}"
        logger.error(f"Помилка Gemini для {domain}: {msg}")
        _add_ui_log("ERROR", f"Gemini помилка для {domain}: {msg[:100]}", domain)
        result['error'] = msg
        return result
    
    # Крок 3: Зберігаємо результат в БД та Redis
    try:
        # Зберігаємо в Redis для швидкого доступу
        _save_scraping_result(session_id, domain, result)
        
        # Зберігаємо в БД для постійного зберігання
        if result['success'] and result['deals_count'] > 0:
            from app.db.session import SessionLocal
            from app.db import crud
            
            db = SessionLocal()
            try:
                # Зберігаємо кожну угоду в БД
                for deal_data in result['deals']:
                    crud.create_scraped_deal(
                        db=db,
                        session_id=session_id,
                        domain=domain,
                        deal_data=deal_data
                    )
                logger.info(f"✓ Збережено {result['deals_count']} угод в БД для {domain}")
            except Exception as db_error:
                logger.error(f"Помилка збереження в БД: {db_error}")
            finally:
                db.close()
    except Exception as e:
        logger.warning(f"Не вдалося зберегти результат: {e}")
    
    # Крок 4: Відправляємо результати в webhook
    if result['success'] and result['deals_count'] > 0:
        try:
            from app.services.webhook import WebhookService
            
            webhook_config = config.get('webhook', {})
            webhook = WebhookService.create_from_config(webhook_config)
            
            logger.info(f"Відправка {result['deals_count']} угод в webhook...")
            _add_ui_log("DEBUG", f"Відправка {result['deals_count']} угод в webhook для {domain}...", domain)
            
            webhook_result = await webhook.send_deals_from_scraping_result(result, session_id)
            
            result['webhook_sent'] = webhook_result['successful'] > 0
            result['webhook_stats'] = webhook_result
            
            successful = webhook_result['successful']
            total = webhook_result['total']
            logger.info(f"Webhook: {successful}/{total} успішних")
            
            if successful > 0:
                _add_ui_log("INFO", f"✓ Webhook: відправлено {successful}/{total} угод для {domain}", domain, {"successful": successful, "total": total})
            else:
                _add_ui_log("WARNING", f"⚠ Webhook: 0/{total} угод для {domain}", domain)
                
        except Exception as e:
            logger.error(f"Помилка відправки в webhook: {e}")
            _add_ui_log("ERROR", f"Webhook помилка для {domain}: {str(e)[:100]}", domain)
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


def _update_session_in_db(session_id: int, result: Dict):
    """Оновити сесію парсингу в БД"""
    try:
        from app.db.session import SessionLocal
        from app.db import crud
        
        db = SessionLocal()
        try:
            session = crud.get_scraping_session(db, session_id)
            if session:
                # Отримуємо поточні значення
                processed = session.processed_domains or 0
                successful = session.successful_domains or 0
                failed = session.failed_domains or 0
                
                # Оновлюємо лічильники
                processed += 1
                if result.get('success'):
                    successful += 1
                else:
                    failed += 1
                
                # Перевіряємо чи всі домени оброблені
                status = session.status
                if processed >= session.total_domains:
                    status = "completed"
                
                # Оновлюємо сесію
                crud.update_scraping_session(
                    db=db,
                    session_id=session_id,
                    processed=processed,
                    successful=successful,
                    failed=failed,
                    status=status
                )
                
                # Оновлюємо статус в Redis
                if status == "completed":
                    redis_client.set("scraping:status", "completed")
                elif status == "failed":
                    redis_client.set("scraping:status", "failed")
                
                logger.debug(f"Оновлено сесію {session_id}: processed={processed}, successful={successful}, failed={failed}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Помилка оновлення сесії в БД: {e}")


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
    
    # Логуємо конфігурацію (без паролів)
    proxy_info = "Без проксі"
    if config and config.get('proxy') and config['proxy'].get('host'):
        proxy_info = f"Проксі: {config['proxy']['host']}:{config['proxy'].get('http_port', 59100)}"
    
    _add_ui_log("INFO", f"🚀 Старт парсингу: {len(domains)} доменів, сесія #{session_id}", extra={
        "session_id": session_id,
        "total_domains": len(domains),
        "proxy": proxy_info
    })
    
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
    _add_ui_log("INFO", f"📋 Запущено {len(task_ids)} задач для обробки", extra={"task_count": len(task_ids)})
    
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
