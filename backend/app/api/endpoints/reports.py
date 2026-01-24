from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.reports import (
    ReportSummary,
    DetailedReport,
    DomainReport,
    ExportResponse
)
from typing import Optional, Literal
import csv
import json
import io

router = APIRouter()


@router.get("/summary", response_model=ReportSummary)
async def get_summary(db: Session = Depends(get_db)):
    """
    Отримати загальну статистику по всій системі
    
    Включає:
    - Загальну кількість доменів
    - Кількість сесій парсингу
    - Кількість знайдених угод
    - Успішні/невдалі спроби
    - Середню продуктивність
    """
    # TODO: Отримати реальні дані з БД
    
    return ReportSummary(
        total_domains=1500,
        total_sessions=25,
        total_deals_found=3200,
        total_deals_sent=3150,
        successful_scrapes=1420,
        failed_scrapes=80,
        average_deals_per_domain=2.13,
        last_scrape_date=None,
        domains_per_hour_avg=185.5
    )


@router.get("/detailed", response_model=DetailedReport)
async def get_detailed_report(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    status: Optional[str] = Query(None, description="Фільтр по статусу"),
    search: Optional[str] = Query(None, description="Пошук по домену"),
    db: Session = Depends(get_db)
):
    """
    Отримати детальний звіт по доменам
    
    - **skip**: Пропустити N записів
    - **limit**: Максимум записів для повернення
    - **status**: Фільтр по статусу (success, failed, pending)
    - **search**: Пошук по назві домену
    """
    # TODO: Отримати дані з БД з фільтрами
    
    return DetailedReport(
        domains=[],
        total=0
    )


@router.get("/export")
async def export_report(
    format: Literal["csv", "json"] = Query("csv", description="Формат експорту"),
    session_id: Optional[int] = Query(None, description="ID сесії для експорту"),
    db: Session = Depends(get_db)
):
    """
    Експортувати звіт у CSV або JSON форматі
    
    - **format**: csv або json
    - **session_id**: Експортувати конкретну сесію (None = всі)
    """
    # TODO: Отримати дані з БД
    
    # Mock дані для демонстрації
    deals = [
        {
            "id": 1,
            "domain": "example.com",
            "shop": "Example Shop",
            "description": "Знижка 20%",
            "code": "SAVE20",
            "discount": "20%",
            "created_at": "2026-01-24 12:00:00"
        }
    ]
    
    if format == "csv":
        # Створюємо CSV
        output = io.StringIO()
        if deals:
            writer = csv.DictWriter(output, fieldnames=deals[0].keys())
            writer.writeheader()
            writer.writerows(deals)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=scraping_report.csv"
            }
        )
    
    else:  # JSON
        return {
            "format": "json",
            "records_count": len(deals),
            "data": deals
        }
