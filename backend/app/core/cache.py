"""
Redis кешування для HTML контенту

Зберігає завантажений HTML в Redis на 1 годину для оптимізації продуктивності
"""
import redis.asyncio as redis
import json
import hashlib
from typing import Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Redis кеш для зберігання HTML контенту
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.ttl = 3600  # 1 година в секундах
        
    async def connect(self):
        """Підключитися до Redis"""
        try:
            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("✓ Підключено до Redis кешу")
        except Exception as e:
            logger.error(f"✗ Помилка підключення до Redis: {e}")
            self.redis_client = None
    
    async def disconnect(self):
        """Відключитися від Redis"""
        if self.redis_client:
            await self.redis_client.close()
    
    def _make_key(self, domain: str) -> str:
        """Створити ключ для кешування"""
        # Використовуємо hash для коротшого ключа
        domain_hash = hashlib.md5(domain.encode()).hexdigest()
        return f"html_cache:{domain_hash}"
    
    async def get_html(self, domain: str) -> Optional[dict]:
        """
        Отримати HTML з кешу
        
        Args:
            domain: Домен сайту
            
        Returns:
            dict з html, title, text або None якщо не знайдено
        """
        if not self.redis_client:
            return None
            
        try:
            key = self._make_key(domain)
            cached = await self.redis_client.get(key)
            
            if cached:
                logger.info(f"✓ Кеш HIT: {domain}")
                return json.loads(cached)
            else:
                logger.debug(f"Кеш MISS: {domain}")
                return None
                
        except Exception as e:
            logger.error(f"Помилка читання з кешу: {e}")
            return None
    
    async def set_html(self, domain: str, html_data: dict) -> bool:
        """
        Зберегти HTML в кеш
        
        Args:
            domain: Домен сайту
            html_data: dict з html, title, text та іншими даними
            
        Returns:
            True якщо успішно збережено
        """
        if not self.redis_client:
            return False
            
        try:
            key = self._make_key(domain)
            value = json.dumps(html_data, ensure_ascii=False)
            
            await self.redis_client.setex(key, self.ttl, value)
            logger.info(f"✓ Збережено в кеш: {domain} (TTL: {self.ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"Помилка запису в кеш: {e}")
            return False
    
    async def delete_html(self, domain: str) -> bool:
        """Видалити HTML з кешу"""
        if not self.redis_client:
            return False
            
        try:
            key = self._make_key(domain)
            await self.redis_client.delete(key)
            logger.info(f"✓ Видалено з кешу: {domain}")
            return True
        except Exception as e:
            logger.error(f"Помилка видалення з кешу: {e}")
            return False
    
    async def clear_all(self) -> bool:
        """Очистити весь кеш HTML"""
        if not self.redis_client:
            return False
            
        try:
            # Знайти всі ключі з префіксом html_cache:
            keys = []
            async for key in self.redis_client.scan_iter(match="html_cache:*"):
                keys.append(key)
            
            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"✓ Очищено кеш: {len(keys)} записів")
            
            return True
        except Exception as e:
            logger.error(f"Помилка очищення кешу: {e}")
            return False
    
    async def get_cache_stats(self) -> dict:
        """Отримати статистику кешу"""
        if not self.redis_client:
            return {"error": "Redis не підключено"}
        
        try:
            # Підрахувати кількість ключів
            count = 0
            async for _ in self.redis_client.scan_iter(match="html_cache:*"):
                count += 1
            
            # Отримати info
            info = await self.redis_client.info()
            
            return {
                "cached_pages": count,
                "ttl_seconds": self.ttl,
                "redis_memory_used": info.get("used_memory_human", "N/A"),
                "redis_connected_clients": info.get("connected_clients", 0)
            }
        except Exception as e:
            logger.error(f"Помилка отримання статистики: {e}")
            return {"error": str(e)}


# Глобальний instance кешу
_cache_instance: Optional[RedisCache] = None


async def get_cache() -> RedisCache:
    """Отримати instance Redis кешу"""
    global _cache_instance
    
    if _cache_instance is None:
        _cache_instance = RedisCache()
        await _cache_instance.connect()
    
    return _cache_instance
