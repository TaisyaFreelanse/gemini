"""
Тестовий скрипт для перевірки SchedulerService

Запуск: python -m app.services.test_scheduler
"""
import asyncio
import time
from datetime import datetime
from app.services.scheduler import get_scheduler, init_default_jobs


def test_job_callback(job_name: str):
    """Тестова функція для виконання в scheduler"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Задача '{job_name}' виконана!")


async def test_basic_scheduler():
    """Тест базових функцій scheduler"""
    print("=" * 80)
    print("ТЕСТ 1: Базові функції scheduler")
    print("=" * 80)
    
    scheduler = get_scheduler()
    
    # Тест 1.1: Запуск scheduler
    print("\n1.1 Запуск scheduler...")
    scheduler.start()
    assert scheduler.is_running(), "Scheduler має бути запущений"
    print("✓ Scheduler запущено")
    
    # Тест 1.2: Додавання interval задачі
    print("\n1.2 Додавання interval задачі (кожні 5 секунд)...")
    job = scheduler.add_interval_job(
        job_id="test_interval",
        func=test_job_callback,
        interval_minutes=0.0833,  # ~5 секунд
        args=("interval_test",),
        description="Тестова interval задача"
    )
    assert job is not None, "Задача має бути створена"
    print(f"✓ Задача додана, наступний запуск: {job.next_run_time}")
    
    # Тест 1.3: Список задач
    print("\n1.3 Отримання списку задач...")
    jobs = scheduler.get_all_jobs()
    print(f"✓ Знайдено задач: {len(jobs)}")
    for job_info in jobs:
        print(f"   - {job_info['id']}: {job_info['next_run_time']}")
    
    # Тест 1.4: Чекаємо виконання
    print("\n1.4 Чекаємо виконання задачі (10 секунд)...")
    await asyncio.sleep(10)
    
    # Тест 1.5: Видалення задачі
    print("\n1.5 Видалення задачі...")
    success = scheduler.remove_job("test_interval")
    assert success, "Задача має бути видалена"
    print("✓ Задача видалена")


async def test_cron_expressions():
    """Тест cron виразів"""
    print("\n" + "=" * 80)
    print("ТЕСТ 2: Cron вирази")
    print("=" * 80)
    
    scheduler = get_scheduler()
    
    # Приклади cron виразів
    cron_tests = [
        ("every_6_hours", "0 */6 * * *", "Кожні 6 годин"),
        ("daily_midnight", "0 0 * * *", "Щодня о 00:00"),
        ("every_30_min", "*/30 * * * *", "Кожні 30 хвилин"),
        ("monday_9am", "0 9 * * 1", "Понеділок о 9:00"),
    ]
    
    print("\nДодавання cron задач...")
    for job_id, cron_expr, description in cron_tests:
        job = scheduler.add_cron_job(
            job_id=job_id,
            func=test_job_callback,
            cron_expression=cron_expr,
            args=(job_id,),
            description=description
        )
        
        if job:
            print(f"✓ {description}: наступний запуск {job.next_run_time}")
        else:
            print(f"✗ Помилка додавання: {description}")
    
    # Список всіх задач
    jobs = scheduler.get_all_jobs()
    print(f"\n✓ Всього активних задач: {len(jobs)}")


async def test_job_management():
    """Тест управління задачами"""
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Управління задачами (пауза/відновлення)")
    print("=" * 80)
    
    scheduler = get_scheduler()
    
    # Створюємо задачу
    print("\n3.1 Створення задачі...")
    job = scheduler.add_interval_job(
        job_id="test_management",
        func=test_job_callback,
        interval_minutes=0.0333,  # ~2 секунди
        args=("management_test",)
    )
    print(f"✓ Задача створена: {job.id}")
    
    # Чекаємо кілька виконань
    print("\n3.2 Чекаємо 5 секунд (має виконатись 2-3 рази)...")
    await asyncio.sleep(5)
    
    # Призупиняємо
    print("\n3.3 Призупинення задачі...")
    success = scheduler.pause_job("test_management")
    assert success, "Призупинення має бути успішним"
    print("✓ Задача призупинена")
    
    print("\n3.4 Чекаємо 5 секунд (задача НЕ має виконуватись)...")
    await asyncio.sleep(5)
    
    # Відновлюємо
    print("\n3.5 Відновлення задачі...")
    success = scheduler.resume_job("test_management")
    assert success, "Відновлення має бути успішним"
    print("✓ Задача відновлена")
    
    print("\n3.6 Чекаємо 5 секунд (задача знову має виконуватись)...")
    await asyncio.sleep(5)
    
    # Видаляємо
    print("\n3.7 Видалення задачі...")
    scheduler.remove_job("test_management")
    print("✓ Задача видалена")


async def test_scraping_integration():
    """Тест інтеграції з парсингом"""
    print("\n" + "=" * 80)
    print("ТЕСТ 4: Інтеграція з парсингом")
    print("=" * 80)
    
    scheduler = get_scheduler()
    
    # Тестові домени
    test_domains = ["example.com", "test.com", "demo.com"]
    
    print("\n4.1 Планування повного парсингу...")
    job = scheduler.schedule_full_scraping(
        cron_expression="*/5 * * * *",  # Кожні 5 хвилин (для тесту)
        domains=test_domains,
        config={"test_mode": True}
    )
    
    if job:
        print(f"✓ Повний парсинг запланований: {job.next_run_time}")
    else:
        print("✗ Помилка планування")
    
    print("\n4.2 Планування часткового парсингу...")
    job = scheduler.schedule_partial_scraping(
        cron_expression="*/10 * * * *",  # Кожні 10 хвилин
        all_domains=test_domains,
        batch_size=2,
        config={"test_mode": True}
    )
    
    if job:
        print(f"✓ Частковий парсинг запланований: {job.next_run_time}")
    else:
        print("✗ Помилка планування")
    
    print("\n4.3 Планування очищення...")
    job = scheduler.schedule_cleanup_old_sessions(interval_hours=1)
    
    if job:
        print(f"✓ Очищення заплановане: {job.next_run_time}")
    else:
        print("✗ Помилка планування")
    
    # Список всіх задач
    jobs = scheduler.get_all_jobs()
    print(f"\n✓ Всього запланованих задач: {len(jobs)}")
    for job_info in jobs:
        print(f"   - {job_info['id']}: {job_info['trigger']}")


async def test_default_jobs():
    """Тест ініціалізації дефолтних задач"""
    print("\n" + "=" * 80)
    print("ТЕСТ 5: Ініціалізація дефолтних задач")
    print("=" * 80)
    
    # Очищаємо всі задачі
    scheduler = get_scheduler()
    for job_info in scheduler.get_all_jobs():
        scheduler.remove_job(job_info['id'])
    
    print("\nІніціалізація дефолтних задач...")
    test_domains = [f"domain{i}.com" for i in range(1, 21)]  # 20 доменів
    
    init_default_jobs(domains=test_domains, config={"test_mode": True})
    
    jobs = scheduler.get_all_jobs()
    print(f"\n✓ Створено {len(jobs)} дефолтних задач:")
    for job_info in jobs:
        print(f"   - {job_info['id']}")
        print(f"     Наступний запуск: {job_info['next_run_time']}")
        print(f"     Trigger: {job_info['trigger']}\n")


async def main():
    """Запуск всіх тестів"""
    
    print("\n" + "=" * 80)
    print("🧪 ТЕСТУВАННЯ SCHEDULERSERVICE")
    print("=" * 80)
    
    try:
        await test_basic_scheduler()
        await test_cron_expressions()
        await test_job_management()
        await test_scraping_integration()
        await test_default_jobs()
        
        print("\n" + "=" * 80)
        print("✓ ВСІ ТЕСТИ ПРОЙДЕНО УСПІШНО!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ ПОМИЛКА: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Зупиняємо scheduler
        print("\nЗупинка scheduler...")
        scheduler = get_scheduler()
        scheduler.shutdown(wait=False)
        print("✓ Scheduler зупинено")


if __name__ == "__main__":
    asyncio.run(main())
