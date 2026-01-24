from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.db.session import Base


class ScrapingSession(Base):
    """
    Модель для історії запусків парсингу
    """
    __tablename__ = "scraping_sessions"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    total_domains = Column(Integer, default=0)
    processed_domains = Column(Integer, default=0)
    successful_domains = Column(Integer, default=0)
    failed_domains = Column(Integer, default=0)
    status = Column(String(50), default="running")  # running, completed, failed

    # Relationships
    deals = relationship("ScrapedDeal", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ScrapingSession(id={self.id}, status='{self.status}', total={self.total_domains})>"
