"""
Тестовий скрипт для перевірки Celery tasks

Запуск:
1. Запустити Redis: docker run -d -p 6379:6379 redis:7-alpine
2. Запустити Celery worker: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=10
3. Запустити цей скрипт: python -m app.tasks.test_celery
"""
from app.tasks.scraping_tasks import scrape_domain_task, start_batch_scraping, get_session_progress
import time


def test_single_domain():
    """Тест парсингу одного домену"""
    print("=" * 80)
    print("ТЕСТ 1: Парсинг одного домену")
    print("=" * 80)
    
    domain = "example.com"
    session_id = 1
    
    # Запускаємо задачу
    print(f"\n🚀 Запуск задачі для {domain}...")
    task = scrape_domain_task.delay(domain, session_id)
    
    print(f"Task ID: {task.id}")
    print("Чекаємо на результат...")
    
    # Чекаємо на результат (максимум 60 секунд)
    try:
        result = task.get(timeout=60)
        print("\n✓ Результат отримано:")
        print(f"  Success: {result.get('success')}")
        print(f"  Domain: {result.get('domain')}")
        print(f"  Deals found: {result.get('deals_count')}")
        if result.get('error'):
            print(f"  Error: {result.get('error')}")
    except Exception as e:
        print(f"\n✗ Помилка: {e}")


def test_batch_scraping():
    """Тест пакетного парсингу"""
    print("\n" + "=" * 80)
    print("ТЕСТ 2: Пакетний парсинг")
    print("=" * 80)
    
    domains = [
        "example.com",
        "test.com",
        "demo.com"
    ]
    session_id = 2
    
    print(f"\n🚀 Запуск пакетного парсингу: {len(domains)} доменів...")
    task = start_batch_scraping.delay(domains, session_id)
    
    print(f"Task ID: {task.id}")
    
    # Чекаємо на результат запуску
    try:
        batch_info = task.get(timeout=10)
        print("\n✓ Пакет запущено:")
        print(f"  Session ID: {batch_info.get('session_id')}")
        print(f"  Total domains: {batch_info.get('total_domains')}")
        print(f"  Tasks started: {len(batch_info.get('task_ids', []))}")
        
        # Перевіряємо прогрес кожні 2 секунди
        print("\n📊 Моніторинг прогресу...")
        for i in range(30):  # Максимум 60 секунд
            time.sleep(2)
            
            progress = get_session_progress.delay(session_id).get(timeout=5)
            if progress:
                total = progress.get('total', 0)
                processed = progress.get('processed', 0)
                successful = progress.get('successful', 0)
                failed = progress.get('failed', 0)
                running = progress.get('running', 0)
                
                print(f"  [{i*2}s] Processed: {processed}/{total}, "
                      f"Success: {successful}, Failed: {failed}, Running: {running}")
                
                if processed >= total:
                    print("\n✓ Всі домени оброблено!")
                    break
        
    except Exception as e:
        print(f"\n✗ Помилка: {e}")


def test_celery_status():
    """Перевірка статусу Celery"""
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Статус Celery")
    print("=" * 80)
    
    from app.tasks.celery_app import celery_app
    
    # Перевіряємо з'єднання
    try:
        stats = celery_app.control.inspect().stats()
        if stats:
            print("\n✓ Celery workers активні:")
            for worker_name, worker_stats in stats.items():
                print(f"\n  Worker: {worker_name}")
                print(f"    Pool: {worker_stats.get('pool', {}).get('implementation')}")
                print(f"    Max concurrency: {worker_stats.get('pool', {}).get('max-concurrency')}")
        else:
            print("\n⚠️ Немає активних workers")
            print("Запустіть worker: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=10")
    except Exception as e:
        print(f"\n✗ Помилка підключення до Celery: {e}")
        print("Переконайтесь що Redis запущено та worker працює")


if __name__ == "__main__":
    # Спочатку перевіряємо статус
    test_celery_status()
    
    # Запитуємо чи продовжувати тести
    print("\n" + "=" * 80)
    response = input("Запустити тести парсингу? (y/n): ")
    
    if response.lower() == 'y':
        # Тест одного домену
        test_single_domain()
        
        # Тест пакетного парсингу
        # test_batch_scraping()  # Розкоментувати для тесту
