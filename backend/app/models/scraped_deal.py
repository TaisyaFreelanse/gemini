from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base


class ScrapedDeal(Base):
    """
    Модель для зібраних акцій/промокодів
    """
    __tablename__ = "scraped_deals"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("scraping_sessions.id"), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    deal_data = Column(JSONB, nullable=False)  # Зберігаємо повні дані DealSchema
    webhook_sent = Column(Boolean, default=False)
    webhook_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("ScrapingSession", back_populates="deals")

    def __repr__(self):
        return f"<ScrapedDeal(id={self.id}, domain='{self.domain}', webhook_sent={self.webhook_sent})>"
