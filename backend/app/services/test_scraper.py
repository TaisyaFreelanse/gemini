"""
Простий тестовий скрипт для перевірки роботи WebScraper

Запуск: python -m app.services.test_scraper
"""
import asyncio
from app.services.scraper import WebScraper
from app.services.proxy import ProxyConfig, ProxyRotator


async def test_scraper():
    """Тестуємо WebScraper"""
    
    # Тест 1: Без проксі
    print("=" * 80)
    print("ТЕСТ 1: Парсинг без проксі")
    print("=" * 80)
    
    scraper = WebScraper()
    result = await scraper.scrape_domain("example.com", use_proxy=False)
    
    if result['success']:
        print(f"✓ Успішно завантажено {result['domain']}")
        print(f"  Title: {result['content']['title']}")
        print(f"  Meta: {result['content']['meta_description']}")
        print(f"  Text length: {len(result['content']['text'])} символів")
        print(f"  Links: {len(result['content']['links'])} посилань")
    else:
        print(f"✗ Помилка: {result['error']}")
    
    # Тест 2: З проксі (якщо налаштовано)
    print("\n" + "=" * 80)
    print("ТЕСТ 2: Парсинг з проксі")
    print("=" * 80)
    
    # Приклад налаштування проксі
    proxy_config = {
        "host": "proxy.example.com",  # Замінити на реальний
        "http_port": 59100,
        "socks_port": 59101,
        "login": "user",  # Замінити на реальний
        "password": "pass"  # Замінити на реальний
    }
    
    scraper_with_proxy = WebScraper.create_with_config(proxy_config)
    result2 = await scraper_with_proxy.scrape_domain("example.com", use_proxy=True)
    
    if result2['success']:
        print(f"✓ Успішно завантажено через проксі {result2['domain']}")
    else:
        print(f"✗ Помилка: {result2['error']}")
    
    # Тест 3: Обробка помилок
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Обробка неіснуючого домену")
    print("=" * 80)
    
    result3 = await scraper.scrape_domain("this-domain-definitely-does-not-exist-12345.com", use_proxy=False)
    print(f"Результат: {'✓ успіх' if result3['success'] else '✗ помилка'}")
    if not result3['success']:
        print(f"Повідомлення: {result3['error']}")


if __name__ == "__main__":
    asyncio.run(test_scraper())
