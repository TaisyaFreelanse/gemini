"""
Тестовий скрипт для перевірки WebhookService

Запуск: python -m app.services.test_webhook
"""
import asyncio
from app.services.webhook import WebhookService
from app.schemas.deals import DealSchema


async def test_single_deal():
    """Тест відправки однієї угоди"""
    print("=" * 80)
    print("ТЕСТ 1: Відправка однієї угоди")
    print("=" * 80)
    
    # Створюємо тестову угоду
    deal = DealSchema(
        shop="Test Shop",
        domain="testshop.com",
        description="Знижка 20% на всі товари",
        full_description="Отримайте знижку 20% на всі товари при використанні промокоду",
        code="SAVE20",
        date_start="2026-01-24 12:00",
        date_end="2026-02-24 23:59",
        offer_type=1,
        target_url="https://testshop.com/promo",
        discount="20%",
        categories=["3", "11"]
    )
    
    # ВАЖЛИВО: Замініть на ваш реальний webhook URL для тестування
    webhook_url = "https://webhook.site/unique-endpoint"  # Замінити!
    
    webhook = WebhookService(
        webhook_url=webhook_url,
        webhook_token="test_token_123"
    )
    
    print(f"\n🚀 Відправка угоди в webhook: {webhook_url}")
    print(f"   Shop: {deal.shop}")
    print(f"   Code: {deal.code}")
    print(f"   Discount: {deal.discount}")
    
    success, error = await webhook.send_deal(deal, "testshop.com", session_id=1)
    
    if success:
        print("\n✓ Угода успішно відправлена!")
    else:
        print(f"\n✗ Помилка відправки: {error}")
    
    # Статистика
    stats = webhook.get_stats()
    print(f"\n📊 Статистика:")
    print(f"   Total: {stats['total_sent']}")
    print(f"   Successful: {stats['successful']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Success rate: {stats['success_rate']:.1f}%")


async def test_batch_deals():
    """Тест пакетної відправки"""
    print("\n" + "=" * 80)
    print("ТЕСТ 2: Пакетна відправка кількох угод")
    print("=" * 80)
    
    # Створюємо кілька тестових угод
    deals = [
        DealSchema(
            shop="Shop A",
            domain="shopa.com",
            description="Безкоштовна доставка",
            full_description="Безкоштовна доставка на всі замовлення від 500 грн",
            code="FREESHIP",
            offer_type=3,
            target_url="https://shopa.com/delivery",
            discount="Не знайдено",
            categories=["5"]
        ),
        DealSchema(
            shop="Shop B",
            domain="shopb.com",
            description="Знижка 15%",
            full_description="Знижка 15% на електроніку",
            code="TECH15",
            offer_type=1,
            target_url="https://shopb.com/electronics",
            discount="15%",
            categories=["1", "3"]
        ),
        DealSchema(
            shop="Shop C",
            domain="shopc.com",
            description="2+1 подарунок",
            full_description="Купи 2 товари, отримай третій безкоштовно",
            code="BUY2GET1",
            offer_type=4,
            target_url="https://shopc.com/promo",
            discount="Не знайдено",
            categories=["2"]
        )
    ]
    
    webhook_url = "https://webhook.site/unique-endpoint"  # Замінити!
    
    webhook = WebhookService(webhook_url=webhook_url)
    
    print(f"\n🚀 Відправка {len(deals)} угод пакетом...")
    
    result = await webhook.send_deals_batch(deals, "testdomain.com", session_id=2)
    
    print(f"\n📊 Результат:")
    print(f"   Total: {result['total']}")
    print(f"   Successful: {result['successful']}")
    print(f"   Failed: {result['failed']}")
    
    if result['errors']:
        print(f"\n❌ Помилки:")
        for error in result['errors']:
            print(f"   - Deal #{error['deal_index']}: {error['error']}")


async def test_webhook_errors():
    """Тест обробки помилок"""
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Обробка помилок")
    print("=" * 80)
    
    deal = DealSchema(
        shop="Test Shop",
        domain="test.com",
        description="Test deal",
        full_description="Test description",
        code="TEST123",
        offer_type=1,
        target_url="https://test.com",
        categories=[]
    )
    
    # Тест з неіснуючим URL
    print("\n📍 Тест 3.1: Неіснуючий webhook URL")
    webhook_bad = WebhookService(
        webhook_url="https://nonexistent-webhook-12345.com/api",
        max_retries=2  # Менше спроб для швидшого тесту
    )
    
    success, error = await webhook_bad.send_deal(deal, "test.com")
    print(f"   Result: {'✓ Success' if success else '✗ Failed'}")
    if error:
        print(f"   Error: {error[:100]}...")
    
    # Тест без URL
    print("\n📍 Тест 3.2: Відсутній webhook URL")
    webhook_none = WebhookService(webhook_url=None)
    
    success, error = await webhook_none.send_deal(deal, "test.com")
    print(f"   Result: {'✓ Success' if success else '✗ Failed'}")
    if error:
        print(f"   Error: {error}")


async def main():
    """Запуск всіх тестів"""
    
    print("\n" + "=" * 80)
    print("⚠️  УВАГА: Для тестування потрібен реальний webhook URL!")
    print("Рекомендується використати https://webhook.site/")
    print("=" * 80)
    
    response = input("\nПродовжити тестування? (y/n): ")
    
    if response.lower() != 'y':
        print("Тестування скасовано")
        return
    
    # Запускаємо тести
    await test_single_deal()
    await test_batch_deals()
    await test_webhook_errors()
    
    print("\n" + "=" * 80)
    print("✓ Всі тести завершено!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
