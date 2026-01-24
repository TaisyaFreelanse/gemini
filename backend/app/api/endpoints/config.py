from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.config import (
    ConfigResponse,
    UpdateApiUrlRequest,
    UpdateGeminiKeyRequest,
    UpdatePromptRequest,
    UpdateWebhookRequest,
    UpdateProxyRequest,
    ConfigUpdateResponse
)
from app.core.config import settings
import redis

router = APIRouter()

# Redis клієнт для збереження конфігурації
redis_client = redis.from_url(settings.REDIS_URL)


@router.get("", response_model=ConfigResponse)
async def get_config(db: Session = Depends(get_db)):
    """
    Отримати всі налаштування системи
    
    Чутливі дані (API ключі, паролі) приховуються зірочками
    """
    # TODO: Отримати конфігурацію з БД замість settings
    
    return ConfigResponse(
        api_url=settings.DOMAINS_API_URL,
        gemini_key="***",  # Приховуємо ключ
        webhook_url=settings.WEBHOOK_URL,
        webhook_token="***",  # Приховуємо токен
        proxy_host=settings.PROXY_HOST,
        proxy_http_port=settings.PROXY_HTTP_PORT,
        proxy_socks_port=settings.PROXY_SOCKS_PORT,
        proxy_login=settings.PROXY_LOGIN,
        scraping_timeout=settings.SCRAPING_TIMEOUT,
        celery_workers=settings.CELERY_WORKER_CONCURRENCY
    )


@router.put("/api-url", response_model=ConfigUpdateResponse)
async def update_api_url(
    request: UpdateApiUrlRequest,
    db: Session = Depends(get_db)
):
    """
    Змінити API URL для отримання списку доменів
    """
    # TODO: Зберегти в БД
    redis_client.set("config:api_url", request.api_url)
    
    return ConfigUpdateResponse(
        success=True,
        message="API URL успішно оновлено"
    )


@router.put("/gemini-key", response_model=ConfigUpdateResponse)
async def update_gemini_key(
    request: UpdateGeminiKeyRequest,
    db: Session = Depends(get_db)
):
    """
    Змінити Gemini API ключ
    """
    # TODO: Зберегти в БД (зашифровано)
    redis_client.set("config:gemini_key", request.api_key)
    
    return ConfigUpdateResponse(
        success=True,
        message="Gemini API ключ успішно оновлено"
    )


@router.put("/prompt", response_model=ConfigUpdateResponse)
async def update_prompt(
    request: UpdatePromptRequest,
    db: Session = Depends(get_db)
):
    """
    Оновити промпт для Gemini AI
    """
    # TODO: Зберегти в БД
    redis_client.set("config:prompt", request.prompt)
    
    return ConfigUpdateResponse(
        success=True,
        message="Промпт успішно оновлено"
    )


@router.put("/webhook", response_model=ConfigUpdateResponse)
async def update_webhook(
    request: UpdateWebhookRequest,
    db: Session = Depends(get_db)
):
    """
    Налаштувати webhook для відправки результатів
    """
    # TODO: Зберегти в БД
    redis_client.set("config:webhook_url", request.webhook_url)
    if request.webhook_token:
        redis_client.set("config:webhook_token", request.webhook_token)
    
    return ConfigUpdateResponse(
        success=True,
        message="Webhook налаштування успішно оновлено"
    )


@router.put("/proxy", response_model=ConfigUpdateResponse)
async def update_proxy(
    request: UpdateProxyRequest,
    db: Session = Depends(get_db)
):
    """
    Налаштувати proxy сервер
    """
    # TODO: Зберегти в БД (пароль зашифровано)
    proxy_config = {
        "host": request.proxy_host,
        "http_port": request.proxy_http_port,
        "socks_port": request.proxy_socks_port,
        "login": request.proxy_login,
        "password": request.proxy_password
    }
    
    import json
    redis_client.set("config:proxy", json.dumps(proxy_config))
    
    return ConfigUpdateResponse(
        success=True,
        message="Proxy налаштування успішно оновлено"
    )
