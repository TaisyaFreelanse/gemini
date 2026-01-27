#!/usr/bin/env python3
"""
Скрипт для запуска парсинга с реальными данными из api.json
чтобы появились результаты во фронтенде Reports
"""

import requests
import json
import time
from pathlib import Path

API_BASE_URL = "http://localhost:8000/api/v1"
API_JSON_FILE = Path(__file__).parent / "api.json"

def load_domains():
    """Загрузить домены из api.json"""
    try:
        with open(API_JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        domains = []
        if isinstance(data, dict) and 'data' in data:
            raw_data = data['data']
        elif isinstance(data, list):
            raw_data = data
        else:
            return []
        
        for item in raw_data:
            if isinstance(item, str):
                domains.append(item)
            elif isinstance(item, dict):
                url = item.get('url', '') or item.get('domain', '') or item.get('name', '')
                if url:
                    # Извлекаем домен из URL
                    if '://' in url:
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        domain = parsed.netloc or parsed.path
                    else:
                        domain = url
                    if domain:
                        domains.append(domain)
        
        return domains
    except Exception as e:
        print(f"Ошибка загрузки api.json: {e}")
        return []

def check_api():
    """Проверить доступность API"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API доступен")
            return True
        else:
            print(f"❌ API вернул статус {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API недоступен: {e}")
        return False

def start_parsing(batch_size=5):
    """Запустить парсинг"""
    try:
        print(f"\n🚀 Запуск парсинга с {batch_size} доменами...")
        
        response = requests.post(
            f"{API_BASE_URL}/parsing/start",
            json={"batch_size": batch_size},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            session_id = result.get('session_id')
            total = result.get('total_domains', 0)
            
            print(f"✅ Парсинг запущен!")
            print(f"   Session ID: {session_id}")
            print(f"   Всего доменов: {total}")
            
            return session_id
        else:
            print(f"❌ Ошибка запуска: {response.status_code}")
            print(f"   Ответ: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

def monitor_progress(session_id, max_wait=300):
    """Мониторинг прогресса парсинга"""
    print(f"\n⏳ Мониторинг прогресса (максимум {max_wait} секунд)...")
    
    start_time = time.time()
    last_processed = 0
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_BASE_URL}/parsing/status", timeout=5)
            if response.status_code == 200:
                status = response.json()
                processed = status.get('processed_domains', 0)
                total = status.get('total_domains', 0)
                progress = status.get('progress_percent', 0)
                current_status = status.get('status', 'unknown')
                
                if processed != last_processed:
                    print(f"   Прогресс: {processed}/{total} ({progress:.1f}%) - {current_status}")
                    last_processed = processed
                
                if current_status == 'completed' or (total > 0 and processed >= total):
                    print(f"\n✅ Парсинг завершен!")
                    print(f"   Обработано: {processed}/{total}")
                    return True
                
                if current_status == 'failed':
                    print(f"\n❌ Парсинг завершился с ошибкой")
                    return False
        except Exception as e:
            print(f"   ⚠ Ошибка получения статуса: {e}")
        
        time.sleep(5)
    
    print(f"\n⏱ Время ожидания истекло")
    return False

def check_reports():
    """Проверить результаты в Reports"""
    print(f"\n📊 Проверка результатов в Reports...")
    
    try:
        # Проверяем summary
        response = requests.get(f"{API_BASE_URL}/reports/summary", timeout=5)
        if response.status_code == 200:
            summary = response.json()
            total_domains = summary.get('total_domains', 0)
            total_deals = summary.get('total_deals_found', 0)
            
            print(f"   Всего доменов: {total_domains}")
            print(f"   Найдено угод: {total_deals}")
            
            if total_domains > 0 or total_deals > 0:
                print(f"✅ Данные есть в БД!")
                return True
            else:
                print(f"⚠ Данных пока нет")
                return False
        else:
            print(f"❌ Ошибка получения summary: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def main():
    """Главная функция"""
    print("=" * 60)
    print("🚀 ЗАПУСК ПАРСИНГА ДЛЯ ПОЯВЛЕНИЯ ДАННЫХ В REPORTS")
    print("=" * 60)
    
    # 1. Проверяем API
    if not check_api():
        print("\n❌ API недоступен. Убедитесь, что Docker контейнеры запущены:")
        print("   docker compose up -d")
        return 1
    
    # 2. Загружаем домены
    domains = load_domains()
    if not domains:
        print("\n❌ Не удалось загрузить домены из api.json")
        return 1
    
    print(f"\n✅ Загружено доменов: {len(domains)}")
    print(f"   Примеры: {', '.join(domains[:3])}")
    
    # 3. Запускаем парсинг с небольшим количеством доменов для быстрого результата
    batch_size = 3  # Берем первые 3 домена для быстрого теста
    session_id = start_parsing(batch_size)
    
    if not session_id:
        print("\n❌ Не удалось запустить парсинг")
        return 1
    
    # 4. Мониторим прогресс
    completed = monitor_progress(session_id, max_wait=120)  # Ждем максимум 2 минуты
    
    # 5. Проверяем результаты
    if completed:
        time.sleep(3)  # Даем время на сохранение в БД
        check_reports()
    
    print("\n" + "=" * 60)
    print("✅ ГОТОВО!")
    print("=" * 60)
    print("\nТеперь откройте http://localhost/reports")
    print("Данные должны появиться автоматически (автообновление каждые 10 секунд)")
    
    return 0

if __name__ == "__main__":
    exit(main())
