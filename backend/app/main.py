from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.rate_limiter import rate_limit_middleware

app = FastAPI(
    title="Web Scraper Gemini API",
    description="API для парсингу сайтів з промокодами через Gemini AI",
    version="1.0.0"
)

# CORS: with allow_credentials=True, "*" is invalid — use explicit origins
import os

_CORS_ORIGINS = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    # Render domains
    "https://gemini-scraper-frontend.onrender.com",
    "https://gemini-scraper-backend.onrender.com",
]

# Add custom CORS origin from environment if set
_extra_cors = os.getenv("CORS_ORIGINS", "")
if _extra_cors:
    _CORS_ORIGINS.extend([origin.strip() for origin in _extra_cors.split(",") if origin.strip()])
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Rate limiting middleware (100 req/min)
app.middleware("http")(rate_limit_middleware)

@app.get("/")
async def root():
    return {"message": "Web Scraper Gemini API"}

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "web-scraper-gemini"
    }

# Підключаємо роутери
from app.api.endpoints import parsing, config, reports, scheduler, cache, mock_domains, logs

app.include_router(parsing.router, prefix="/api/v1/parsing", tags=["Parsing"])
app.include_router(config.router, prefix="/api/v1/config", tags=["Configuration"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(scheduler.router, prefix="/api/v1/scheduler", tags=["Scheduler"])
app.include_router(cache.router, prefix="/api/v1/cache", tags=["Cache"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["Logs"])
app.include_router(mock_domains.router, prefix="/api/v1", tags=["Mock"])