from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.session import Base


class Domain(Base):
    """
    Модель для доменів які потрібно парсити
    """
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    scraping_status = Column(String(50), default="pending")  # pending, running, completed, failed
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Domain(id={self.id}, domain='{self.domain}', status='{self.scraping_status}')>"
