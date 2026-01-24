"""
Cache management endpoints

Керування Redis кешем для HTML контенту
"""
from fastapi import APIRouter, HTTPException
from typing import Dict
from app.core.cache import get_cache

router = APIRouter()


@router.get("/stats", response_model=Dict)
async def get_cache_stats():
    """
    Отримати статистику кешу
    
    Returns:
        - cached_pages: кількість закешованих сторінок
        - ttl_seconds: час життя кешу в секундах
        - redis_memory_used: використана пам'ять Redis
        - redis_connected_clients: підключені клієнти
    """
    try:
        cache = await get_cache()
        stats = await cache.get_cache_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка отримання статистики: {e}")


@router.delete("/clear")
async def clear_cache():
    """
    Очистити весь HTML кеш
    
    Returns:
        - success: bool
        - message: повідомлення про результат
    """
    try:
        cache = await get_cache()
        success = await cache.clear_all()
        
        if success:
            return {
                "success": True,
                "message": "Кеш успішно очищено"
            }
        else:
            raise HTTPException(status_code=500, detail="Не вдалося очистити кеш")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка очищення кешу: {e}")


@router.delete("/{domain}")
async def delete_domain_cache(domain: str):
    """
    Видалити кеш для конкретного домену
    
    Args:
        domain: Домен для видалення з кешу
    
    Returns:
        - success: bool
        - message: повідомлення про результат
    """
    try:
        cache = await get_cache()
        success = await cache.delete_html(domain)
        
        if success:
            return {
                "success": True,
                "message": f"Кеш для {domain} видалено"
            }
        else:
            return {
                "success": False,
                "message": f"Кеш для {domain} не знайдено"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка видалення кешу: {e}")
