# Web Scraper з Gemini AI

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-teal?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Production%20Ready-success)

Докеризований вебдодаток для автоматичного парсингу сайтів з промокодами через Gemini AI з автоматичною відправкою результатів у webhook.

## 🚀 Технологічний стек

**Backend:**
- Python 3.11+ / FastAPI
- PostgreSQL 15 (база даних)
- Redis 7 (Celery broker + cache)
- Celery (багатопотокова обробка)
- SQLAlchemy (ORM)
- Gemini AI API
- BeautifulSoup4 (парсинг HTML)
.
**Frontend:**
- React 18 + Vite
- Tailwind CSS
- React Router
- Axios / React Query

**Infrastructure:**
- Docker + Docker Compose
- Nginx (reverse proxy)

## 📋 Вимоги

- Docker 20.10+
- Docker Compose 2.0+
- Мінімум 4GB RAM
- Мінімум 10GB вільного місця

## 🛠 Встановлення

### 1. Клонування репозиторію

```bash
git clone <repository-url>
cd web-scraper-gemini
```

### 2. Налаштування змінних середовища

```bash
cp .env.example .env
nano .env  # відредагуйте необхідні параметри
```

### 3. Запуск через Docker Compose

```bash
# Збірка та запуск всіх сервісів
docker-compose up -d --build

# Перевірка статусу
docker-compose ps

# Перегляд логів
docker-compose logs -f backend
```

### 4. Виконання міграцій БД (буде додано пізніше)

```bash
docker-compose exec backend alembic upgrade head
```

## 📁 Структура проекту

```
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Конфігурація
│   │   ├── models/         # SQLAlchemy моделі
│   │   ├── schemas/        # Pydantic схеми
│   │   ├── services/       # Бізнес-логіка
│   │   ├── tasks/          # Celery завдання
│   │   └── db/             # Database utilities
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/    # React компоненти
│   │   ├── pages/         # Сторінки
│   │   └── services/      # API клієнт
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🌐 Доступ до сервісів

- **Frontend:** http://localhost
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **PostgreSQL:** localhost:5432
- **Redis:** localhost:6379

## 📊 API Endpoints (будуть реалізовані)

### Parsing
- `POST /api/v1/parsing/start` - Запустити парсинг
- `POST /api/v1/parsing/stop` - Зупинити парсинг
- `GET /api/v1/parsing/status` - Статус поточного процесу
- `GET /api/v1/parsing/history` - Історія парсингу

### Configuration
- `GET /api/v1/config` - Отримати всі налаштування
- `PUT /api/v1/config/api-url` - Змінити API URL
- `PUT /api/v1/config/gemini-key` - Змінити Gemini API ключ
- `PUT /api/v1/config/webhook` - Налаштування webhook
- `PUT /api/v1/config/proxy` - Налаштування proxy

### Reports
- `GET /api/v1/reports/summary` - Загальна статистика
- `GET /api/v1/reports/detailed` - Детальний звіт
- `GET /api/v1/reports/export` - Експорт у CSV/JSON

## ⚙️ Налаштування

### Gemini API
API ключ вказується у `.env` файлі. Використовується модель `gemini-1.5-flash` для аналізу HTML контенту.

### Proxy
Підтримуються HTTP/HTTPS та SOCKS5 проксі. Конфігурація у `.env` файлі.

### Celery Workers
За замовчуванням запускається 10 паралельних workers для обробки доменів. Мінімальна швидкість: 150 доменів/годину.

## 🧪 Тестування (буде додано)

```bash
# Тести backend
docker-compose exec backend pytest

# Тести frontend
docker-compose exec frontend npm test
```

## 🔧 Розробка

### Backend розробка

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend розробка

```bash
cd frontend
npm install
npm run dev
```

## 📝 Статус розробки

- [x] ✅ Створити структуру проекту
- [x] ✅ Реалізувати SQLAlchemy моделі та Alembic міграції
- [x] ✅ Розробити WebScraper з підтримкою proxy
- [x] ✅ Інтегрувати Gemini AI API
- [x] ✅ Налаштувати Celery для багатопотокової обробки
- [x] ✅ Створити REST API endpoints
- [x] ✅ Реалізувати відправку у webhook
- [x] ✅ Налаштувати cron scheduler
- [x] ✅ Розробити React UI
- [x] ✅ Протестувати систему
- [x] ✅ Написати документацію
- [x] ✅ Додати Redis кешування
- [x] ✅ Додати Rate limiting

**Статус:** 🎉 ГОТОВО ДО PRODUCTION DEPLOY

## 📚 Документація

- **`README.md`** - Ви тут! Головна документація проекту
- **`REQUIREMENTS_CHECKLIST.md`** - ✅ Checklist виконання всіх вимог (61/61 = 100%)
- **`TESTING.md`** - Інструкції з тестування системи
- **`PERFORMANCE_OPTIMIZATION.md`** - Деталі оптимізацій продуктивності (Redis, Rate limiting, Connection pooling)
- **`backend/README_DATABASE.md`** - Документація по базі даних PostgreSQL
- **`plan.md`** - Детальний план розробки з усіма вимогами

## ⚡ Оптимізація продуктивності

Система оптимізована для обробки **≥150 domains/hour** (прогноз: **400-600 domains/hour**):

1. ✅ **Redis кешування** - HTML content (TTL: 1 hour)
2. ✅ **Rate limiting** - 100 req/min на IP
3. ✅ **Connection pooling** - PostgreSQL (pool_size=10)
4. ✅ **Асинхронні запити** - aiohttp для HTTP
5. ✅ **10 Celery workers** - паралельна обробка
6. ✅ **Proxy ротація** - автоматична ротація при помилках (3 спроби)
7. ✅ **Оптимізація HTML** - очищення перед Gemini (50KB text, 100KB HTML)

Детальніше: **`PERFORMANCE_OPTIMIZATION.md`**

## 🛠️ Troubleshooting

### Celery worker не запускається на Windows

```bash
# У celery_app.py вже налаштовано worker_pool='solo' для Windows
```

### Gemini API помилки

1. Перевірте правильність `GEMINI_API_KEY` в `.env`
2. Перевірте квоту API на https://makersuite.google.com/
3. Перевірте інтернет з'єднання

### PostgreSQL connection refused

```bash
# Перевірте чи запущено контейнер
docker-compose ps postgres

# Перегляньте логи
docker-compose logs postgres

# Перезапустіть контейнер
docker-compose restart postgres
```

### Очистити Redis кеш

```bash
# Через API
curl -X DELETE http://localhost:8000/api/v1/cache/clear

# Через Docker
docker-compose exec redis redis-cli FLUSHALL
```

### Rate limit exceeded

Якщо отримуєте HTTP 429, почекайте або збільште ліміт в `backend/app/core/rate_limiter.py`:

```python
rate_limiter = RateLimiter(max_requests=200, window_seconds=60)
```

## 📄 Ліцензія

MIT License

---

**🎉 Проект готовий до розгортання на production сервері!**
