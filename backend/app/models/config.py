from sqlalchemy import Column, String, Text, DateTime, func
from app.db.session import Base


class Config(Base):
    """
    Модель для налаштувань системи
    """
    __tablename__ = "config"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Config(key='{self.key}')>"
