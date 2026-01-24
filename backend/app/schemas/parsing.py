from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ScrapingStatus(str, Enum):
    """Статуси парсингу"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class ParsingStartRequest(BaseModel):
    """Запит на запуск парсингу"""
    batch_size: Optional[int] = Field(None, description="Кількість доменів для обробки (None = всі)")
    force_refresh: bool = Field(False, description="Примусово оновити всі домени")


class ParsingStartResponse(BaseModel):
    """Відповідь на запуск парсингу"""
    session_id: int
    status: str
    message: str
    total_domains: int


class ParsingStatusResponse(BaseModel):
    """Статус поточного парсингу"""
    session_id: Optional[int]
    status: ScrapingStatus
    total_domains: int
    processed_domains: int
    successful_domains: int
    failed_domains: int
    progress_percent: float
    domains_per_hour: float
    started_at: Optional[datetime]
    estimated_completion: Optional[datetime]


class ParsingHistoryItem(BaseModel):
    """Елемент історії парсингу"""
    id: int
    started_at: datetime
    completed_at: Optional[datetime]
    total_domains: int
    processed_domains: int
    successful_domains: int
    failed_domains: int
    status: str
    duration_seconds: Optional[int]

    class Config:
        from_attributes = True


class ParsingHistoryResponse(BaseModel):
    """Відповідь зі списком історії"""
    sessions: List[ParsingHistoryItem]
    total: int
