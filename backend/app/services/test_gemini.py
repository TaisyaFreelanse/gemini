"""
Тестовий скрипт для перевірки GeminiService

Запуск: python -m app.services.test_gemini
"""
import asyncio
from app.services.gemini import GeminiService
from app.services.scraper import WebScraper


async def test_gemini_with_scraper():
    """Тест інтеграції WebScraper + GeminiService"""
    
    print("=" * 80)
    print("ТЕСТ: WebScraper + GeminiService")
    print("=" * 80)
    
    # Крок 1: Завантажуємо HTML
    print("\n1️⃣ Завантаження HTML...")
    scraper = WebScraper()
    domain = "example.com"  # Замінити на реальний сайт з промокодами
    
    scraped_data = await scraper.scrape_domain(domain, use_proxy=False)
    
    if not scraped_data['success']:
        print(f"✗ Помилка завантаження: {scraped_data['error']}")
        return
    
    print(f"✓ HTML завантажено ({len(scraped_data['html_raw'])} байт)")
    print(f"  Title: {scraped_data['content']['title']}")
    print(f"  Clean HTML: {len(scraped_data['content']['clean_html'])} символів")
    
    # Крок 2: Аналізуємо через Gemini
    print("\n2️⃣ Аналіз через Gemini AI...")
    gemini = GeminiService()
    
    deals, error, metadata = await gemini.extract_deals_from_scraped_data(scraped_data)
    
    print(f"\n📊 Результати:")
    print(f"  Спроб API: {metadata.get('attempts', 0)}")
    print(f"  Невалідних угод: {metadata.get('invalid_deals_count', 0)}")
    
    if error:
        print(f"\n✗ Помилка: {error}")
        if metadata.get('raw_response'):
            print(f"\nСира відповідь (перші 500 символів):")
            print(metadata['raw_response'][:500])
        return
    
    if not deals:
        print("\n⚠️ Gemini не знайшов жодної акції")
        return
    
    print(f"\n✓ Знайдено {len(deals)} акцій:")
    print("=" * 80)
    
    for idx, deal in enumerate(deals, 1):
        print(f"\n🎁 Акція #{idx}:")
        print(f"   Shop: {deal.shop}")
        print(f"   Description: {deal.description}")
        print(f"   Code: {deal.code}")
        print(f"   Discount: {deal.discount}")
        print(f"   Valid: {deal.date_start} → {deal.date_end}")
        print(f"   URL: {deal.target_url}")
        print(f"   Categories: {', '.join(deal.categories)}")


async def test_gemini_direct():
    """Прямий тест GeminiService з простим HTML"""
    
    print("\n" + "=" * 80)
    print("ТЕСТ: Прямий виклик GeminiService")
    print("=" * 80)
    
    # Простий тестовий HTML з промокодом
    test_html = """
    <html>
    <head><title>Test Shop</title></head>
    <body>
        <h1>Welcome to Test Shop!</h1>
        <div class="promo-banner">
            <h2>Special Offer! 20% OFF</h2>
            <p>Use code <strong>SAVE20</strong> at checkout</p>
            <p>Valid until February 28, 2026</p>
        </div>
    </body>
    </html>
    """
    
    gemini = GeminiService()
    deals, error, metadata = await gemini.extract_deals(test_html, "testshop.com")
    
    if error:
        print(f"✗ Помилка: {error}")
        return
    
    print(f"✓ Знайдено {len(deals)} акцій")
    for deal in deals:
        print(f"\n  Code: {deal.code}")
        print(f"  Description: {deal.description}")


async def main():
    """Запуск всіх тестів"""
    
    # Тест 1: Простий HTML
    await test_gemini_direct()
    
    # Тест 2: З реальним скрапінгом (розкоментувати після налаштування)
    # await test_gemini_with_scraper()


if __name__ == "__main__":
    asyncio.run(main())
