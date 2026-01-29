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
    # Proxy: зберігаємо тільки якщо є непусте значення, щоб не перебивати .env
    if body.proxy_host is not None or body.proxy_http_port is not None or body.proxy_socks_port is not None or body.proxy_login is not None or body.proxy_password is not None:
        # Отримуємо поточні значення (з Redis, потім з .env)
        ph = body.proxy_host.strip() if body.proxy_host and body.proxy_host.strip() else None
        if ph is None:
            ph = _redis_str("config:proxy_host") or settings.PROXY_HOST or None
        
        pport = body.proxy_http_port if body.proxy_http_port is not None else _redis_int("config:proxy_http_port", settings.PROXY_HTTP_PORT)
        psport = body.proxy_socks_port if body.proxy_socks_port is not None else _redis_int("config:proxy_socks_port", settings.PROXY_SOCKS_PORT)
        
        plogin = body.proxy_login.strip() if body.proxy_login and body.proxy_login.strip() else None
        if plogin is None:
            plogin = _redis_str("config:proxy_login") or settings.PROXY_LOGIN or None
        
        _pass = body.proxy_password
        if _pass is None or (isinstance(_pass, str) and _pass.strip() in ("", "***")):
            _pass = _redis_str("config:proxy_password") or settings.PROXY_PASSWORD
        ppass = _pass.strip() if _pass else None
        
        # Зберігаємо тільки якщо є хоча б host
        if ph:
            redis_client.set("config:proxy", json.dumps({"host": ph, "http_port": pport, "socks_port": psport, "login": plogin or "", "password": ppass or ""}))
            redis_client.set("config:proxy_host", ph)
            redis_client.set("config:proxy_http_port", str(pport))
            redis_client.set("config:proxy_socks_port", str(psport))
            if plogin:
                redis_client.set("config:proxy_login", plogin)
            if ppass:
                redis_client.set("config:proxy_password", ppass)
        else:
            # Якщо host пустий, видаляємо proxy конфіг з Redis (буде використано .env)
            for k in ("config:proxy", "config:proxy_host", "config:proxy_http_port", 
                      "config:proxy_socks_port", "config:proxy_login", "config:proxy_password"):
                redis_client.delete(k)
    return ConfigUpdateResponse(success=True, message="Конфігурацію збережено")


CONFIG_KEYS = (
    "config:api_url", "config:gemini_key", "config:prompt",
    "config:webhook_url", "config:webhook_token",
    "config:proxy", "config:proxy_host", "config:proxy_http_port",
    "config:proxy_socks_port", "config:proxy_login", "config:proxy_password",
    "config:domains", "config:domains_count",
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


@router.get("/effective")
async def get_effective_config(db: Session = Depends(get_db)):
    """
    Отримати ефективну конфігурацію (що реально буде використовуватися).
    Показує звідки взято кожне значення: Redis чи .env
    """
    result = {}
    
    # Proxy
    redis_proxy_host = _redis_str("config:proxy_host")
    result["proxy"] = {
        "host": {
            "redis": redis_proxy_host or "(empty)",
            "env": settings.PROXY_HOST or "(empty)",
            "effective": redis_proxy_host or settings.PROXY_HOST or "(none)",
            "source": "redis" if redis_proxy_host else "env"
        },
        "http_port": {
            "redis": _redis_int("config:proxy_http_port", 0) or "(empty)",
            "env": settings.PROXY_HTTP_PORT,
            "effective": _redis_int("config:proxy_http_port", settings.PROXY_HTTP_PORT)
        },
        "login": {
            "redis": _redis_str("config:proxy_login") or "(empty)",
            "env": settings.PROXY_LOGIN or "(empty)",
            "effective": _redis_str("config:proxy_login") or settings.PROXY_LOGIN or "(none)"
        }
    }
    
    # Gemini
    result["gemini"] = {
        "key_set_in_redis": bool(_redis_str("config:gemini_key")),
        "key_set_in_env": bool(settings.GEMINI_API_KEY),
        "model": settings.GEMINI_MODEL
    }
    
    # Webhook
    result["webhook"] = {
        "url_redis": _redis_str("config:webhook_url") or "(empty)",
        "url_env": settings.WEBHOOK_URL or "(empty)",
        "effective": _redis_str("config:webhook_url") or settings.WEBHOOK_URL or "(none)"
    }
    
    # Domains
    domains_raw = redis_client.get("config:domains")
    domains_count = 0
    if domains_raw:
        try:
            domains_count = len(json.loads(domains_raw.decode()))
        except:
            pass
    result["domains"] = {
        "uploaded_count": domains_count
    }
    
    return result


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


# ========== Domains Management ==========

@router.post("/domains/upload")
async def upload_domains(data: dict, db: Session = Depends(get_db)):
    """
    Завантажити домени з JSON у форматі:
    {
        "status": true,
        "message": "",
        "data": ["domain1.com", "domain2.com", ...]
    }
    або просто масив: ["domain1.com", "domain2.com", ...]
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Підтримуємо обидва формати
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                domains = data["data"]
            elif "domains" in data and isinstance(data["domains"], list):
                domains = data["domains"]
            else:
                # Може бути просто масив в тілі
                raise HTTPException(
                    status_code=400, 
                    detail="Невірний формат. Очікується {data: [...]} або {domains: [...]}"
                )
        elif isinstance(data, list):
            domains = data
        else:
            raise HTTPException(status_code=400, detail="Невірний формат даних")
        
        # Фільтруємо та валідуємо домени
        valid_domains = []
        for d in domains:
            if isinstance(d, str) and d.strip():
                domain = d.strip().lower()
                # Видаляємо протокол якщо є
                if domain.startswith("https://"):
                    domain = domain[8:]
                elif domain.startswith("http://"):
                    domain = domain[7:]
                # Видаляємо trailing slash
                domain = domain.rstrip("/")
                if domain and "." in domain:
                    valid_domains.append(domain)
        
        # Видаляємо дублікати
        valid_domains = list(dict.fromkeys(valid_domains))
        
        if not valid_domains:
            raise HTTPException(status_code=400, detail="Не знайдено валідних доменів")
        
        # Зберігаємо в Redis
        redis_client.set("config:domains", json.dumps(valid_domains))
        redis_client.set("config:domains_count", str(len(valid_domains)))
        
        logger.info(f"Завантажено {len(valid_domains)} доменів")
        
        return {
            "success": True,
            "message": f"Успішно завантажено {len(valid_domains)} доменів",
            "count": len(valid_domains),
            "domains": valid_domains[:20],  # Показуємо перші 20 для прев'ю
            "total": len(valid_domains)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка завантаження доменів: {e}")
        raise HTTPException(status_code=400, detail=f"Помилка обробки: {str(e)}")


@router.get("/domains")
async def get_domains(db: Session = Depends(get_db)):
    """
    Отримати список завантажених доменів
    """
    try:
        domains_raw = redis_client.get("config:domains")
        if domains_raw:
            domains = json.loads(domains_raw.decode())
            return {
                "success": True,
                "count": len(domains),
                "domains": domains
            }
        return {
            "success": True,
            "count": 0,
            "domains": []
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "domains": [],
            "error": str(e)
        }


@router.delete("/domains")
async def clear_domains(db: Session = Depends(get_db)):
    """
    Очистити список завантажених доменів
    """
    redis_client.delete("config:domains")
    redis_client.delete("config:domains_count")
    return {
        "success": True,
        "message": "Список доменів очищено"
    }
