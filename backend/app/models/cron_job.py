from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.db.session import Base


class CronJob(Base):
    """
    Модель для налаштувань cron задач
    """
    __tablename__ = "cron_jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    cron_expression = Column(String(100), nullable=False)
    job_type = Column(String(50), nullable=False)  # full_scraping, partial_scraping
    batch_size = Column(Integer, nullable=True)
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CronJob(id={self.id}, name='{self.name}', enabled={self.enabled})>"
