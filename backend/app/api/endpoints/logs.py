from fastapi import APIRouter, Query
from typing import Optional, List
from datetime import datetime
import redis
import json
import logging

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Redis клієнт
redis_client = redis.from_url(settings.REDIS_URL)

# Ключ для зберігання логів в Redis
LOGS_KEY = "app:logs"
MAX_LOGS = 500  # Максимальна кількість логів


def add_log(level: str, message: str, domain: str = None, extra: dict = None):
    """
    Додати лог запис в Redis (викликається з інших модулів)
    """
    try:
        log_entry = {
            "id": int(datetime.utcnow().timestamp() * 1000),
            "timestamp": datetime.utcnow().isoformat(),
            "level": level.upper(),
            "message": message,
            "domain": domain,
            "extra": extra or {}
        }
        
        # Додаємо в список (зліва)
        redis_client.lpush(LOGS_KEY, json.dumps(log_entry))
        
        # Обрізаємо до MAX_LOGS
        redis_client.ltrim(LOGS_KEY, 0, MAX_LOGS - 1)
        
    except Exception as e:
        logger.error(f"Помилка додавання логу в Redis: {e}")


@router.get("")
async def get_logs(
    limit: int = Query(100, ge=1, le=500, description="Кількість логів"),
    level: Optional[str] = Query(None, description="Фільтр за рівнем (INFO, ERROR, WARNING, DEBUG)"),
    domain: Optional[str] = Query(None, description="Фільтр за доменом"),
    since: Optional[str] = Query(None, description="Логи після цього timestamp (ISO format)")
):
    """
    Отримати логи парсингу
    """
    try:
        # Отримуємо логи з Redis
        raw_logs = redis_client.lrange(LOGS_KEY, 0, limit - 1)
        
        logs = []
        for raw in raw_logs:
            try:
                log = json.loads(raw.decode())
                
                # Фільтрація за рівнем
                if level and log.get("level") != level.upper():
                    continue
                
                # Фільтрація за доменом
                if domain and log.get("domain") != domain:
                    continue
                
                # Фільтрація за часом
                if since:
                    log_time = datetime.fromisoformat(log.get("timestamp", ""))
                    since_time = datetime.fromisoformat(since)
                    if log_time <= since_time:
                        continue
                
                logs.append(log)
                
            except (json.JSONDecodeError, ValueError):
                continue
        
        return {
            "success": True,
            "count": len(logs),
            "logs": logs
        }
        
    except Exception as e:
        logger.error(f"Помилка отримання логів: {e}")
        return {
            "success": False,
            "count": 0,
            "logs": [],
            "error": str(e)
        }


@router.delete("")
async def clear_logs():
    """
    Очистити всі логи
    """
    try:
        redis_client.delete(LOGS_KEY)
        return {
            "success": True,
            "message": "Логи очищено"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/stats")
async def get_logs_stats():
    """
    Статистика логів
    """
    try:
        total = redis_client.llen(LOGS_KEY)
        
        # Підраховуємо по рівнях
        raw_logs = redis_client.lrange(LOGS_KEY, 0, -1)
        stats = {"INFO": 0, "ERROR": 0, "WARNING": 0, "DEBUG": 0}
        
        for raw in raw_logs:
            try:
                log = json.loads(raw.decode())
                level = log.get("level", "INFO")
                if level in stats:
                    stats[level] += 1
            except:
                continue
        
        return {
            "success": True,
            "total": total,
            "by_level": stats
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
