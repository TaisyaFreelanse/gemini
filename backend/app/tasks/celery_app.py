from celery import Celery
from app.core.config import settings

# Створюємо Celery app
celery_app = Celery(
    "web_scraper",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.tasks.scraping_tasks']
)

# Конфігурація Celery
celery_app.conf.update(
    # Багатопотоковість
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,  # 10 паралельних workers
    worker_prefetch_multiplier=1,  # Беремо по 1 задачі за раз для рівномірного розподілу
    
    # Часові обмеження
    task_soft_time_limit=300,  # 5 хвилин soft limit
    task_time_limit=360,  # 6 хвилин hard limit
    
    # Серіалізація
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    
    # Часова зона
    timezone='UTC',
    enable_utc=True,
    
    # Результати
    result_expires=3600,  # Результати зберігаються 1 годину
    
    # Повтори при помилках
    task_acks_late=True,  # Підтверджувати виконання після завершення
    task_reject_on_worker_lost=True,  # Повертати задачу в чергу при падінні worker
    
    # Оптимізація
    worker_pool='solo',  # Для Windows compatibility (можна змінити на 'prefork' для Linux)
    worker_max_tasks_per_child=100,  # Перезапускати worker після 100 задач
)

# Автоматичне відкриття задач
celery_app.autodiscover_tasks(['app.tasks'])
