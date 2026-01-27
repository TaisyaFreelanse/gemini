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
    
    # Отримати список доменів з API
    domains = []
    try:
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
                
                # Обробляємо домени
                for item in raw_domains:
                    if isinstance(item, str):
                        domains.append(item)
                    elif isinstance(item, dict):
                        url = item.get('url', '') or item.get('domain', '') or item.get('name', '')
                        if url:
                            if '://' in url:
                                from urllib.parse import urlparse
                                parsed = urlparse(url)
                                domain = parsed.netloc or parsed.path
                            else:
                                domain = url
                            if domain:
                                domains.append(domain)
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
                        
                        # Обробляємо домени (можуть бути строки або об'єкти)
                        for item in raw_domains:
                            if isinstance(item, str):
                                domains.append(item)
                            elif isinstance(item, dict):
                                url = item.get('url', '') or item.get('domain', '')
                                if url and '://' in url:
                                    from urllib.parse import urlparse
                                    parsed = urlparse(url)
                                    domain = parsed.netloc or parsed.path
                                else:
                                    domain = url
                                if domain:
                                    domains.append(domain)
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

        # Проксі: спочатку config:proxy (JSON), потім config:proxy_*, потім settings
        proxy_host = None
        proxy_login = None
        proxy_password = None
        proxy_http_port = settings.PROXY_HTTP_PORT
        proxy_socks_port = settings.PROXY_SOCKS_PORT
        config_proxy_raw = redis_client.get("config:proxy")
        if config_proxy_raw:
            try:
                import json
                p = json.loads(config_proxy_raw.decode())
                proxy_host = p.get("host") or None
                proxy_login = p.get("login") or None
                proxy_password = p.get("password") or None
                proxy_http_port = p.get("http_port", settings.PROXY_HTTP_PORT)
                proxy_socks_port = p.get("socks_port", settings.PROXY_SOCKS_PORT)
            except Exception:
                pass
        if proxy_host is None:
            ph = redis_client.get("config:proxy_host")
            proxy_host = ph.decode() if ph else settings.PROXY_HOST
        if proxy_login is None:
            pl = redis_client.get("config:proxy_login")
            proxy_login = pl.decode() if pl else settings.PROXY_LOGIN
        if proxy_password is None:
            pp = redis_client.get("config:proxy_password")
            proxy_password = pp.decode() if pp else settings.PROXY_PASSWORD
        try:
            pport = redis_client.get("config:proxy_http_port")
            if pport:
                proxy_http_port = int(pport.decode())
        except Exception:
            pass
        try:
            psport = redis_client.get("config:proxy_socks_port")
            if psport:
                proxy_socks_port = int(psport.decode())
        except Exception:
            pass

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
            } if proxy_host else None
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
    Зупинити поточний парсинг
    """
    current_status = redis_client.get("scraping:status")
    if not current_status or current_status.decode() != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Немає активного парсингу для зупинки"
        )
    
    # TODO: Зупинити всі Celery задачі
    # TODO: Оновити статус session в БД
    
    redis_client.set("scraping:status", "stopped")
    
    return {
        "success": True,
        "message": "Парсинг зупинено"
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

            if session.started_at:
                duration = (datetime.utcnow() - session.started_at).total_seconds() / 3600
                domains_per_hour = processed / duration if duration > 0 else 0.0
            else:
                domains_per_hour = 0.0

            if processed > 0 and total > processed and domains_per_hour > 0:
                remaining = total - processed
                estimated_completion = datetime.utcnow() + timedelta(
                    hours=remaining / domains_per_hour
                )
            else:
                estimated_completion = session.completed_at or datetime.utcnow()

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
