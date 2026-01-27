from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.config import (
    ConfigResponse,
    FullConfigUpdate,
    UpdateApiUrlRequest,
    UpdateGeminiKeyRequest,
    UpdatePromptRequest,
    UpdateWebhookRequest,
    UpdateProxyRequest,
    ConfigUpdateResponse
)
from app.core.config import settings
import redis
import json

router = APIRouter()

# Redis клієнт для збереження конфігурації
redis_client = redis.from_url(settings.REDIS_URL)


def _redis_str(key: str, default: str = "") -> str:
    raw = redis_client.get(key)
    return raw.decode() if raw else default


def _redis_int(key: str, default: int) -> int:
    raw = redis_client.get(key)
    if not raw:
        return default
    try:
        return int(raw.decode())
    except ValueError:
        return default


@router.get("", response_model=ConfigResponse)
async def get_config(db: Session = Depends(get_db)):
    """
    Отримати всі налаштування (читаємо з Redis, fallback на settings).
    Формат полів під фронт: domains_api_url, gemini_api_key, gemini_prompt тощо.
    """
    return ConfigResponse(
        domains_api_url=_redis_str("config:api_url") or settings.DOMAINS_API_URL,
        gemini_api_key="",  # Не повертаємо ключ; фронт при збереженні відправить його знов
        gemini_prompt=_redis_str("config:prompt"),
        webhook_url=_redis_str("config:webhook_url") or settings.WEBHOOK_URL,
        webhook_token="",
        proxy_host=_redis_str("config:proxy_host") or settings.PROXY_HOST,
        proxy_http_port=_redis_int("config:proxy_http_port", settings.PROXY_HTTP_PORT),
        proxy_socks_port=_redis_int("config:proxy_socks_port", settings.PROXY_SOCKS_PORT),
        proxy_login=_redis_str("config:proxy_login") or settings.PROXY_LOGIN,
        proxy_password="",
        scraping_timeout=settings.SCRAPING_TIMEOUT,
        celery_workers=settings.CELERY_WORKER_CONCURRENCY
    )


@router.put("", response_model=ConfigUpdateResponse)
async def update_config_full(body: FullConfigUpdate, db: Session = Depends(get_db)):
    """
    Зберегти всю конфігурацію з фронту (один запит).
    Фронт викликає PUT /config з об'єктом { domains_api_url, gemini_api_key, ... }.
    """
    if body.domains_api_url is not None:
        redis_client.set("config:api_url", body.domains_api_url or "")
    # Ключ/токен/пароль оновлюємо лише якщо передали непусте значення (не "***" і не порожнє), щоб не затерти при збереженні форми
    if body.gemini_api_key and body.gemini_api_key.strip() and body.gemini_api_key.strip() != "***":
        redis_client.set("config:gemini_key", body.gemini_api_key.strip())
    if body.gemini_prompt is not None:
        redis_client.set("config:prompt", body.gemini_prompt or "")
    if body.webhook_url is not None:
        redis_client.set("config:webhook_url", body.webhook_url or "")
    if body.webhook_token is not None and (body.webhook_token.strip() not in ("", "***") if body.webhook_token else False):
        redis_client.set("config:webhook_token", body.webhook_token.strip())
    if body.proxy_host is not None or body.proxy_http_port is not None or body.proxy_socks_port is not None or body.proxy_login is not None or body.proxy_password is not None:
        ph = body.proxy_host if body.proxy_host is not None else _redis_str("config:proxy_host") or settings.PROXY_HOST
        pport = body.proxy_http_port if body.proxy_http_port is not None else _redis_int("config:proxy_http_port", settings.PROXY_HTTP_PORT)
        psport = body.proxy_socks_port if body.proxy_socks_port is not None else _redis_int("config:proxy_socks_port", settings.PROXY_SOCKS_PORT)
        plogin = body.proxy_login if body.proxy_login is not None else (_redis_str("config:proxy_login") or settings.PROXY_LOGIN)
        _pass = body.proxy_password
        if _pass is None or (isinstance(_pass, str) and _pass.strip() in ("", "***")):
            _pass = _redis_str("config:proxy_password") or settings.PROXY_PASSWORD
        ppass = _pass or ""
        redis_client.set("config:proxy", json.dumps({"host": ph or "", "http_port": pport, "socks_port": psport, "login": plogin or "", "password": ppass or ""}))
        redis_client.set("config:proxy_host", ph or "")
        redis_client.set("config:proxy_http_port", str(pport))
        redis_client.set("config:proxy_socks_port", str(psport))
        redis_client.set("config:proxy_login", plogin or "")
        redis_client.set("config:proxy_password", ppass or "")
    return ConfigUpdateResponse(success=True, message="Конфігурацію збережено")


CONFIG_KEYS = (
    "config:api_url", "config:gemini_key", "config:prompt",
    "config:webhook_url", "config:webhook_token",
    "config:proxy", "config:proxy_host", "config:proxy_http_port",
    "config:proxy_socks_port", "config:proxy_login", "config:proxy_password",
)


@router.post("/reset", response_model=ConfigUpdateResponse)
async def reset_config(db: Session = Depends(get_db)):
    """Скинути збережену конфігурацію в Redis (значення знову беруться з .env / дефолтів)."""
    for key in CONFIG_KEYS:
        try:
            redis_client.delete(key)
        except Exception:
            pass
    return ConfigUpdateResponse(success=True, message="Конфігурацію скинуто до дефолтних значень")


@router.post("/test", response_model=ConfigUpdateResponse)
async def test_config(db: Session = Depends(get_db)):
    """Перевірка з’єднання / валідності конфігу (заглушка)."""
    return ConfigUpdateResponse(success=True, message="OK")


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
    Налаштувати proxy сервер.
    Зберігаємо в config:proxy (JSON) та окремо config:proxy_* — parsing читає ці ключі.
    """
    import json
    proxy_config = {
        "host": request.proxy_host,
        "http_port": request.proxy_http_port,
        "socks_port": request.proxy_socks_port,
        "login": request.proxy_login,
        "password": request.proxy_password
    }
    redis_client.set("config:proxy", json.dumps(proxy_config))
    redis_client.set("config:proxy_host", request.proxy_host or "")
    redis_client.set("config:proxy_http_port", str(request.proxy_http_port))
    redis_client.set("config:proxy_socks_port", str(request.proxy_socks_port))
    redis_client.set("config:proxy_login", request.proxy_login or "")
    redis_client.set("config:proxy_password", request.proxy_password or "")

    return ConfigUpdateResponse(
        success=True,
        message="Proxy налаштування успішно оновлено"
    )
