from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_db
from app.schemas.parsing import (
    ParsingStartRequest,
    ParsingStartResponse,
    ParsingStatusResponse,
    ParsingHistoryResponse,
    ParsingHistoryItem,
    ScrapingStatus
)
import redis
from app.core.config import settings

router = APIRouter()

# Redis клієнт для отримання статусу
redis_client = redis.from_url(settings.REDIS_URL)


@router.post("/start", response_model=ParsingStartResponse, status_code=status.HTTP_201_CREATED)
async def start_parsing(
    request: ParsingStartRequest,
    db: Session = Depends(get_db)
):
    """
    Запустити парсинг доменів
    
    - **batch_size**: Кількість доменів для обробки (None = всі)
    - **force_refresh**: Примусово оновити всі домени навіть якщо вони вже оброблені
    """
    from app.db import crud
    from app.tasks.scraping_tasks import start_batch_scraping
    import httpx
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Перевірити чи не запущено вже парсинг
    current_status = redis_client.get("scraping:status")
    if current_status and current_status.decode() == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Парсинг вже запущено. Зупиніть поточний процес перед запуском нового."
        )
    
    # Отримати список доменів
    domains = []
    domain_names = {}  # Маппінг domain → shop name з API
    try:
        import json as json_module
        
        def _extract_domain_and_name(item):
            """Витягнути домен та назву магазину з елемента API."""
            domain = None
            name = None
            if isinstance(item, str):
                domain = item.strip().lower()
                if domain.startswith("https://"):
                    domain = domain[8:]
                elif domain.startswith("http://"):
                    domain = domain[7:]
                domain = domain.rstrip("/")
            elif isinstance(item, dict):
                url = (item.get('url', '') or item.get('domain', '') or '').strip()
                name = item.get('name', '') or None
                if url:
                    if '://' in url:
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        domain = (parsed.netloc or parsed.path).strip().lower().rstrip("/")
                    else:
                        domain = url.lower().rstrip("/")
            return domain, (name.strip() if name else None)
        
        # 1. Спочатку перевіряємо завантажені домени з Redis (через Configuration)
        uploaded_domains_raw = redis_client.get("config:domains")
        if uploaded_domains_raw:
            try:
                uploaded_domains = json_module.loads(uploaded_domains_raw.decode())
                if uploaded_domains and isinstance(uploaded_domains, list):
                    domains = uploaded_domains
                    logger.info(f"Використовуємо {len(domains)} завантажених доменів з конфігурації")
            except Exception as e:
                logger.warning(f"Помилка читання завантажених доменів: {e}")
        
        # Завантажуємо збережений маппінг domain → name з Redis
        domain_names_raw = redis_client.get("config:domain_names")
        if domain_names_raw:
            try:
                domain_names = json_module.loads(domain_names_raw.decode())
                logger.info(f"Завантажено {len(domain_names)} назв магазинів з Redis")
            except Exception as e:
                logger.warning(f"Помилка читання domain_names: {e}")
        
        # 2. Якщо немає завантажених доменів, пробуємо API або файл
        if not domains:
            # Отримуємо URL API з конфігурації
            api_url_redis = redis_client.get("config:api_url")
            if api_url_redis:
                api_url = api_url_redis.decode()
            else:
                from app.core.config import settings
                api_url = settings.DOMAINS_API_URL or "http://localhost:8000/api/v1/mock-domains"
            
            # Якщо це mock-domains, читаємо файл напряму (швидше і надійніше)
            if "mock-domains" in api_url or api_url.endswith("/mock-domains"):
                from pathlib import Path
                import json
                api_json_path = Path("/app/api.json")
                if api_json_path.exists():
                    logger.info(f"Читаємо домени з файлу: {api_json_path}")
                    with open(api_json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if isinstance(data, dict) and 'data' in data:
                        raw_domains = data['data']
                    elif isinstance(data, list):
                        raw_domains = data
                    else:
                        raw_domains = []
                    
                    # Обробляємо домени та витягуємо назви
                    for item in raw_domains:
                        domain, name = _extract_domain_and_name(item)
                        if domain:
                            domains.append(domain)
                            if name:
                                domain_names[domain] = name
                else:
                    logger.warning(f"Файл api.json не знайдено: {api_json_path}")
            else:
                # Завантажуємо домени через HTTP
                try:
                    with httpx.Client(timeout=10.0) as client:
                        response = client.get(api_url)
                        if response.status_code == 200:
                            data = response.json()
                            if isinstance(data, dict) and 'data' in data:
                                raw_domains = data['data']
                            elif isinstance(data, list):
                                raw_domains = data
                            else:
                                raw_domains = []
                            
                            # Обробляємо домени та витягуємо назви
                            for item in raw_domains:
                                domain, name = _extract_domain_and_name(item)
                                if domain:
                                    domains.append(domain)
                                    if name:
                                        domain_names[domain] = name
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"API повернув статус {response.status_code}"
                            )
                except httpx.HTTPError as e:
                    logger.error(f"Помилка HTTP при отриманні доменів: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Не вдалося отримати список доменів: {str(e)}"
                )
        
        # Обмежуємо кількість якщо вказано batch_size
        if request.batch_size:
            domains = domains[:request.batch_size]
    except Exception as e:
        logger.error(f"Помилка отримання доменів: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не вдалося отримати список доменів: {str(e)}"
        )
    
    if not domains:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не вдалося отримати домени для парсингу"
        )
    
    # Створити scraping session в БД
    session = crud.create_scraping_session(db, total_domains=len(domains))
    
    # Запустити Celery задачі
    try:
        from app.core.config import settings
        # Получаем настройки из Redis (если есть) или из settings
        gemini_key_redis = redis_client.get("config:gemini_key")
        gemini_key = gemini_key_redis.decode() if gemini_key_redis else settings.GEMINI_API_KEY

        # Проксі: спочатку config:proxy (JSON), потім config:proxy_*, потім settings (.env)
        proxy_host = None
        proxy_login = None
        proxy_password = None
        proxy_http_port = settings.PROXY_HTTP_PORT
        proxy_socks_port = settings.PROXY_SOCKS_PORT
        
        # 1. Спочатку перевіряємо JSON конфіг з Redis
        config_proxy_raw = redis_client.get("config:proxy")
        if config_proxy_raw:
            try:
                import json
                p = json.loads(config_proxy_raw.decode())
                proxy_host = p.get("host") or None
                proxy_login = p.get("login") or None
                proxy_password = p.get("password") or None
                proxy_http_port = p.get("http_port") or settings.PROXY_HTTP_PORT
                proxy_socks_port = p.get("socks_port") or settings.PROXY_SOCKS_PORT
            except Exception:
                pass
        
        # 2. Потім перевіряємо окремі ключі в Redis
        if not proxy_host:
            ph = redis_client.get("config:proxy_host")
            proxy_host = (ph.decode().strip() if ph else None) or None
        if not proxy_login:
            pl = redis_client.get("config:proxy_login")
            proxy_login = (pl.decode().strip() if pl else None) or None
        if not proxy_password:
            pp = redis_client.get("config:proxy_password")
            proxy_password = (pp.decode().strip() if pp else None) or None
        try:
            pport = redis_client.get("config:proxy_http_port")
            if pport and pport.decode().strip():
                proxy_http_port = int(pport.decode().strip())
        except Exception:
            pass
        try:
            psport = redis_client.get("config:proxy_socks_port")
            if psport and psport.decode().strip():
                proxy_socks_port = int(psport.decode().strip())
        except Exception:
            pass
        
        # 3. Фінальний fallback на settings (.env)
        if not proxy_host:
            proxy_host = settings.PROXY_HOST
        if not proxy_login:
            proxy_login = settings.PROXY_LOGIN
        if not proxy_password:
            proxy_password = settings.PROXY_PASSWORD
        
        logger.info(f"Proxy config: host={proxy_host}, port={proxy_http_port}, login={proxy_login[:3] if proxy_login else None}***")

        prompt_redis = redis_client.get("config:prompt")
        prompt_template = prompt_redis.decode() if prompt_redis else None

        webhook_url_raw = redis_client.get("config:webhook_url")
        webhook_url = webhook_url_raw.decode() if webhook_url_raw else settings.WEBHOOK_URL
        webhook_token_raw = redis_client.get("config:webhook_token")
        webhook_token = webhook_token_raw.decode() if webhook_token_raw else settings.WEBHOOK_TOKEN

        config = {
            'gemini_key': gemini_key,
            'prompt': prompt_template,
            'webhook': {
                'url': webhook_url,
                'token': webhook_token
            },
            'proxy': {
                'host': proxy_host,
                'http_port': proxy_http_port,
                'socks_port': proxy_socks_port,
                'login': proxy_login,
                'password': proxy_password
            } if proxy_host else None,
            'domain_names': domain_names  # Маппінг domain → shop name з API
        }
        
        start_batch_scraping.delay(domains, session.id, config)
        
        redis_client.set("scraping:status", "running")
        redis_client.set("scraping:session_id", str(session.id))
        
        return ParsingStartResponse(
            session_id=session.id,
            status="running",
            message=f"Парсинг успішно запущено для {len(domains)} доменів",
            total_domains=len(domains)
        )
    except Exception as e:
        logger.error(f"Помилка запуску парсингу: {e}")
        # Оновлюємо статус сесії на failed
        crud.update_scraping_session(db, session.id, status="failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Помилка запуску парсингу: {str(e)}"
        )


@router.post("/stop")
async def stop_parsing(db: Session = Depends(get_db)):
    """
    Зупинити поточний парсинг - скасувати всі Celery задачі та скинути статус
    """
    import logging
    from app.db import crud
    from app.tasks.celery_app import celery_app
    
    logger = logging.getLogger(__name__)
    
    current_status = redis_client.get("scraping:status")
    if not current_status or current_status.decode() not in ("running", "pending"):
        # Все одно скидаємо статус, якщо щось застрягло
        pass
    
    # 1. Встановлюємо флаг зупинки (задачі перевірятимуть це)
    redis_client.set("scraping:stop_requested", "1")
    redis_client.set("scraping:status", "stopping")
    
    # 2. Отримуємо session_id та скасовуємо всі задачі
    session_id_raw = redis_client.get("scraping:session_id")
    session_id = int(session_id_raw.decode()) if session_id_raw else None
    
    revoked_count = 0
    
    # 2a. Скасовуємо всі задачі з черги
    try:
        # Отримуємо збережені task_ids
        task_ids_raw = redis_client.get("scraping:task_ids")
        if task_ids_raw:
            import json
            task_ids = json.loads(task_ids_raw.decode())
            for task_id in task_ids:
                try:
                    celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
                    revoked_count += 1
                except Exception as e:
                    logger.warning(f"Не вдалося скасувати задачу {task_id}: {e}")
            logger.info(f"Скасовано {revoked_count} задач")
    except Exception as e:
        logger.error(f"Помилка скасування задач: {e}")
    
    # 2b. Purge черги (скасувати всі очікуючі задачі)
    try:
        celery_app.control.purge()
        logger.info("Черга Celery очищена")
    except Exception as e:
        logger.warning(f"Помилка очищення черги: {e}")
    
    # 3. Оновлюємо статус сесії в БД
    if session_id:
        try:
            crud.update_scraping_session(db, session_id, status="stopped")
            logger.info(f"Сесію {session_id} позначено як зупинену")
        except Exception as e:
            logger.error(f"Помилка оновлення сесії: {e}")
    
    # 4. Очищаємо Redis
    redis_client.set("scraping:status", "stopped")
    redis_client.delete("scraping:task_ids")
    redis_client.delete("scraping:stop_requested")
    
    # Через 2 секунди скидаємо статус на idle
    import threading
    def reset_to_idle():
        import time
        time.sleep(2)
        redis_client.set("scraping:status", "idle")
        redis_client.delete("scraping:session_id")
    
    threading.Thread(target=reset_to_idle, daemon=True).start()
    
    return {
        "success": True,
        "message": f"Парсинг зупинено. Скасовано {revoked_count} задач.",
        "revoked_tasks": revoked_count
    }


@router.post("/clear-queue")
async def clear_celery_queue():
    """
    Очистити чергу Celery від накопичених задач.
    
    Видаляє:
    - Всі задачі з черги Celery
    - Флаг активної сесії парсингу
    - Збережені task_ids
    - Скидає статус на idle
    """
    import logging
    from app.tasks.celery_app import celery_app
    
    logger = logging.getLogger(__name__)
    
    results = {
        "queue_purged": False,
        "active_session_cleared": False,
        "task_ids_cleared": False,
        "status_reset": False,
        "errors": []
    }
    
    # 1. Purge черги Celery
    try:
        purge_result = celery_app.control.purge()
        results["queue_purged"] = True
        results["purged_count"] = purge_result if isinstance(purge_result, int) else 0
        logger.info(f"Черга Celery очищена: {purge_result}")
    except Exception as e:
        logger.error(f"Помилка очищення черги Celery: {e}")
        results["errors"].append(f"Purge error: {str(e)}")
    
    # 2. Видаляємо флаг активної сесії
    try:
        deleted = redis_client.delete("parsing:active_session")
        results["active_session_cleared"] = deleted > 0
        logger.info(f"Флаг active_session видалено: {deleted}")
    except Exception as e:
        logger.error(f"Помилка видалення active_session: {e}")
        results["errors"].append(f"Active session error: {str(e)}")
    
    # 3. Видаляємо збережені task_ids
    try:
        deleted = redis_client.delete("scraping:task_ids")
        results["task_ids_cleared"] = deleted > 0
    except Exception as e:
        results["errors"].append(f"Task IDs error: {str(e)}")
    
    # 4. Скидаємо статус парсингу
    try:
        redis_client.set("scraping:status", "idle")
        redis_client.delete("scraping:session_id")
        redis_client.delete("scraping:stop_requested")
        results["status_reset"] = True
    except Exception as e:
        results["errors"].append(f"Status reset error: {str(e)}")
    
    # 5. Видаляємо всі ключі прогресу сесій
    try:
        progress_keys = redis_client.keys("session:*:progress")
        if progress_keys:
            redis_client.delete(*progress_keys)
            results["progress_keys_cleared"] = len(progress_keys)
        else:
            results["progress_keys_cleared"] = 0
    except Exception as e:
        results["errors"].append(f"Progress keys error: {str(e)}")
    
    success = len(results["errors"]) == 0
    
    return {
        "success": success,
        "message": "Черга Celery очищена" if success else "Часткова очистка з помилками",
        "details": results
    }


def _idle_status() -> ParsingStatusResponse:
    """Повернути порожній статус (idle). Використовується при помилках або відсутності сесії."""
    from datetime import datetime
    return ParsingStatusResponse(
        session_id=0,
        status=ScrapingStatus("idle"),
        total_domains=0,
        processed_domains=0,
        successful_domains=0,
        failed_domains=0,
        progress_percent=0.0,
        domains_per_hour=0.0,
        started_at=datetime.utcnow(),
        estimated_completion=datetime.utcnow()
    )


@router.get("/status", response_model=ParsingStatusResponse)
async def get_parsing_status(db: Session = Depends(get_db)):
    """
    Отримати статус поточного процесу парсингу з реальними даними з БД
    
    Синхронізує scraping:status з parsing:active_session для коректного відображення
    """
    import logging
    from app.db import crud
    from datetime import datetime, timedelta

    logger = logging.getLogger(__name__)

    try:
        current_status = redis_client.get("scraping:status")
        status_str = current_status.decode() if current_status else "idle"
    except Exception as e:
        logger.warning("Redis unavailable in /status: %s", e)
        return _idle_status()

    try:
        session_id_raw = redis_client.get("scraping:session_id")
        session_id = int(session_id_raw.decode()) if session_id_raw else None
    except Exception as e:
        logger.warning("Redis session_id read failed: %s", e)
        session_id = None
    
    # Перевіряємо активну сесію з scheduler
    try:
        active_session_raw = redis_client.get("parsing:active_session")
        active_session_id = int(active_session_raw.decode()) if active_session_raw else None
    except Exception:
        active_session_id = None
    
    # Синхронізуємо: якщо є активна сесія але status не "running", синхронізуємо
    if active_session_id and status_str not in ("running", "stopping"):
        session_id = active_session_id
        status_str = "running"
        # Оновлюємо Redis для консистентності
        try:
            redis_client.set("scraping:status", "running")
            redis_client.set("scraping:session_id", str(active_session_id))
        except Exception:
            pass

    if session_id:
        try:
            session = crud.get_scraping_session(db, session_id)
        except Exception as e:
            logger.warning("DB error in get_parsing_status: %s", e)
            return _idle_status()

        if session:
            total = session.total_domains or 0
            processed = session.processed_domains or 0
            successful = session.successful_domains or 0
            failed = session.failed_domains or 0

            progress_percent = (processed / total * 100) if total > 0 else 0.0

            # Конвертуємо timezone-aware в naive для порівняння
            started_at_naive = session.started_at.replace(tzinfo=None) if session.started_at and session.started_at.tzinfo else session.started_at
            completed_at_naive = session.completed_at.replace(tzinfo=None) if session.completed_at and session.completed_at.tzinfo else session.completed_at
            
            if started_at_naive:
                duration = (datetime.utcnow() - started_at_naive).total_seconds() / 3600
                domains_per_hour = processed / duration if duration > 0 else 0.0
            else:
                domains_per_hour = 0.0

            if processed > 0 and total > processed and domains_per_hour > 0:
                remaining = total - processed
                estimated_completion = datetime.utcnow() + timedelta(
                    hours=remaining / domains_per_hour
                )
            else:
                estimated_completion = completed_at_naive or datetime.utcnow()

            return ParsingStatusResponse(
                session_id=session_id,
                status=ScrapingStatus(session.status or status_str),
                total_domains=total,
                processed_domains=processed,
                successful_domains=successful,
                failed_domains=failed,
                progress_percent=round(progress_percent, 1),
                domains_per_hour=round(domains_per_hour, 1),
                started_at=session.started_at or datetime.utcnow(),
                estimated_completion=estimated_completion
            )

    return _idle_status()


@router.get("/progress/{session_id}", response_model=ParsingStatusResponse)
async def get_session_progress(session_id: int, db: Session = Depends(get_db)):
    """
    Отримати прогрес конкретної сесії парсингу
    """
    from datetime import datetime, timedelta
    
    status_raw = redis_client.get("scraping:status")
    status_str = status_raw.decode() if status_raw else "idle"
    
    # Mock дані синхронізовані з /reports
    return ParsingStatusResponse(
        session_id=session_id,
        status=ScrapingStatus(status_str),
        total_domains=3,  # example.com, test.com, demo.org
        processed_domains=3,
        successful_domains=2,
        failed_domains=1,
        progress_percent=100.0,
        domains_per_hour=180.0,
        started_at=datetime.now() - timedelta(minutes=5),
        estimated_completion=datetime.now()
    )


@router.get("/history", response_model=ParsingHistoryResponse)
async def get_parsing_history(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Отримати історію парсингу
    
    - **skip**: Кількість записів для пропуску
    - **limit**: Максимальна кількість записів для повернення
    """
    # TODO: Отримати історію з БД
    
    # Mock дані
    return ParsingHistoryResponse(
        sessions=[],
        total=0
    )


@router.get("/diagnostic")
async def get_parsing_diagnostic(db: Session = Depends(get_db)):
    """
    Отримати діагностичну інформацію про стан парсингу.
    Корисно для дебагу рассинхронізації статусів.
    """
    from app.db import crud
    
    result = {
        "redis": {},
        "db": {},
        "celery": {},
        "recommendations": []
    }
    
    # Redis state
    try:
        result["redis"]["scraping:status"] = redis_client.get("scraping:status")
        if result["redis"]["scraping:status"]:
            result["redis"]["scraping:status"] = result["redis"]["scraping:status"].decode()
        
        result["redis"]["scraping:session_id"] = redis_client.get("scraping:session_id")
        if result["redis"]["scraping:session_id"]:
            result["redis"]["scraping:session_id"] = result["redis"]["scraping:session_id"].decode()
        
        result["redis"]["parsing:active_session"] = redis_client.get("parsing:active_session")
        if result["redis"]["parsing:active_session"]:
            result["redis"]["parsing:active_session"] = result["redis"]["parsing:active_session"].decode()
        
        result["redis"]["scraping:stop_requested"] = redis_client.get("scraping:stop_requested")
        if result["redis"]["scraping:stop_requested"]:
            result["redis"]["scraping:stop_requested"] = result["redis"]["scraping:stop_requested"].decode()
        
        # TTL для active_session
        ttl = redis_client.ttl("parsing:active_session")
        result["redis"]["parsing:active_session_ttl"] = ttl if ttl > 0 else None
        
    except Exception as e:
        result["redis"]["error"] = str(e)
    
    # DB state for active session
    try:
        active_session_id = result["redis"].get("parsing:active_session")
        if active_session_id:
            session = crud.get_scraping_session(db, int(active_session_id))
            if session:
                result["db"]["session_id"] = session.id
                result["db"]["status"] = session.status
                result["db"]["total_domains"] = session.total_domains
                result["db"]["processed_domains"] = session.processed_domains
                result["db"]["successful_domains"] = session.successful_domains
                result["db"]["failed_domains"] = session.failed_domains
                result["db"]["started_at"] = session.started_at.isoformat() if session.started_at else None
    except Exception as e:
        result["db"]["error"] = str(e)
    
    # Celery state
    try:
        from app.tasks.celery_app import celery_app
        inspect = celery_app.control.inspect()
        active = inspect.active()
        reserved = inspect.reserved()
        
        result["celery"]["active_tasks"] = sum(len(v) for v in (active or {}).values())
        result["celery"]["reserved_tasks"] = sum(len(v) for v in (reserved or {}).values())
        
        # Отримуємо кількість задач в черзі
        try:
            with celery_app.connection_or_acquire() as conn:
                queue_length = conn.default_channel.queue_declare(
                    queue='celery', passive=True
                ).message_count
                result["celery"]["queue_length"] = queue_length
        except Exception:
            result["celery"]["queue_length"] = "unknown"
            
    except Exception as e:
        result["celery"]["error"] = str(e)
    
    # Recommendations
    if result["redis"].get("parsing:active_session") and result["redis"].get("scraping:status") != "running":
        result["recommendations"].append(
            "Десинхронізація: є активна сесія але статус не 'running'. "
            "Використайте POST /api/v1/parsing/sync-state для синхронізації."
        )
    
    if result["celery"].get("active_tasks", 0) == 0 and result["redis"].get("parsing:active_session"):
        result["recommendations"].append(
            "Можливо застрягла сесія: активна сесія є, але Celery не обробляє задачі. "
            "Використайте POST /api/v1/parsing/clear-queue для очистки."
        )
    
    return result


@router.post("/sync-state")
async def sync_parsing_state(db: Session = Depends(get_db)):
    """
    Синхронізувати стан парсингу між Redis ключами.
    
    Якщо є активна сесія (parsing:active_session) але scraping:status не відповідає,
    синхронізує їх.
    """
    from app.db import crud
    import logging
    
    logger = logging.getLogger(__name__)
    result = {"synced": False, "actions": []}
    
    try:
        active_session_raw = redis_client.get("parsing:active_session")
        active_session_id = int(active_session_raw.decode()) if active_session_raw else None
        
        current_status = redis_client.get("scraping:status")
        status_str = current_status.decode() if current_status else "idle"
        
        if active_session_id:
            # Є активна сесія - перевіряємо її статус в БД
            session = crud.get_scraping_session(db, active_session_id)
            
            if session and session.status in ("running", "pending"):
                # Сесія активна в БД - синхронізуємо Redis
                if status_str != "running":
                    redis_client.set("scraping:status", "running")
                    redis_client.set("scraping:session_id", str(active_session_id))
                    result["actions"].append(f"Встановлено scraping:status=running для сесії {active_session_id}")
                result["synced"] = True
            elif session and session.status in ("completed", "failed"):
                # Сесія завершена в БД - очищаємо active_session
                redis_client.delete("parsing:active_session")
                redis_client.set("scraping:status", session.status)
                result["actions"].append(f"Очищено active_session, статус={session.status}")
                result["synced"] = True
            else:
                # Сесія не знайдена - очищаємо все
                redis_client.delete("parsing:active_session")
                redis_client.set("scraping:status", "idle")
                redis_client.delete("scraping:session_id")
                result["actions"].append("Очищено застряглий стан (сесія не знайдена в БД)")
                result["synced"] = True
        else:
            # Немає активної сесії
            if status_str == "running":
                # Статус running але немає активної сесії - скидаємо
                redis_client.set("scraping:status", "idle")
                redis_client.delete("scraping:session_id")
                result["actions"].append("Скинуто статус running без активної сесії")
                result["synced"] = True
            else:
                result["actions"].append("Стан вже синхронізований")
                result["synced"] = True
        
        logger.info(f"Sync state result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error syncing state: {e}")
        return {"synced": False, "error": str(e)}
