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


def _is_stop_requested() -> bool:
    """Перевірити чи була запрошена зупинка"""
    try:
        stop_flag = redis_client.get("scraping:stop_requested")
        return stop_flag and stop_flag.decode() == "1"
    except Exception:
        return False


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
    
    # Перевіряємо чи не було запрошено зупинку
    if _is_stop_requested():
        logger.info(f"[Task {task_id}] ⏹ Пропускаємо {domain} - зупинка запрошена")
        
        # Update task status with "skipped" terminal state so counters remain consistent
        skipped_result = {
            "success": False,
            "domain": domain,
            "session_id": session_id,
            "deals_count": 0,
            "deals": [],
            "error": "Зупинка запрошена",
            "skipped": True
        }
        _update_task_status(task_id, domain, "skipped", session_id, skipped_result)
        
        # Also update database session counters to keep DB in sync with Redis
        # Without this, processed_domains in DB would be lower than Redis counter
        _update_session_in_db(session_id, skipped_result)
        
        return skipped_result
    
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
    scraper = None
    scraped_data = None
    try:
        # Створюємо scraper з проксі якщо є конфігурація
        proxy_config = config.get('proxy')
        scraper = WebScraper.create_with_config(proxy_config) if proxy_config else WebScraper()
        
        logger.info(f"Завантаження HTML для {domain}...")
        _add_ui_log("DEBUG", f"Завантаження HTML для {domain}...", domain)
        
        # use_cache=False — async Redis кеш дає "Event loop is closed" у Celery
        scraped_data = await scraper.scrape_domain(domain, use_proxy=bool(proxy_config), use_cache=False)
        
    except Exception as e:
        logger.error(f"Помилка WebScraper для {domain}: {e}")
        _add_ui_log("ERROR", f"WebScraper помилка для {domain}: {str(e)[:100]}", domain)
        result['error'] = f"WebScraper error: {str(e)}"
    finally:
        # Закриваємо HTTP сесію
        if scraper:
            try:
                await scraper.close()
            except Exception:
                pass
    
    # Перевіряємо результат scraping
    if scraped_data is None:
        return result
    
    if not scraped_data['success']:
        error_msg = scraped_data.get('error', 'Scraping failed')
        result['error'] = error_msg
        _add_ui_log("ERROR", f"Помилка завантаження {domain}: {error_msg[:100]}", domain)
        return result
    
    html_len = len(scraped_data.get('html_raw', ''))
    result['metadata']['html_length'] = html_len
    _add_ui_log("INFO", f"✓ Завантажено HTML для {domain} ({html_len} байт)", domain, {"html_length": html_len})
    
    # Перевірка зупинки перед Gemini
    if _is_stop_requested():
        result['error'] = "Зупинка запрошена"
        result['skipped'] = True
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
    """
    Оновити прогрес сесії парсингу (атомні операції через Redis Lua script)
    
    Uses a Lua script for atomic get-and-set to prevent race conditions.
    Also handles "skipped" status as a terminal state (counts as processed).
    """
    try:
        counters_key = f"session:{session_id}:counters"
        domains_key = f"session:{session_id}:domain_status"
        
        # Lua script for atomic status update and counter adjustment
        # This prevents TOCTOU race conditions between hget and hset
        lua_script = """
        local domains_key = KEYS[1]
        local counters_key = KEYS[2]
        local domain = ARGV[1]
        local new_status = ARGV[2]
        local updated_at = ARGV[3]
        
        -- Atomically get old status and set new status
        local old_status = redis.call('HGET', domains_key, domain)
        redis.call('HSET', domains_key, domain, new_status)
        redis.call('EXPIRE', domains_key, 7200)
        
        -- Adjust running counter if old status was "running"
        if old_status == "running" then
            redis.call('HINCRBY', counters_key, 'running', -1)
        end
        
        -- Adjust counters based on new status
        if new_status == "running" then
            redis.call('HINCRBY', counters_key, 'running', 1)
        elseif new_status == "completed" then
            redis.call('HINCRBY', counters_key, 'processed', 1)
            redis.call('HINCRBY', counters_key, 'successful', 1)
        elseif new_status == "failed" then
            redis.call('HINCRBY', counters_key, 'processed', 1)
            redis.call('HINCRBY', counters_key, 'failed', 1)
        elseif new_status == "skipped" then
            -- Skipped tasks are terminal states and count as processed
            redis.call('HINCRBY', counters_key, 'processed', 1)
            redis.call('HINCRBY', counters_key, 'skipped', 1)
        end
        
        -- Update timestamp
        redis.call('HSET', counters_key, 'updated_at', updated_at)
        redis.call('EXPIRE', counters_key, 7200)
        
        return old_status
        """
        
        # Execute the Lua script atomically
        redis_client.eval(
            lua_script,
            2,  # Number of keys
            domains_key,
            counters_key,
            domain,
            status,
            datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.warning(f"Помилка оновлення прогресу сесії: {e}")


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
    """
    Оновити сесію парсингу в БД (атомні операції через SQL UPDATE)
    """
    try:
        from app.db.session import SessionLocal
        from app.db import crud
        
        db = SessionLocal()
        try:
            # Використовуємо атомне оновлення лічильників
            session = crud.atomic_increment_session_counters(
                db=db,
                session_id=session_id,
                success=result.get('success', False)
            )
            
            if session:
                # Оновлюємо статус в Redis
                if session.status == "completed":
                    redis_client.set("scraping:status", "completed")
                    # Очищаємо active_session щоб дозволити наступний запуск
                    redis_client.delete("parsing:active_session")
                    logger.info(f"✓ Сесія {session_id} завершена, active_session очищено")
                elif session.status == "failed":
                    redis_client.set("scraping:status", "failed")
                    # Також очищаємо при помилці
                    redis_client.delete("parsing:active_session")
                
                logger.debug(
                    f"Оновлено сесію {session_id}: "
                    f"processed={session.processed_domains}, "
                    f"successful={session.successful_domains}, "
                    f"failed={session.failed_domains}"
                )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Помилка оновлення сесії в БД: {e}")


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
    
    # Очищаємо флаг зупинки від попередніх сесій
    redis_client.delete("scraping:stop_requested")
    
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
    task_id_list = []  # Для збереження в Redis
    for domain in domains:
        task = scrape_domain_task.delay(domain, session_id, config)
        task_ids.append({
            "task_id": task.id,
            "domain": domain
        })
        task_id_list.append(task.id)
    
    # Зберігаємо task_ids в Redis для можливості скасування
    redis_client.set("scraping:task_ids", json.dumps(task_id_list))
    
    logger.info(f"Запущено {len(task_ids)} задач для сесії {session_id}")
    _add_ui_log("INFO", f"📋 Запущено {len(task_ids)} задач для обробки", extra={"task_count": len(task_ids)})
    
    return {
        "session_id": session_id,
        "total_domains": len(domains),
        "task_ids": task_ids,
        "started_at": datetime.utcnow().isoformat()
    }


def _init_session_progress(session_id: int, domains: List[str]):
    """
    Ініціалізувати прогрес сесії (використовує Redis hashes для атомних операцій)
    """
    try:
        counters_key = f"session:{session_id}:counters"
        domains_key = f"session:{session_id}:domain_status"
        
        # Ініціалізуємо лічильники (including skipped)
        counters = {
            "total": len(domains),
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "running": 0,
            "started_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        redis_client.hset(counters_key, mapping=counters)
        redis_client.expire(counters_key, 7200)
        
        # Ініціалізуємо статуси доменів (батчами для великих списків)
        if domains:
            domain_statuses = {domain: "pending" for domain in domains}
            redis_client.hset(domains_key, mapping=domain_statuses)
            redis_client.expire(domains_key, 7200)
        
        # Зберігаємо статус сесії
        redis_client.set("scraping:status", "running")
        redis_client.set("scraping:session_id", session_id)
        
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
        counters_key = f"session:{session_id}:counters"
        domains_key = f"session:{session_id}:domain_status"
        
        # Отримуємо лічильники
        counters = redis_client.hgetall(counters_key)
        if not counters:
            return None
        
        # Декодуємо bytes -> str
        def decode_val(v):
            return v.decode('utf-8') if isinstance(v, bytes) else v
        
        counters = {decode_val(k): decode_val(v) for k, v in counters.items()}
        
        # Отримуємо статуси доменів
        domains = redis_client.hgetall(domains_key)
        domains = {decode_val(k): decode_val(v) for k, v in domains.items()}
        
        return {
            "session_id": session_id,
            "total": int(counters.get("total", 0)),
            "processed": int(counters.get("processed", 0)),
            "successful": int(counters.get("successful", 0)),
            "failed": int(counters.get("failed", 0)),
            "skipped": int(counters.get("skipped", 0)),  # Include skipped counter
            "running": int(counters.get("running", 0)),
            "updated_at": counters.get("updated_at"),
            "domains": domains
        }
    except Exception as e:
        logger.warning(f"Помилка отримання прогресу: {e}")
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
