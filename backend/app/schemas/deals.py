from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class DealSchema(BaseModel):
    """Схема для промокоду/акції"""
    shop: str = Field(..., max_length=200, description="Назва магазину")
    domain: str = Field(..., max_length=255, description="Домен")
    description: str = Field(..., max_length=60, description="Короткий опис акції")
    full_description: str = Field(..., max_length=160, description="Повний опис умов")
    code: str = Field(..., description="Промокод або 'Не знайдено'")
    date_start: Optional[str] = Field(None, description="Дата початку (YYYY-MM-DD HH:MM)")
    date_end: Optional[str] = Field(None, description="Дата закінчення (YYYY-MM-DD HH:MM)")
    offer_type: int = Field(..., ge=1, le=10, description="Тип акції (1-10)")
    target_url: str = Field(..., description="URL акції")
    click_url: str = Field(default="Не знайдено", description="Click URL або 'Не знайдено'")
    discount: str = Field(default="Не знайдено", description="Розмір знижки або 'Не знайдено'")
    categories: List[str] = Field(default_factory=list, description="Список ID категорій")

    @validator('description')
    def validate_description_length(cls, v):
        if len(v) > 60:
            return v[:57] + "..."
        return v
    
    @validator('full_description')
    def validate_full_description_length(cls, v):
        if len(v) > 160:
            return v[:157] + "..."
        return v
    
    @validator('categories', pre=True)
    def convert_categories(cls, v):
        """Конвертувати категорії в список рядків"""
        if isinstance(v, list):
            return [str(cat) for cat in v]
        return []

    class Config:
        json_schema_extra = {
            "example": {
                "shop": "Example Shop",
                "domain": "example.com",
                "description": "Знижка 20% на всі товари",
                "full_description": "Отримайте знижку 20% на всі товари при використанні промокоду SAVE20",
                "code": "SAVE20",
                "date_start": "2026-01-24 12:00",
                "date_end": "2026-02-24 23:59",
                "offer_type": 1,
                "target_url": "https://example.com/promo",
                "click_url": "Не знайдено",
                "discount": "20%",
                "categories": ["3", "11"]
            }
        }
