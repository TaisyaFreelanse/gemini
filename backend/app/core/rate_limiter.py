"""
Rate Limiting для API endpoints

Обмежує кількість запитів до 100 req/min на IP адресу
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import time
from collections import defaultdict
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter на базі IP адреси
    
    Обмеження: 100 запитів на хвилину на IP
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Dict[ip_address, List[timestamp]]
        self.requests: Dict[str, list] = defaultdict(list)
        
    def _clean_old_requests(self, ip: str, current_time: float):
        """Видалити запити старші ніж window_seconds"""
        cutoff_time = current_time - self.window_seconds
        self.requests[ip] = [
            timestamp for timestamp in self.requests[ip]
            if timestamp > cutoff_time
        ]
    
    def is_allowed(self, ip: str) -> Tuple[bool, int]:
        """
        Перевірити чи дозволений запит
        
        Returns:
            (allowed: bool, remaining: int)
        """
        current_time = time.time()
        
        # Очистити старі запити
        self._clean_old_requests(ip, current_time)
        
        # Підрахувати запити за останню хвилину
        request_count = len(self.requests[ip])
        
        if request_count >= self.max_requests:
            return False, 0
        
        # Додати поточний запит
        self.requests[ip].append(current_time)
        
        remaining = self.max_requests - request_count - 1
        return True, remaining
    
    def get_reset_time(self, ip: str) -> int:
        """Отримати час (секунди) до скидання ліміту"""
        if not self.requests[ip]:
            return 0
        
        oldest_request = min(self.requests[ip])
        reset_time = oldest_request + self.window_seconds
        remaining = max(0, int(reset_time - time.time()))
        
        return remaining


# Глобальний instance rate limiter
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware для rate limiting
    
    Додає headers:
    - X-RateLimit-Limit: максимум запитів
    - X-RateLimit-Remaining: залишилось запитів
    - X-RateLimit-Reset: час до скидання (секунди)
    """
    # Отримати IP адресу
    client_ip = request.client.host if request.client else "unknown"
    
    # Пропустити health check
    if request.url.path in ["/", "/api/v1/health"]:
        return await call_next(request)
    
    # Перевірити rate limit
    allowed, remaining = rate_limiter.is_allowed(client_ip)
    
    if not allowed:
        reset_time = rate_limiter.get_reset_time(client_ip)
        
        logger.warning(
            f"Rate limit exceeded for IP: {client_ip}, "
            f"reset in {reset_time}s"
        )
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Please try again in {reset_time} seconds.",
                "retry_after": reset_time
            },
            headers={
                "X-RateLimit-Limit": str(rate_limiter.max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(reset_time)
            }
        )
    
    # Виконати запит
    response = await call_next(request)
    
    # Додати rate limit headers
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(
        rate_limiter.get_reset_time(client_ip)
    )
    
    return response


def get_rate_limiter_stats() -> dict:
    """Отримати статистику rate limiter"""
    return {
        "max_requests": rate_limiter.max_requests,
        "window_seconds": rate_limiter.window_seconds,
        "tracked_ips": len(rate_limiter.requests),
        "total_requests": sum(len(reqs) for reqs in rate_limiter.requests.values())
    }
