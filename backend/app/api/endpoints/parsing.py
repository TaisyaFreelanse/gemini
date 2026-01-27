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
        
        proxy_host_redis = redis_client.get("config:proxy_host")
        proxy_host = proxy_host_redis.decode() if proxy_host_redis else settings.PROXY_HOST
        
        proxy_login_redis = redis_client.get("config:proxy_login")
        proxy_login = proxy_login_redis.decode() if proxy_login_redis else settings.PROXY_LOGIN
        
        proxy_password_redis = redis_client.get("config:proxy_password")
        proxy_password = proxy_password_redis.decode() if proxy_password_redis else settings.PROXY_PASSWORD
        
        config = {
            'gemini_key': gemini_key,
            'webhook': {
                'url': settings.WEBHOOK_URL,
                'token': settings.WEBHOOK_TOKEN
            },
            'proxy': {
                'host': proxy_host,
                'http_port': settings.PROXY_HTTP_PORT,
                'socks_port': settings.PROXY_SOCKS_PORT,
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


@router.get("/status", response_model=ParsingStatusResponse)
async def get_parsing_status(db: Session = Depends(get_db)):
    """
    Отримати статус поточного процесу парсингу з реальними даними з БД
    """
    from app.db import crud
    from datetime import datetime, timedelta
    
    current_status = redis_client.get("scraping:status")
    status_str = current_status.decode() if current_status else "idle"
    
    # Отримуємо ID поточної сесії
    session_id_raw = redis_client.get("scraping:session_id")
    session_id = int(session_id_raw.decode()) if session_id_raw else None
    
    # Якщо є активна сесія, отримуємо дані з БД
    if session_id:
        session = crud.get_scraping_session(db, session_id)
        if session:
            total = session.total_domains or 0
            processed = session.processed_domains or 0
            successful = session.successful_domains or 0
            failed = session.failed_domains or 0
            
            # Розраховуємо прогрес
            progress_percent = (processed / total * 100) if total > 0 else 0.0
            
            # Розраховуємо швидкість
            if session.started_at:
                duration = (datetime.utcnow() - session.started_at).total_seconds() / 3600
                domains_per_hour = processed / duration if duration > 0 else 0.0
            else:
                domains_per_hour = 0.0
            
            # Оцінка завершення
            if processed > 0 and total > processed:
                remaining = total - processed
                estimated_completion = datetime.utcnow() + timedelta(
                    hours=remaining / domains_per_hour if domains_per_hour > 0 else 1
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
    
    # Якщо немає активної сесії, повертаємо порожній статус
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
