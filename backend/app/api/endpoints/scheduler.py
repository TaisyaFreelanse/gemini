from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.services.scheduler import get_scheduler, init_default_jobs

router = APIRouter()


# ========== Schemas ==========

class CronJobCreate(BaseModel):
    """Схема для створення cron задачі"""
    job_id: str = Field(..., description="Унікальний ID задачі")
    cron_expression: str = Field(..., description="Cron вираз (напр. '0 */6 * * *')")
    job_type: str = Field(..., description="Тип задачі: 'full_scraping' або 'partial_scraping'")
    domains: List[str] = Field(default_factory=list, description="Список доменів")
    batch_size: Optional[int] = Field(500, description="Розмір пачки для partial_scraping")
    config: Optional[dict] = Field(default_factory=dict, description="Додаткова конфігурація")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "my_scraping_job",
                "cron_expression": "0 */6 * * *",
                "job_type": "full_scraping",
                "domains": ["example.com", "test.com"],
                "config": {}
            }
        }


class JobResponse(BaseModel):
    """Схема відповіді про задачу"""
    id: str
    name: Optional[str]
    next_run_time: Optional[str]
    trigger: str
    func: str
    pending: bool


class SchedulerStatus(BaseModel):
    """Статус scheduler"""
    is_running: bool
    jobs_count: int
    jobs: List[JobResponse]


# ========== Endpoints ==========

@router.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status():
    """
    Отримати статус scheduler та список задач
    """
    scheduler = get_scheduler()
    
    jobs = scheduler.get_all_jobs()
    
    return {
        "is_running": scheduler.is_running(),
        "jobs_count": len(jobs),
        "jobs": jobs
    }


@router.post("/start")
async def start_scheduler():
    """
    Запустити scheduler
    """
    scheduler = get_scheduler()
    
    if scheduler.is_running():
        return {
            "message": "Scheduler вже запущений",
            "is_running": True
        }
    
    scheduler.start()
    
    return {
        "message": "Scheduler успішно запущено",
        "is_running": True
    }


@router.post("/stop")
async def stop_scheduler(wait: bool = True):
    """
    Зупинити scheduler
    
    Args:
        wait: Чекати завершення поточних задач
    """
    scheduler = get_scheduler()
    
    if not scheduler.is_running():
        return {
            "message": "Scheduler вже зупинений",
            "is_running": False
        }
    
    scheduler.shutdown(wait=wait)
    
    return {
        "message": "Scheduler успішно зупинено",
        "is_running": False
    }


@router.post("/jobs/cron")
async def add_cron_job(job_data: CronJobCreate):
    """
    Додати нову cron задачу
    
    Приклади cron виразів:
    - "0 */6 * * *" - кожні 6 годин
    - "0 0 * * *" - щодня о 00:00
    - "*/30 * * * *" - кожні 30 хвилин
    - "0 9 * * 1" - кожного понеділка о 9:00
    """
    scheduler = get_scheduler()
    
    # Запускаємо scheduler якщо не запущений
    if not scheduler.is_running():
        scheduler.start()
    
    # Додаємо задачу в залежності від типу
    if job_data.job_type == "full_scraping":
        job = scheduler.schedule_full_scraping(
            cron_expression=job_data.cron_expression,
            domains=job_data.domains,
            config=job_data.config
        )
    elif job_data.job_type == "partial_scraping":
        job = scheduler.schedule_partial_scraping(
            cron_expression=job_data.cron_expression,
            all_domains=job_data.domains,
            batch_size=job_data.batch_size,
            config=job_data.config
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Невідомий тип задачі: {job_data.job_type}"
        )
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не вдалося додати задачу"
        )
    
    return {
        "message": f"Задача '{job_data.job_id}' успішно додана",
        "job_id": job.id,
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
    }


@router.delete("/jobs/{job_id}")
async def remove_job(job_id: str):
    """
    Видалити задачу
    """
    scheduler = get_scheduler()
    
    success = scheduler.remove_job(job_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задачу '{job_id}' не знайдено"
        )
    
    return {
        "message": f"Задачу '{job_id}' успішно видалено"
    }


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    """
    Призупинити задачу
    """
    scheduler = get_scheduler()
    
    success = scheduler.pause_job(job_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задачу '{job_id}' не знайдено"
        )
    
    return {
        "message": f"Задачу '{job_id}' призупинено"
    }


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """
    Відновити задачу
    """
    scheduler = get_scheduler()
    
    success = scheduler.resume_job(job_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задачу '{job_id}' не знайдено"
        )
    
    return {
        "message": f"Задачу '{job_id}' відновлено"
    }


@router.get("/jobs/{job_id}")
async def get_job_info(job_id: str):
    """
    Отримати інформацію про конкретну задачу
    """
    scheduler = get_scheduler()
    
    job = scheduler.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задачу '{job_id}' не знайдено"
        )
    
    return {
        "id": job.id,
        "name": job.name,
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        "trigger": str(job.trigger),
        "func": f"{job.func.__module__}.{job.func.__name__}",
        "pending": job.pending
    }


@router.post("/init-defaults")
async def initialize_default_jobs(
    domains: List[str],
    config: Optional[dict] = None
):
    """
    Ініціалізувати дефолтні cron задачі:
    - Повний парсинг кожні 6 годин
    - Частковий парсинг кожні 2 години (500 доменів)
    - Очищення старих сесій раз на добу
    """
    if not domains:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Список доменів не може бути порожнім"
        )
    
    init_default_jobs(domains, config)
    
    scheduler = get_scheduler()
    jobs = scheduler.get_all_jobs()
    
    return {
        "message": "Дефолтні задачі успішно ініціалізовані",
        "jobs_count": len(jobs),
        "jobs": jobs
    }
