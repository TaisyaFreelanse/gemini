from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Web Scraper Gemini"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Gemini AI
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MAX_CONTENT_LENGTH: int = 80000  # max chars HTML/email перед відправкою (0 = без обрізки)
    
    # Domains API
    DOMAINS_API_URL: Optional[str] = None
    
    # Webhook
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_TOKEN: Optional[str] = None
    
    # Proxy
    PROXY_HOST: Optional[str] = None
    PROXY_HTTP_PORT: int = 59100
    PROXY_SOCKS_PORT: int = 59101
    PROXY_LOGIN: Optional[str] = None
    PROXY_PASSWORD: Optional[str] = None
    
    # Scraping
    SCRAPING_TIMEOUT: int = 30
    SCRAPING_MAX_RETRIES: int = 3
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    CELERY_WORKER_CONCURRENCY: int = 10
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Якщо Celery URLs не вказані, використовуємо REDIS_URL
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
