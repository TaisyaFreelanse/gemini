from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ReportSummary(BaseModel):
    """Загальна статистика"""
    total_domains: int
    total_sessions: int
    total_deals_found: int
    total_deals_sent: int
    successful_scrapes: int
    failed_scrapes: int
    average_deals_per_domain: float
    last_scrape_date: Optional[datetime]
    domains_per_hour_avg: float


class DomainReport(BaseModel):
    """Звіт по окремому домену"""
    domain: str
    last_scraped_at: Optional[datetime]
    scraping_status: str
    deals_found: int
    error_count: int
    last_error: Optional[str]

    class Config:
        from_attributes = True


class DetailedReport(BaseModel):
    """Детальний звіт"""
    domains: List[DomainReport]
    total: int


class DealExport(BaseModel):
    """Експорт угоди"""
    id: int
    session_id: int
    domain: str
    shop: str
    description: str
    code: Optional[str]
    discount: Optional[str]
    date_start: Optional[str]
    date_end: Optional[str]
    target_url: str
    webhook_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ExportResponse(BaseModel):
    """Відповідь експорту"""
    format: str
    records_count: int
    data: List[DealExport]
