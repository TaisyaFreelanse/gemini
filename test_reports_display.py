#!/usr/bin/env python3
"""
Тест для проверки отображения результатов во фронтенде
"""

import requests
import json
import time

API_BASE_URL = "http://localhost:8000/api/v1"
FRONTEND_URL = "http://localhost"

def test_reports_api():
    """Проверка API отчетов"""
    print("=== Проверка API отчетов ===\n")
    
    # Проверяем summary
    try:
        response = requests.get(f"{API_BASE_URL}/reports/summary", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Summary получен:")
            print(f"   Всего доменов: {data.get('total_domains', 0)}")
            print(f"   Всего сессий: {data.get('total_sessions', 0)}")
            print(f"   Угод найдено: {data.get('total_deals_found', 0)}")
            print(f"   Успешных парсингов: {data.get('successful_scrapes', 0)}")
            print(f"   Ошибок: {data.get('failed_scrapes', 0)}")
        else:
            print(f"❌ Ошибка: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    print()
    
    # Проверяем список отчетов
    try:
        response = requests.get(f"{API_BASE_URL}/reports", timeout=5)
        if response.status_code == 200:
            data = response.json()
            domains = data.get('domains', [])
            total = data.get('total', 0)
            
            print(f"✅ Список отчетов получен:")
            print(f"   Всего записей: {total}")
            print(f"   В ответе: {len(domains)}")
            
            if domains:
                print(f"\n   Первые результаты:")
                for i, domain in enumerate(domains[:5], 1):
                    print(f"   {i}. {domain.get('domain', 'N/A')}")
                    print(f"      Угод: {domain.get('deals_count', 0)}")
                    print(f"      Статус: {'✅ Успешно' if domain.get('success') else '❌ Ошибка'}")
                    print(f"      Дата: {domain.get('scraped_at', 'N/A')}")
            else:
                print("   ⚠️  Нет данных в БД. Запустите парсинг для получения результатов.")
        else:
            print(f"❌ Ошибка: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def test_frontend_reports():
    """Проверка доступности фронтенда"""
    print("\n=== Проверка фронтенда ===\n")
    
    try:
        response = requests.get(f"{FRONTEND_URL}/reports", timeout=5)
        if response.status_code == 200:
            print(f"✅ Страница Reports доступна")
            print(f"   Размер: {len(response.content)} байт")
        else:
            print(f"❌ Ошибка: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТ ОТОБРАЖЕНИЯ РЕЗУЛЬТАТОВ")
    print("=" * 60)
    print()
    
    test_reports_api()
    test_frontend_reports()
    
    print("\n" + "=" * 60)
    print("РЕКОМЕНДАЦИИ:")
    print("=" * 60)
    print("1. Если нет данных в БД:")
    print("   - Запустите парсинг через Dashboard или API")
    print("   - Подождите завершения парсинга")
    print("   - Результаты появятся автоматически на странице Reports")
    print()
    print("2. Проверьте автообновление:")
    print("   - Откройте http://localhost/reports")
    print("   - Данные обновляются каждые 10 секунд")
    print()
    print("3. Если данные не появляются:")
    print("   - Проверьте логи: docker compose logs backend")
    print("   - Проверьте БД: docker compose exec postgres psql -U scraper_user -d scraper_db -c 'SELECT COUNT(*) FROM scraped_deals;'")
