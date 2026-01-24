"""
CRUD (Create, Read, Update, Delete) операції для роботи з БД
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime

from app.models.domain import Domain
from app.models.scraping_session import ScrapingSession
from app.models.scraped_deal import ScrapedDeal
from app.models.config import Config
from app.models.cron_job import CronJob


# ========== Domains ==========

def get_domain(db: Session, domain_id: int) -> Optional[Domain]:
    """Отримати домен за ID"""
    return db.query(Domain).filter(Domain.id == domain_id).first()


def get_domain_by_name(db: Session, domain_name: str) -> Optional[Domain]:
    """Отримати домен за назвою"""
    return db.query(Domain).filter(Domain.domain == domain_name).first()


def get_domains(db: Session, skip: int = 0, limit: int = 100) -> List[Domain]:
    """Отримати список доменів"""
    return db.query(Domain).offset(skip).limit(limit).all()


def create_domain(db: Session, domain_name: str) -> Domain:
    """Створити новий домен"""
    db_domain = Domain(domain=domain_name, scraping_status="pending")
    db.add(db_domain)
    db.commit()
    db.refresh(db_domain)
    return db_domain


def update_domain_status(
    db: Session,
    domain_id: int,
    status: str,
    error_count: Optional[int] = None
) -> Optional[Domain]:
    """Оновити статус домену"""
    domain = get_domain(db, domain_id)
    if domain:
        domain.scraping_status = status
        domain.last_scraped_at = datetime.utcnow()
        if error_count is not None:
            domain.error_count = error_count
        db.commit()
        db.refresh(domain)
    return domain


# ========== Scraping Sessions ==========

def create_scraping_session(db: Session, total_domains: int) -> ScrapingSession:
    """Створити нову сесію парсингу"""
    session = ScrapingSession(
        total_domains=total_domains,
        status="running"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_scraping_session(db: Session, session_id: int) -> Optional[ScrapingSession]:
    """Отримати сесію за ID"""
    return db.query(ScrapingSession).filter(ScrapingSession.id == session_id).first()


def get_scraping_sessions(
    db: Session,
    skip: int = 0,
    limit: int = 100
) -> List[ScrapingSession]:
    """Отримати список сесій"""
    return db.query(ScrapingSession).order_by(
        desc(ScrapingSession.started_at)
    ).offset(skip).limit(limit).all()


def update_scraping_session(
    db: Session,
    session_id: int,
    processed: Optional[int] = None,
    successful: Optional[int] = None,
    failed: Optional[int] = None,
    status: Optional[str] = None
) -> Optional[ScrapingSession]:
    """Оновити статус сесії"""
    session = get_scraping_session(db, session_id)
    if session:
        if processed is not None:
            session.processed_domains = processed
        if successful is not None:
            session.successful_domains = successful
        if failed is not None:
            session.failed_domains = failed
        if status:
            session.status = status
            if status in ["completed", "failed"]:
                session.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
    return session


# ========== Scraped Deals ==========

def create_scraped_deal(
    db: Session,
    session_id: int,
    domain: str,
    deal_data: dict
) -> ScrapedDeal:
    """Створити запис про знайдену угоду"""
    deal = ScrapedDeal(
        session_id=session_id,
        domain=domain,
        deal_data=deal_data
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def get_scraped_deals(
    db: Session,
    session_id: Optional[int] = None,
    domain: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[ScrapedDeal]:
    """Отримати список знайдених угод з фільтрами"""
    query = db.query(ScrapedDeal)
    
    if session_id:
        query = query.filter(ScrapedDeal.session_id == session_id)
    if domain:
        query = query.filter(ScrapedDeal.domain == domain)
    
    return query.order_by(desc(ScrapedDeal.created_at)).offset(skip).limit(limit).all()


def mark_deal_webhook_sent(db: Session, deal_id: int) -> Optional[ScrapedDeal]:
    """Позначити що угода відправлена в webhook"""
    deal = db.query(ScrapedDeal).filter(ScrapedDeal.id == deal_id).first()
    if deal:
        deal.webhook_sent = True
        deal.webhook_sent_at = datetime.utcnow()
        db.commit()
        db.refresh(deal)
    return deal


def get_deals_summary(db: Session) -> dict:
    """Отримати загальну статистику по угодах"""
    total_deals = db.query(func.count(ScrapedDeal.id)).scalar()
    webhook_sent = db.query(func.count(ScrapedDeal.id)).filter(
        ScrapedDeal.webhook_sent == True
    ).scalar()
    
    return {
        "total_deals": total_deals or 0,
        "webhook_sent": webhook_sent or 0,
        "webhook_pending": (total_deals or 0) - (webhook_sent or 0)
    }


# ========== Config ==========

def get_config(db: Session, key: str) -> Optional[Config]:
    """Отримати конфігурацію за ключем"""
    return db.query(Config).filter(Config.key == key).first()


def get_all_config(db: Session) -> List[Config]:
    """Отримати всі конфігурації"""
    return db.query(Config).all()


def set_config(db: Session, key: str, value: str) -> Config:
    """Встановити конфігурацію"""
    config = get_config(db, key)
    if config:
        config.value = value
        config.updated_at = datetime.utcnow()
    else:
        config = Config(key=key, value=value)
        db.add(config)
    db.commit()
    db.refresh(config)
    return config


def delete_config(db: Session, key: str) -> bool:
    """Видалити конфігурацію"""
    config = get_config(db, key)
    if config:
        db.delete(config)
        db.commit()
        return True
    return False


# ========== Cron Jobs ==========

def create_cron_job(
    db: Session,
    name: str,
    cron_expression: str,
    job_type: str,
    batch_size: Optional[int] = None
) -> CronJob:
    """Створити cron задачу"""
    job = CronJob(
        name=name,
        cron_expression=cron_expression,
        job_type=job_type,
        batch_size=batch_size
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_cron_job(db: Session, job_id: int) -> Optional[CronJob]:
    """Отримати cron задачу за ID"""
    return db.query(CronJob).filter(CronJob.id == job_id).first()


def get_cron_job_by_name(db: Session, name: str) -> Optional[CronJob]:
    """Отримати cron задачу за назвою"""
    return db.query(CronJob).filter(CronJob.name == name).first()


def get_cron_jobs(db: Session, enabled_only: bool = False) -> List[CronJob]:
    """Отримати список cron задач"""
    query = db.query(CronJob)
    if enabled_only:
        query = query.filter(CronJob.enabled == True)
    return query.all()


def update_cron_job(
    db: Session,
    job_id: int,
    cron_expression: Optional[str] = None,
    batch_size: Optional[int] = None,
    enabled: Optional[bool] = None
) -> Optional[CronJob]:
    """Оновити cron задачу"""
    job = get_cron_job(db, job_id)
    if job:
        if cron_expression:
            job.cron_expression = cron_expression
        if batch_size is not None:
            job.batch_size = batch_size
        if enabled is not None:
            job.enabled = enabled
        db.commit()
        db.refresh(job)
    return job


def delete_cron_job(db: Session, job_id: int) -> bool:
    """Видалити cron задачу"""
    job = get_cron_job(db, job_id)
    if job:
        db.delete(job)
        db.commit()
        return True
    return False


def mark_cron_job_run(db: Session, job_id: int) -> Optional[CronJob]:
    """Позначити що задача була виконана"""
    job = get_cron_job(db, job_id)
    if job:
        job.last_run_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
    return job
