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
    # TODO: Перевірити чи не запущено вже парсинг
    current_status = redis_client.get("scraping:status")
    if current_status and current_status.decode() == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Парсинг вже запущено. Зупиніть поточний процес перед запуском нового."
        )
    
    # TODO: Отримати список доменів з API або БД
    # TODO: Створити scraping session в БД
    # TODO: Запустити Celery задачі для обробки доменів
    
    # Поки що повертаємо mock відповідь
    redis_client.set("scraping:status", "running")
    
    return ParsingStartResponse(
        session_id=1,
        status="running",
        message="Парсинг успішно запущено",
        total_domains=request.batch_size or 100
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
    Отримати статус поточного процесу парсингу
    """
    from datetime import datetime, timedelta
    
    current_status = redis_client.get("scraping:status")
    status_str = current_status.decode() if current_status else "idle"
    
    # Mock дані синхронізовані з /reports
    return ParsingStatusResponse(
        session_id=1,
        status=ScrapingStatus(status_str),
        total_domains=3,  # example.com, test.com, demo.org
        processed_domains=3,  # всі оброблено
        successful_domains=2,  # example.com, test.com
        failed_domains=1,  # demo.org
        progress_percent=100.0,  # 3/3 = 100%
        domains_per_hour=180.0,
        started_at=datetime.now() - timedelta(minutes=5),  # 5 хвилин тому
        estimated_completion=datetime.now()  # вже завершено
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
