# База даних PostgreSQL

## Структура таблиць

### 1. domains
Список доменів для парсингу
- `id` - первинний ключ
- `domain` - назва домену (унікальна)
- `last_scraped_at` - дата останнього парсингу
- `scraping_status` - статус (pending, running, completed, failed)
- `error_count` - кількість помилок
- `created_at`, `updated_at` - дати створення/оновлення

### 2. scraping_sessions
Історія запусків парсингу
- `id` - первинний ключ
- `started_at`, `completed_at` - час початку/завершення
- `total_domains` - всього доменів в сесії
- `processed_domains`, `successful_domains`, `failed_domains` - статистика
- `status` - статус сесії (running, completed, failed)

### 3. scraped_deals
Зібрані акції/промокоди
- `id` - первинний ключ
- `session_id` - посилання на сесію
- `domain` - домен звідки отримано
- `deal_data` - JSONB з повними даними DealSchema
- `webhook_sent` - чи відправлено в webhook
- `webhook_sent_at` - дата відправки
- `created_at` - дата створення

### 4. config
Налаштування системи
- `key` - ключ налаштування (первинний ключ)
- `value` - значення (TEXT)
- `updated_at` - дата оновлення

### 5. cron_jobs
Налаштування cron задач
- `id` - первинний ключ
- `name` - назва задачі (унікальна)
- `cron_expression` - cron вираз
- `job_type` - тип (full_scraping, partial_scraping)
- `batch_size` - розмір пачки для partial_scraping
- `enabled` - чи активна задача
- `last_run_at` - дата останнього запуску
- `created_at`, `updated_at` - дати створення/оновлення

## Міграції

### Застосувати міграції

```bash
cd backend
alembic upgrade head
```

### Створити нову міграцію

```bash
alembic revision --autogenerate -m "description"
```

### Відкотити останню міграцію

```bash
alembic downgrade -1
```

### Переглянути історію міграцій

```bash
alembic history
```

### Переглянути поточну версію БД

```bash
alembic current
```

## CRUD операції

Всі CRUD операції доступні в `app/db/crud.py`:

```python
from app.db import crud
from app.api.deps import get_db

# Domains
domain = crud.create_domain(db, "example.com")
domains = crud.get_domains(db, skip=0, limit=100)
crud.update_domain_status(db, domain.id, "completed")

# Scraping Sessions
session = crud.create_scraping_session(db, total_domains=10)
crud.update_scraping_session(db, session.id, processed=5, successful=4, failed=1)

# Scraped Deals
deal = crud.create_scraped_deal(db, session.id, "example.com", deal_data)
deals = crud.get_scraped_deals(db, session_id=session.id)
crud.mark_deal_webhook_sent(db, deal.id)

# Config
crud.set_config(db, "gemini_api_key", "AIzaSy...")
config = crud.get_config(db, "gemini_api_key")

# Cron Jobs
job = crud.create_cron_job(db, "daily_scraping", "0 0 * * *", "full_scraping")
jobs = crud.get_cron_jobs(db, enabled_only=True)
crud.update_cron_job(db, job.id, enabled=False)
```

## Підключення до БД

```python
from app.db.session import SessionLocal

# Створити сесію
db = SessionLocal()

try:
    # Робота з БД
    pass
finally:
    db.close()
```

Або використовуючи dependency injection в FastAPI:

```python
from fastapi import Depends
from app.api.deps import get_db

@router.get("/")
def read_items(db: Session = Depends(get_db)):
    items = crud.get_items(db)
    return items
```

## Docker

База даних автоматично створюється при запуску через Docker Compose:

```bash
docker-compose up -d postgres
```

Дані зберігаються в volume `postgres_data`.
