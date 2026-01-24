from pydantic import BaseModel, Field, HttpUrl
from typing import Optional


class ConfigResponse(BaseModel):
    """Відповідь з усіма налаштуваннями"""
    api_url: Optional[str] = None
    gemini_key: str = "***"  # Приховуємо ключ
    webhook_url: Optional[str] = None
    webhook_token: str = "***"  # Приховуємо токен
    proxy_host: Optional[str] = None
    proxy_http_port: int = 59100
    proxy_socks_port: int = 59101
    proxy_login: Optional[str] = None
    scraping_timeout: int = 30
    celery_workers: int = 10


class UpdateApiUrlRequest(BaseModel):
    """Запит на оновлення API URL"""
    api_url: str = Field(..., description="URL для отримання списку доменів")


class UpdateGeminiKeyRequest(BaseModel):
    """Запит на оновлення Gemini API ключа"""
    api_key: str = Field(..., min_length=20, description="Gemini API ключ")


class UpdatePromptRequest(BaseModel):
    """Запит на оновлення промпту"""
    prompt: str = Field(..., min_length=10, description="Промпт для Gemini AI")


class UpdateWebhookRequest(BaseModel):
    """Запит на оновлення webhook налаштувань"""
    webhook_url: str = Field(..., description="URL webhook для відправки результатів")
    webhook_token: Optional[str] = Field(None, description="Bearer token для автентифікації")


class UpdateProxyRequest(BaseModel):
    """Запит на оновлення proxy налаштувань"""
    proxy_host: str = Field(..., description="Proxy host")
    proxy_http_port: int = Field(59100, ge=1, le=65535)
    proxy_socks_port: int = Field(59101, ge=1, le=65535)
    proxy_login: str = Field(..., description="Proxy login")
    proxy_password: str = Field(..., description="Proxy password")


class ConfigUpdateResponse(BaseModel):
    """Відповідь на оновлення конфігурації"""
    success: bool
    message: str
