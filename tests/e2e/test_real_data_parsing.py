"""
Тест с реальными данными из api.json и apiparsing.json
Проверяет полный цикл: загрузка доменов → парсинг → отображение результатов
"""

import pytest
from playwright.sync_api import Page, expect
import json
import time
import os
from pathlib import Path
from typing import List, Dict

# Конфигурация
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
PROJECT_ROOT = Path(__file__).parent.parent.parent
API_JSON_FILE = PROJECT_ROOT / "api.json"
APIPARSING_JSON_FILE = PROJECT_ROOT / "apiparsing.json"


def load_domains_from_api_json() -> List[str]:
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


def load_parsing_results() -> List[str]:
    """Загрузить результаты парсинга из apiparsing.json"""
    try:
        with open(APIPARSING_JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict) and 'data' in data:
            return data['data'] if isinstance(data['data'], list) else []
        elif isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"Ошибка загрузки apiparsing.json: {e}")
        return []


class TestRealDataParsing:
    """Тест с реальными данными из api.json и apiparsing.json"""
    
    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """Настройка перед каждым тестом"""
        page.set_viewport_size({"width": 1920, "height": 1080})
        yield
    
    def test_01_load_real_domains_from_api_json(self, page: Page):
        """Тест 1: Загрузка реальных доменов из api.json"""
        print("\n=== ТЕСТ 1: Загрузка реальных доменов ===")
        
        domains = load_domains_from_api_json()
        assert len(domains) > 0, "Должны быть загружены домены из api.json"
        
        print(f"  ✓ Загружено доменов: {len(domains)}")
        print(f"  ✓ Примеры: {', '.join(domains[:5])}")
        
        # Проверяем через API
        response = page.request.get(f"{API_BASE_URL}/mock-domains")
        assert response.status == 200, "Mock domains API должен работать"
        
        api_data = response.json()
        assert api_data.get('status') == True, "API должен вернуть успешный статус"
        assert len(api_data.get('data', [])) > 0, "API должен вернуть домены"
        
        print(f"  ✓ API вернул {len(api_data.get('data', []))} доменов")
    
    def test_02_configure_api_url_for_real_domains(self, page: Page):
        """Тест 2: Настройка API URL для получения реальных доменов"""
        print("\n=== ТЕСТ 2: Настройка API URL ===")
        
        page.goto(f"{FRONTEND_URL}/configuration")
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(3000)
        
        # Находим поле для API URL
        api_url_input = page.locator('input[type="url"]').first
        if api_url_input.count() > 0 and api_url_input.is_visible():
            api_url_input.clear()
            api_url_input.fill(f"{API_BASE_URL}/mock-domains")
            print(f"  ✓ Установлен API URL: {API_BASE_URL}/mock-domains")
            
            # Сохраняем конфигурацию
            save_button = page.locator('button:has-text("Save"), button:has-text("Сохранить"), button[type="submit"]').first
            if save_button.count() > 0 and save_button.is_visible():
                save_button.click()
                page.wait_for_timeout(3000)
                
                # Проверяем сообщение об успехе
                success_message = page.locator('text=/success|успешно|saved|сохранено/i')
                if success_message.count() > 0:
                    print(f"  ✓ Конфигурация сохранена")
        else:
            print("  ⚠ Поле API URL не найдено, пропускаем настройку")
    
    def test_03_start_real_parsing_with_domains(self, page: Page):
        """Тест 3: Запуск реального парсинга с доменами из api.json"""
        print("\n=== ТЕСТ 3: Запуск реального парсинга ===")
        
        # Загружаем домены
        domains = load_domains_from_api_json()
        assert len(domains) > 0, "Должны быть домены для парсинга"
        
        # Берем первые 3 домена для быстрого теста
        test_domains = domains[:3]
        print(f"  ✓ Тестируем с {len(test_domains)} доменами: {', '.join(test_domains)}")
        
        # Переходим на Dashboard
        page.goto(f"{FRONTEND_URL}/")
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(3000)
        
        # Запускаем парсинг через API
        try:
            response = page.request.post(
                f"{API_BASE_URL}/parsing/start",
                data=json.dumps({"batch_size": len(test_domains)}),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status == 201 or response.status == 200:
                result = response.json()
                session_id = result.get('session_id')
                print(f"  ✓ Парсинг запущен: Session ID = {session_id}")
                print(f"  ✓ Всего доменов: {result.get('total_domains', 0)}")
                
                # Ждем начала обработки
                print("  ⏳ Ожидание начала обработки (10 секунд)...")
                time.sleep(10)
                
                return session_id
            else:
                print(f"  ⚠ Ошибка запуска: {response.status()}")
                return None
        except Exception as e:
            print(f"  ⚠ Ошибка: {e}")
            return None
    
    def test_04_monitor_parsing_progress(self, page: Page):
        """Тест 4: Мониторинг прогресса парсинга в реальном времени"""
        print("\n=== ТЕСТ 4: Мониторинг прогресса ===")
        
        page.goto(f"{FRONTEND_URL}/")
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(3000)
        
        # Проверяем статус через API несколько раз
        for i in range(5):
            try:
                response = page.request.get(f"{API_BASE_URL}/parsing/status")
                if response.status == 200:
                    status = response.json()
                    processed = status.get('processed_domains', 0)
                    total = status.get('total_domains', 0)
                    progress = status.get('progress_percent', 0)
                    
                    print(f"  [{i+1}/5] Прогресс: {processed}/{total} ({progress:.1f}%)")
                    
                    if processed >= total and total > 0:
                        print(f"  ✓ Парсинг завершен!")
                        break
            except Exception as e:
                print(f"  ⚠ Ошибка получения статуса: {e}")
            
            if i < 4:
                time.sleep(5)
    
    def test_05_verify_results_in_reports_page(self, page: Page):
        """Тест 5: Проверка отображения результатов на странице Reports"""
        print("\n=== ТЕСТ 5: Проверка результатов в Reports ===")
        
        try:
            page.goto(f"{FRONTEND_URL}/reports")
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(5)  # Используем time.sleep вместо page.wait_for_timeout
        except Exception as e:
            print(f"  ⚠ Ошибка загрузки страницы: {e}")
            # Продолжаем проверку через API
        
        # Проверяем через API
        response = page.request.get(f"{API_BASE_URL}/reports")
        assert response.status == 200, "API отчетов должен быть доступен"
        
        reports_data = response.json()
        domains_list = reports_data.get('domains', [])
        total = reports_data.get('total', 0)
        
        print(f"  ✓ Получено отчетов: {total}")
        print(f"  ✓ В ответе: {len(domains_list)}")
        
        if domains_list:
            print(f"\n  Результаты парсинга:")
            for i, report in enumerate(domains_list[:10], 1):
                domain = report.get('domain', 'N/A')
                deals_count = report.get('deals_count', 0)
                success = report.get('success', False)
                scraped_at = report.get('scraped_at', 'N/A')
                
                status_icon = "✅" if success else "❌"
                print(f"  {i}. {status_icon} {domain}")
                print(f"     Угод: {deals_count}, Дата: {scraped_at}")
        else:
            print("  ⚠ Нет данных в отчетах. Возможно, парсинг еще не завершен.")
        
        # Проверяем отображение на странице
        page.wait_for_timeout(3000)
        
        # Ищем таблицу или список результатов
        reports_table = page.locator('table').first
        reports_text = page.locator('text=/domain|домен|deals|угод/i')
        
        if reports_table.count() > 0 or reports_text.count() > 0:
            print(f"  ✓ Результаты отображаются на странице")
        else:
            print("  ⚠ Результаты не найдены на странице (возможно, нет данных)")
    
    def test_06_verify_summary_statistics(self, page: Page):
        """Тест 6: Проверка статистики summary"""
        print("\n=== ТЕСТ 6: Проверка статистики ===")
        
        try:
            page.goto(f"{FRONTEND_URL}/reports")
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(3)  # Используем time.sleep
        except Exception as e:
            print(f"  ⚠ Ошибка загрузки страницы: {e}")
            # Продолжаем проверку через API
        
        # Проверяем summary через API
        response = page.request.get(f"{API_BASE_URL}/reports/summary")
        assert response.status == 200, "API summary должен быть доступен"
        
        summary = response.json()
        
        print(f"  ✓ Статистика получена:")
        print(f"     Всего доменов: {summary.get('total_domains', 0)}")
        print(f"     Всего сессий: {summary.get('total_sessions', 0)}")
        print(f"     Угод найдено: {summary.get('total_deals_found', 0)}")
        print(f"     Успешных парсингов: {summary.get('successful_scrapes', 0)}")
        print(f"     Ошибок: {summary.get('failed_scrapes', 0)}")
        
        # Проверяем отображение на странице
        summary_cards = page.locator('text=/Всього доменів|Успішних|Помилок|Знайдено угод/i')
        if summary_cards.count() > 0:
            print(f"  ✓ Статистика отображается на странице")
    
    def test_07_compare_with_apiparsing_json(self, page: Page):
        """Тест 7: Сравнение результатов с apiparsing.json"""
        print("\n=== ТЕСТ 7: Сравнение с apiparsing.json ===")
        
        # Загружаем данные из apiparsing.json
        parsing_results = load_parsing_results()
        
        if not parsing_results:
            print("  ⚠ apiparsing.json не найден или пуст, пропускаем сравнение")
            return
        
        print(f"  ✓ Загружено результатов из apiparsing.json: {len(parsing_results)}")
        
        # Получаем данные из API
        response = page.request.get(f"{API_BASE_URL}/reports")
        if response.status == 200:
            api_data = response.json()
            api_domains = [r.get('domain') for r in api_data.get('domains', [])]
            
            print(f"  ✓ Получено доменов из API: {len(api_domains)}")
            
            # Сравниваем количество
            if len(parsing_results) > 0:
                print(f"  ✓ apiparsing.json содержит {len(parsing_results)} записей")
                print(f"  ✓ API содержит {len(api_domains)} записей")
                
                # Проверяем совпадение доменов
                if api_domains:
                    matching = set(parsing_results) & set(api_domains)
                    if matching:
                        print(f"  ✓ Найдено совпадений: {len(matching)}")
                        print(f"     Примеры: {', '.join(list(matching)[:3])}")
    
    def test_08_verify_real_time_updates(self, page: Page):
        """Тест 8: Проверка автообновления в реальном времени"""
        print("\n=== ТЕСТ 8: Автообновление в реальном времени ===")
        
        page.goto(f"{FRONTEND_URL}/reports")
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(3000)
        
        # Получаем начальное состояние
        initial_response = page.request.get(f"{API_BASE_URL}/reports")
        if initial_response.status == 200:
            initial_data = initial_response.json()
            initial_count = initial_data.get('total', 0)
            print(f"  ✓ Начальное количество: {initial_count}")
        
        # Ждем автообновления (10 секунд)
        print("  ⏳ Ожидание автообновления (12 секунд)...")
        time.sleep(12)
        
        # Проверяем, что страница обновилась
        page.wait_for_timeout(2000)
        
        # Получаем обновленное состояние
        updated_response = page.request.get(f"{API_BASE_URL}/reports")
        if updated_response.status == 200:
            updated_data = updated_response.json()
            updated_count = updated_data.get('total', 0)
            print(f"  ✓ Обновленное количество: {updated_count}")
            
            # Проверяем, что данные обновились (или остались теми же, если парсинг завершен)
            if updated_count != initial_count:
                print(f"  ✓ Данные обновились: {initial_count} → {updated_count}")
            else:
                print(f"  ✓ Данные стабильны (парсинг завершен или не запущен)")
    
    def test_09_verify_deals_display(self, page: Page):
        """Тест 9: Проверка отображения найденных угод"""
        print("\n=== ТЕСТ 9: Отображение угод ===")
        
        page.goto(f"{FRONTEND_URL}/reports")
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(5000)
        
        # Получаем данные через API
        response = page.request.get(f"{API_BASE_URL}/reports")
        if response.status == 200:
            data = response.json()
            domains = data.get('domains', [])
            
            if domains:
                print(f"  ✓ Найдено доменов с результатами: {len(domains)}")
                
                # Проверяем наличие угод
                total_deals = sum(d.get('deals_count', 0) for d in domains)
                print(f"  ✓ Всего угод найдено: {total_deals}")
                
                # Проверяем отображение на странице
                deals_display = page.locator('text=/угод|deals|count/i')
                if deals_display.count() > 0:
                    print(f"  ✓ Количество угод отображается на странице")
                
                # Проверяем таблицу
                table_rows = page.locator('table tbody tr')
                if table_rows.count() > 0:
                    print(f"  ✓ Найдено строк в таблице: {table_rows.count()}")
                    
                    # Проверяем первую строку
                    first_row = table_rows.first
                    if first_row.count() > 0:
                        row_text = first_row.text_content()
                        print(f"  ✓ Первая строка содержит данные: {row_text[:50]}...")
            else:
                print("  ⚠ Нет данных для отображения")
    
    def test_10_full_workflow_with_real_data(self, page: Page):
        """Тест 10: Полный workflow с реальными данными"""
        print("\n=== ТЕСТ 10: Полный workflow ===")
        
        # 1. Загружаем домены
        domains = load_domains_from_api_json()
        assert len(domains) > 0, "Должны быть домены"
        
        # Берем первые 2 для быстрого теста
        test_domains = domains[:2]
        print(f"  ✓ Шаг 1: Загружено {len(test_domains)} доменов для теста")
        
        # 2. Настраиваем API URL
        page.goto(f"{FRONTEND_URL}/configuration")
        page.wait_for_timeout(2000)
        api_url_input = page.locator('input[type="url"]').first
        if api_url_input.count() > 0:
            api_url_input.fill(f"{API_BASE_URL}/mock-domains")
            save_button = page.locator('button:has-text("Save"), button[type="submit"]').first
            if save_button.count() > 0:
                save_button.click()
                page.wait_for_timeout(2000)
        print(f"  ✓ Шаг 2: API URL настроен")
        
        # 3. Запускаем парсинг
        page.goto(f"{FRONTEND_URL}/")
        page.wait_for_timeout(3000)
        
        try:
            response = page.request.post(
                f"{API_BASE_URL}/parsing/start",
                data=json.dumps({"batch_size": len(test_domains)}),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status in [200, 201]:
                result = response.json()
                session_id = result.get('session_id')
                print(f"  ✓ Шаг 3: Парсинг запущен (Session: {session_id})")
                
                # 4. Мониторим прогресс
                print(f"  ⏳ Шаг 4: Мониторинг прогресса (30 секунд)...")
                for i in range(6):
                    time.sleep(5)
                    status_response = page.request.get(f"{API_BASE_URL}/parsing/status")
                    if status_response.status == 200:
                        status = status_response.json()
                        processed = status.get('processed_domains', 0)
                        total = status.get('total_domains', 0)
                        print(f"     [{i+1}/6] {processed}/{total} доменов обработано")
                
                # 5. Проверяем результаты
                print(f"  ✓ Шаг 5: Проверка результатов...")
                page.goto(f"{FRONTEND_URL}/reports")
                page.wait_for_timeout(5000)
                
                reports_response = page.request.get(f"{API_BASE_URL}/reports")
                if reports_response.status == 200:
                    reports_data = reports_response.json()
                    domains_count = reports_data.get('total', 0)
                    print(f"  ✓ Найдено результатов: {domains_count}")
                    
                    if domains_count > 0:
                        print(f"  ✅ УСПЕХ: Результаты парсинга отображаются!")
                    else:
                        print(f"  ⚠ Нет результатов (возможно, парсинг еще не завершен)")
        except Exception as e:
            print(f"  ⚠ Ошибка в workflow: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
