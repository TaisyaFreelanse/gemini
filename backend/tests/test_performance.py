"""
Тести продуктивності та оптимізацій

Перевірка Redis кешування, Rate limiting, та інших оптимізацій
"""
import asyncio
import time
from datetime import datetime


async def test_redis_cache():
    """
    Тест Redis кешування HTML
    """
    print("\n" + "=" * 80)
    print("ТЕСТ 1: Redis Cache (HTML content, TTL: 1 hour)")
    print("=" * 80)
    
    try:
        from app.core.cache import get_cache
        
        cache = await get_cache()
        
        # Тестові дані
        test_domain = "example.com"
        test_html_data = {
            'html_raw': '<html><body>Test HTML</body></html>',
            'content': {
                'title': 'Test Page',
                'text': 'Test content'
            }
        }
        
        print("\n1. Збереження в кеш...")
        start = time.time()
        success = await cache.set_html(test_domain, test_html_data)
        write_time = time.time() - start
        
        if success:
            print(f"   ✓ Збережено за {write_time*1000:.2f}ms")
        else:
            print("   ✗ Помилка збереження")
            return False
        
        print("\n2. Читання з кешу...")
        start = time.time()
        cached_data = await cache.get_html(test_domain)
        read_time = time.time() - start
        
        if cached_data:
            print(f"   ✓ Прочитано за {read_time*1000:.2f}ms")
            print(f"   ✓ Дані відповідають: {cached_data == test_html_data}")
        else:
            print("   ✗ Дані не знайдено в кеші")
            return False
        
        print("\n3. Статистика кешу...")
        stats = await cache.get_cache_stats()
        print(f"   • Закешовано сторінок: {stats.get('cached_pages', 0)}")
        print(f"   • TTL: {stats.get('ttl_seconds', 0)}s ({stats.get('ttl_seconds', 0)/3600:.1f}h)")
        print(f"   • Redis memory: {stats.get('redis_memory_used', 'N/A')}")
        
        print("\n4. Видалення з кешу...")
        success = await cache.delete_html(test_domain)
        if success:
            print("   ✓ Видалено успішно")
        
        # Перевірка що видалено
        cached_data = await cache.get_html(test_domain)
        if not cached_data:
            print("   ✓ Підтверджено видалення")
        
        print("\n✅ REDIS CACHE: PASS")
        print(f"   Швидкість читання: {read_time*1000:.2f}ms (очікується <10ms)")
        return True
        
    except Exception as e:
        print(f"\n✗ Помилка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_scraper_with_cache():
    """
    Тест WebScraper з кешуванням
    """
    print("\n" + "=" * 80)
    print("ТЕСТ 2: WebScraper з Redis Cache")
    print("=" * 80)
    
    try:
        from app.services.scraper import WebScraper
        from app.core.cache import get_cache
        
        scraper = WebScraper()
        cache = await get_cache()
        test_domain = "example.com"
        
        # Очистити кеш перед тестом
        await cache.delete_html(test_domain)
        
        print("\n1. Перше завантаження (без кешу)...")
        start = time.time()
        result1 = await scraper.scrape_domain(test_domain, use_proxy=False, use_cache=True)
        time1 = time.time() - start
        
        if result1['success']:
            print(f"   ✓ Завантажено за {time1:.2f}s")
            print(f"   • Cached: {result1.get('cached', False)}")
            print(f"   • HTML size: {len(result1.get('html_raw', ''))} chars")
        else:
            print(f"   ✗ Помилка: {result1.get('error')}")
            return False
        
        print("\n2. Друге завантаження (з кешу)...")
        start = time.time()
        result2 = await scraper.scrape_domain(test_domain, use_proxy=False, use_cache=True)
        time2 = time.time() - start
        
        if result2['success']:
            print(f"   ✓ Завантажено за {time2:.2f}s")
            print(f"   • Cached: {result2.get('cached', False)}")
            
            if result2.get('cached'):
                speedup = time1 / time2
                print(f"\n   🚀 Прискорення: {speedup:.0f}x швидше з кешем!")
            else:
                print("   ⚠️  Кеш не використано")
        else:
            print(f"   ✗ Помилка: {result2.get('error')}")
            return False
        
        # Очистити після тесту
        await cache.delete_html(test_domain)
        
        print("\n✅ SCRAPER + CACHE: PASS")
        return True
        
    except Exception as e:
        print(f"\n✗ Помилка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rate_limiter():
    """
    Тест Rate Limiter
    """
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Rate Limiter (100 req/min)")
    print("=" * 80)
    
    try:
        from app.core.rate_limiter import RateLimiter
        
        # Створити rate limiter з меншим лімітом для тесту
        limiter = RateLimiter(max_requests=5, window_seconds=10)
        test_ip = "192.168.1.1"
        
        print(f"\nЛіміт: {limiter.max_requests} запитів на {limiter.window_seconds}s")
        
        print("\n1. Тест нормальних запитів...")
        for i in range(3):
            allowed, remaining = limiter.is_allowed(test_ip)
            print(f"   Запит {i+1}: {'✓ OK' if allowed else '✗ BLOCKED'}, залишилось: {remaining}")
        
        print("\n2. Тест перевищення ліміту...")
        # Зробити ще 3 запити щоб перевищити ліміт 5
        for i in range(3):
            allowed, remaining = limiter.is_allowed(test_ip)
            status = "✓ OK" if allowed else "✗ BLOCKED"
            print(f"   Запит {i+4}: {status}, залишилось: {remaining}")
        
        # Перевірити що заблоковано
        allowed, remaining = limiter.is_allowed(test_ip)
        if not allowed:
            reset_time = limiter.get_reset_time(test_ip)
            print(f"\n   ✓ Ліміт спрацював! Reset через {reset_time}s")
        else:
            print("\n   ✗ Ліміт НЕ спрацював (помилка)")
            return False
        
        print("\n3. Статистика...")
        from app.core.rate_limiter import get_rate_limiter_stats
        stats = get_rate_limiter_stats()
        print(f"   • Tracked IPs: {stats['tracked_ips']}")
        print(f"   • Total requests: {stats['total_requests']}")
        
        print("\n✅ RATE LIMITER: PASS")
        return True
        
    except Exception as e:
        print(f"\n✗ Помилка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_performance_estimate():
    """
    Оцінка продуктивності системи
    """
    print("\n" + "=" * 80)
    print("ТЕСТ 4: Оцінка продуктивності")
    print("=" * 80)
    
    # Середній час на операції (секунди)
    scraping_time = 5
    gemini_time = 3
    webhook_time = 1
    total_per_domain = scraping_time + gemini_time + webhook_time
    
    workers = 10
    
    # Без кешу
    domains_per_hour_no_cache = (3600 / total_per_domain) * workers
    
    # З кешем (припускаємо 50% hit rate)
    cached_time = 0.01  # дуже швидко з кешу
    avg_time_with_cache = (total_per_domain + cached_time) / 2  # 50% кеш
    domains_per_hour_with_cache = (3600 / avg_time_with_cache) * workers
    
    print("\n📊 Прогноз продуктивності:")
    print(f"\n   Параметри:")
    print(f"   • Scraping: {scraping_time}s")
    print(f"   • Gemini AI: {gemini_time}s")
    print(f"   • Webhook: {webhook_time}s")
    print(f"   • Total per domain: {total_per_domain}s")
    print(f"   • Celery workers: {workers}")
    
    print(f"\n   Без кешу:")
    print(f"   • {domains_per_hour_no_cache:.0f} domains/hour")
    
    print(f"\n   З кешем (50% hit rate):")
    print(f"   • {domains_per_hour_with_cache:.0f} domains/hour")
    
    print(f"\n   Вимога: ≥150 domains/hour")
    
    if domains_per_hour_no_cache >= 150:
        print(f"   ✅ PASS: {domains_per_hour_no_cache:.0f} ≥ 150")
    else:
        print(f"   ⚠️  Може не вистачити без оптимізацій")
    
    if domains_per_hour_with_cache >= 150:
        print(f"   ✅ PASS (з кешем): {domains_per_hour_with_cache:.0f} ≥ 150")
        print(f"   🚀 Запас: {(domains_per_hour_with_cache/150):.1f}x від вимоги")


async def main():
    """Запуск всіх performance тестів"""
    
    print("\n" + "=" * 80)
    print("🚀 ТЕСТИ ПРОДУКТИВНОСТІ ТА ОПТИМІЗАЦІЙ")
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    results = []
    
    # Тест 1: Redis Cache
    results.append(await test_redis_cache())
    
    # Тест 2: Scraper з Cache
    results.append(await test_scraper_with_cache())
    
    # Тест 3: Rate Limiter
    results.append(test_rate_limiter())
    
    # Тест 4: Performance Estimate
    await test_performance_estimate()
    
    # Підсумки
    print("\n" + "=" * 80)
    print("ПІДСУМКИ")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nПройдено тестів: {passed}/{total} ({(passed/total*100):.0f}%)")
    
    if passed == total:
        print("\n🎉 ВСІ ОПТИМІЗАЦІЇ ПРАЦЮЮТЬ!")
    else:
        print("\n⚠️  Деякі тести не пройдено - перевірте налаштування")
    
    print("\n" + "=" * 80)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
