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


@router.get("", response_model=DetailedReport)
@router.get("/", response_model=DetailedReport)
async def get_reports_root(db: Session = Depends(get_db)):
    """
    Базовий endpoint - повертає список доменів
    """
    from datetime import datetime
    
    # Mock дані - список доменів з результатами
    mock_domains = [
        DomainReport(
            domain="example.com",
            session_id=1,
            deals_count=5,
            success=True,
            scraped_at=datetime.now(),
            webhook_sent=True,
            error_count=0,
            last_error=None
        ),
        DomainReport(
            domain="test.com",
            session_id=1,
            deals_count=3,
            success=True,
            scraped_at=datetime.now(),
            webhook_sent=True,
            error_count=0,
            last_error=None
        ),
        DomainReport(
            domain="demo.org",
            session_id=1,
            deals_count=0,
            success=False,
            scraped_at=datetime.now(),
            webhook_sent=False,
            error_count=1,
            last_error="Connection timeout"
        )
    ]
    
    return DetailedReport(
        domains=mock_domains,
        total=len(mock_domains)
    )


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
    from datetime import datetime
    
    # Mock дані синхронізовані з /reports endpoint
    return ReportSummary(
        total_domains=3,  # example.com, test.com, demo.org
        total_sessions=1,
        total_deals_found=8,  # 5 + 3 + 0
        total_deals_sent=8,
        successful_scrapes=2,  # example.com, test.com
        failed_scrapes=1,  # demo.org
        average_deals_per_domain=2.67,  # 8 / 3
        last_scrape_date=datetime.now(),
        domains_per_hour_avg=180.0
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
