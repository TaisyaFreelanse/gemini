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


def _empty_detailed_report() -> DetailedReport:
    return DetailedReport(domains=[], total=0)


@router.get("", response_model=DetailedReport)
@router.get("/", response_model=DetailedReport)
async def get_reports_root(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    status: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Базовий endpoint - повертає список доменів з реальними даними з БД
    """
    import logging
    from sqlalchemy import func, case
    from app.models.scraped_deal import ScrapedDeal
    from app.models.scraping_session import ScrapingSession

    logger = logging.getLogger(__name__)

    try:
        query = db.query(
            ScrapedDeal.domain,
            ScrapedDeal.session_id,
            func.count(ScrapedDeal.id).label('deals_count'),
            func.max(ScrapedDeal.created_at).label('scraped_at'),
            func.max(case((ScrapedDeal.webhook_sent == True, 1), else_=0)).label('webhook_sent'),
            func.count(case((ScrapedDeal.webhook_sent == False, 1))).label('webhook_pending')
        ).group_by(ScrapedDeal.domain, ScrapedDeal.session_id)

        if domain:
            query = query.filter(ScrapedDeal.domain.ilike(f"%{domain}%"))

        total = query.count()
        results = query.order_by(func.max(ScrapedDeal.created_at).desc()).offset(skip).limit(limit).all()

        domain_reports = []
        for result in results:
            success = result.deals_count > 0
            domain_reports.append(
                DomainReport(
                    domain=result.domain,
                    session_id=result.session_id,
                    deals_count=result.deals_count,
                    success=success,
                    scraped_at=result.scraped_at,
                    webhook_sent=bool(result.webhook_sent),
                    error_count=0 if success else 1,
                    last_error=None if success else "No deals found"
                )
            )

        return DetailedReport(domains=domain_reports, total=total)
    except Exception as e:
        logger.warning("Reports root error: %s", e)
        return _empty_detailed_report()


@router.get("/summary", response_model=ReportSummary)
async def get_summary(db: Session = Depends(get_db)):
    """
    Отримати загальну статистику по всій системі з реальними даними з БД
    """
    from app.models.scraped_deal import ScrapedDeal
    from app.models.scraping_session import ScrapingSession
    from sqlalchemy import func, distinct
    
    # Отримуємо реальні дані з БД
    try:
        total_deals = db.query(func.count(ScrapedDeal.id)).scalar() or 0
        total_deals_sent = db.query(func.count(ScrapedDeal.id)).filter(
            ScrapedDeal.webhook_sent == True
        ).scalar() or 0
        
        # Унікальні домени
        unique_domains = db.query(func.count(distinct(ScrapedDeal.domain))).scalar() or 0
        
        # Сесії
        total_sessions = db.query(func.count(ScrapingSession.id)).scalar() or 0
        successful_sessions = db.query(func.count(ScrapingSession.id)).filter(
            ScrapingSession.status == "completed"
        ).scalar() or 0
        failed_sessions = db.query(func.count(ScrapingSession.id)).filter(
            ScrapingSession.status == "failed"
        ).scalar() or 0
        
        # Остання дата парсингу
        last_scrape = db.query(func.max(ScrapedDeal.created_at)).scalar()
        
        # Середня кількість угод на домен
        avg_deals = total_deals / unique_domains if unique_domains > 0 else 0
        
        # Середня швидкість (доменів за годину) - беремо з останньої сесії
        last_session = db.query(ScrapingSession).order_by(
            ScrapingSession.started_at.desc()
        ).first()
        
        domains_per_hour = 0
        if last_session and last_session.completed_at and last_session.started_at:
            duration_hours = (last_session.completed_at - last_session.started_at).total_seconds() / 3600
            if duration_hours > 0:
                domains_per_hour = last_session.processed_domains / duration_hours
    except Exception as e:
        # Если таблицы не существуют, возвращаем нулевые значения
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Ошибка получения данных из БД: {e}")
        total_deals = 0
        total_deals_sent = 0
        unique_domains = 0
        total_sessions = 0
        successful_sessions = 0
        failed_sessions = 0
        last_scrape = None
        avg_deals = 0
        domains_per_hour = 0
    
    return ReportSummary(
        total_domains=unique_domains,
        total_sessions=total_sessions,
        total_deals_found=total_deals,
        total_deals_sent=total_deals_sent,
        successful_scrapes=successful_sessions,
        failed_scrapes=failed_sessions,
        average_deals_per_domain=round(avg_deals, 2),
        last_scrape_date=last_scrape,
        domains_per_hour_avg=round(domains_per_hour, 2) if domains_per_hour > 0 else 0.0
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
    domain: Optional[str] = Query(None, description="Фільтр за доменом"),
    db: Session = Depends(get_db)
):
    """
    Експортувати звіт у CSV або JSON форматі
    
    - **format**: csv або json
    - **session_id**: Експортувати конкретну сесію (None = всі)
    - **domain**: Фільтр за доменом (None = всі)
    """
    from app.db import crud
    from datetime import datetime
    
    # Отримуємо реальні дані з БД
    scraped_deals = crud.get_scraped_deals(
        db, 
        session_id=session_id, 
        domain=domain,
        limit=10000  # Максимум для експорту
    )
    
    # Перетворюємо в плоский формат для експорту
    deals = []
    for deal in scraped_deals:
        deal_data = deal.deal_data or {}
        flat_deal = {
            "id": deal.id,
            "session_id": deal.session_id,
            "domain": deal.domain,
            "shop": deal_data.get("shop", ""),
            "description": deal_data.get("description", ""),
            "full_description": deal_data.get("full_description", ""),
            "code": deal_data.get("code", ""),
            "discount": deal_data.get("discount", ""),
            "offer_type": deal_data.get("offer_type", ""),
            "target_url": deal_data.get("target_url", ""),
            "date_start": deal_data.get("date_start", ""),
            "date_end": deal_data.get("date_end", ""),
            "categories": ", ".join(deal_data.get("categories", [])) if deal_data.get("categories") else "",
            "webhook_sent": deal.webhook_sent,
            "created_at": deal.created_at.strftime("%Y-%m-%d %H:%M:%S") if deal.created_at else ""
        }
        deals.append(flat_deal)
    
    if not deals:
        deals = [{"message": "Немає даних для експорту"}]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if format == "csv":
        # Створюємо CSV
        output = io.StringIO()
        if deals and "message" not in deals[0]:
            writer = csv.DictWriter(output, fieldnames=deals[0].keys())
            writer.writeheader()
            writer.writerows(deals)
        else:
            output.write("Немає даних для експорту")
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=scraping_report_{timestamp}.csv"
            }
        )
    
    else:  # JSON
        export_data = {
            "format": "json",
            "exported_at": datetime.now().isoformat(),
            "records_count": len(deals) if "message" not in deals[0] else 0,
            "filters": {
                "session_id": session_id,
                "domain": domain
            },
            "data": deals if "message" not in deals[0] else []
        }
        
        json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
        
        return StreamingResponse(
            iter([json_content]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=scraping_report_{timestamp}.json"
            }
        )