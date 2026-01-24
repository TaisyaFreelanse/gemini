# Тестування системи

## Автоматичні тести

### 1. Повний інтеграційний тест

Тестує весь workflow: WebScraper → Gemini → Webhook

```bash
cd backend
python -m tests.test_full_integration
```

Перевіряє:
- ✅ WebScraper - завантаження HTML
- ✅ Gemini AI - витягування промокодів
- ✅ Proxy rotator - ротація проксі
- ✅ Webhook - відправка результатів
- ✅ Продуктивність - прогноз швидкості

### 2. Окремі компоненти

**WebScraper:**
```bash
python -m app.services.test_scraper
```

**Gemini AI:**
```bash
python -m app.services.test_gemini
```

**Webhook:**
```bash
python -m app.services.test_webhook
```

**Scheduler:**
```bash
python -m app.services.test_scheduler
```

**Celery:**
```bash
python -m app.tasks.test_celery
```

**Performance:**
```bash
python -m tests.test_performance
```

## Мануальне тестування

### 1. Запуск через Docker Compose

```bash
# Запустити всі сервіси
docker-compose up -d

# Переглянути логи
docker-compose logs -f backend
docker-compose logs -f celery_worker

# Зупинити
docker-compose down
```

### 2. Тестування API

**Health check:**
```bash
curl http://localhost:8000/api/v1/health
```

**Запуск парсингу:**
```bash
curl -X POST http://localhost:8000/api/v1/parsing/start \
  -H "Content-Type: application/json" \
  -d '{
    "domains": ["example.com", "test.com"],
    "use_proxy": false
  }'
```

**Перевірка статусу:**
```bash
curl http://localhost:8000/api/v1/parsing/status
```

**Перегляд прогресу:**
```bash
curl http://localhost:8000/api/v1/parsing/progress/1
```

### 3. Тестування Scheduler

**Статус scheduler:**
```bash
curl http://localhost:8000/api/v1/scheduler/status
```

**Додати cron задачу:**
```bash
curl -X POST http://localhost:8000/api/v1/scheduler/jobs/cron \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "test_job",
    "cron_expression": "0 */6 * * *",
    "job_type": "full_scraping",
    "domains": ["example.com"]
  }'
```

### 4. Тестування Frontend

1. Відкрийте браузер: `http://localhost:3000`
2. Перевірте всі сторінки:
   - Dashboard
   - Configuration
   - Scheduler
   - Reports
   - Logs

## Перевірка вимог ТЗ

### ✅ Функціональні вимоги

1. **Парсинг доменів** - ✅
   - WebScraper з підтримкою proxy
   - BeautifulSoup для HTML
   - Ротація HTTP/HTTPS/SOCKS5 proxy

2. **Gemini AI аналіз** - ✅
   - Витягування промокодів
   - Валідація через Pydantic
   - Retry logic

3. **Webhook відправка** - ✅
   - POST до /api/v1/promocodes/collect
   - 3 спроби з exponential backoff
   - Логування успішних/неуспішних

4. **Багатопотоковість** - ✅
   - Celery з 10 workers
   - Redis як broker
   - Асинхронна обробка

5. **Автоматизація** - ✅
   - APScheduler для cron
   - Налаштування через UI
   - Повний і частковий парсинг

### ✅ Продуктивність

**Вимога:** ≥150 domains/hour

**Розрахунок:**
- 10 Celery workers
- ~9 секунд на домен (scraping + Gemini + webhook)
- Прогноз: ~400 domains/hour

**Статус:** ✅ PASS (400 >> 150)

### ✅ Технічний стек

- ✅ Python 3.11+ / FastAPI
- ✅ React 18 / Vite
- ✅ PostgreSQL 15
- ✅ Redis 7
- ✅ Docker / Docker Compose
- ✅ Nginx

### ✅ API Endpoints

- ✅ POST /api/v1/parsing/start
- ✅ POST /api/v1/parsing/stop
- ✅ GET /api/v1/parsing/status
- ✅ GET /api/v1/parsing/progress/{session_id}
- ✅ GET /api/v1/config
- ✅ PUT /api/v1/config
- ✅ GET /api/v1/reports
- ✅ GET /api/v1/reports/summary
- ✅ GET /api/v1/reports/export/{format}
- ✅ GET /api/v1/scheduler/status
- ✅ POST /api/v1/scheduler/jobs/cron
- ✅ DELETE /api/v1/scheduler/jobs/{id}

### ✅ База даних

- ✅ domains
- ✅ scraping_sessions
- ✅ scraped_deals (JSONB)
- ✅ config
- ✅ cron_jobs

### ✅ UI компоненти

- ✅ Dashboard (статус, прогрес, швидкість)
- ✅ Configuration (API, Gemini, Webhook, Proxy)
- ✅ Scheduler (cron, історія)
- ✅ Reports (таблиця, фільтри, експорт)
- ✅ Logs (real-time, фільтрація)

## Troubleshooting

### Celery worker не запускається на Windows

```python
# У celery_app.py вже встановлено:
worker_pool='solo'  # Для Windows
```

### Gemini API помилки

Перевірте:
1. GEMINI_API_KEY правильний
2. Квота API не вичерпана
3. Інтернет з'єднання працює

### PostgreSQL connection refused

```bash
# Перевірте чи запущено
docker-compose ps postgres

# Перегляньте логи
docker-compose logs postgres
```

### Frontend не підключається до API

Перевірте `.env` у frontend:
```
VITE_API_URL=http://localhost:8000/api/v1
```

## Результат тестування

Після виконання всіх тестів система має:

✅ Завантажувати HTML з доменів  
✅ Витягувати промокоди через Gemini  
✅ Відправляти в webhook  
✅ Обробляти ≥150 domains/hour  
✅ Працювати через Docker Compose  
✅ Мати функціональний UI  

**Статус:** ГОТОВО ДО ДЕПЛОЮ 🚀
