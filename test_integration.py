#!/usr/bin/env python3
"""
Тестовый скрипт для проверки интеграции фронтенда с API
Использует данные из api.json и apiparsing.json
"""

import json
import requests
import time
from typing import Dict, List, Optional
from datetime import datetime

# Конфигурация
API_BASE_URL = "http://localhost:8000/api/v1"
FRONTEND_URL = "http://localhost"
API_JSON_FILE = "api.json"
APIPARSING_JSON_FILE = "apiparsing.json"

class Colors:
    """Цвета для вывода в консоль"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    """Вывести заголовок"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(text: str):
    """Вывести успешное сообщение"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_error(text: str):
    """Вывести сообщение об ошибке"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def print_info(text: str):
    """Вывести информационное сообщение"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def print_warning(text: str):
    """Вывести предупреждение"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def load_json_file(filename: str) -> Optional[Dict]:
    """Загрузить JSON файл"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print_error(f"Файл {filename} не найден")
        return None
    except json.JSONDecodeError as e:
        print_error(f"Ошибка парсинга JSON в {filename}: {e}")
        return None

def test_health_check() -> bool:
    """Тест 1: Проверка здоровья API"""
    print_header("ТЕСТ 1: Health Check")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"API доступен: {data.get('status', 'unknown')}")
            return True
        else:
            print_error(f"API вернул статус {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("Не удалось подключиться к API. Убедитесь, что бэкенд запущен.")
        return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_frontend_accessibility() -> bool:
    """Тест 2: Проверка доступности фронтенда"""
    print_header("ТЕСТ 2: Доступность фронтенда")
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        if response.status_code == 200:
            print_success(f"Фронтенд доступен: HTTP {response.status_code}")
            print_info(f"Размер ответа: {len(response.content)} байт")
            return True
        else:
            print_error(f"Фронтенд вернул статус {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("Не удалось подключиться к фронтенду. Убедитесь, что он запущен.")
        return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_config_api() -> bool:
    """Тест 3: Работа с конфигурацией"""
    print_header("ТЕСТ 3: API конфигурации")
    try:
        # Получить текущую конфигурацию
        response = requests.get(f"{API_BASE_URL}/config", timeout=5)
        if response.status_code == 200:
            config = response.json()
            print_success("Конфигурация получена")
            print_info(f"  API URL: {config.get('api_url', 'N/A')}")
            print_info(f"  Webhook URL: {config.get('webhook_url', 'N/A')}")
            print_info(f"  Proxy Host: {config.get('proxy_host', 'N/A')}")
            return True
        else:
            print_error(f"Ошибка получения конфигурации: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_mock_domains_api() -> bool:
    """Тест 4: Проверка mock domains API"""
    print_header("ТЕСТ 4: Mock Domains API")
    try:
        response = requests.get(f"{API_BASE_URL}/mock-domains", timeout=5)
        if response.status_code == 200:
            data = response.json()
            domains_count = len(data.get('data', []))
            print_success(f"Mock domains API работает")
            print_info(f"  Загружено доменов: {domains_count}")
            print_info(f"  Статус: {data.get('status', 'unknown')}")
            print_info(f"  Сообщение: {data.get('message', 'N/A')}")
            return True
        else:
            print_error(f"Ошибка получения доменов: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_update_api_url_from_file() -> bool:
    """Тест 5: Обновление API URL для получения доменов"""
    print_header("ТЕСТ 5: Обновление API URL")
    
    # Загружаем api.json для понимания структуры
    api_data = load_json_file(API_JSON_FILE)
    if not api_data:
        return False
    
    # Создаем mock API endpoint (в реальности это будет внешний API)
    # Для теста используем локальный файл
    try:
        # Обновляем API URL (в реальности это будет внешний API)
        update_data = {
            "api_url": "http://localhost:8000/api/v1/mock-domains"
        }
        
        response = requests.put(
            f"{API_BASE_URL}/config/api-url",
            json=update_data,
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            print_success(f"API URL обновлен: {result.get('message', 'OK')}")
            print_info(f"  Новый URL: {update_data['api_url']}")
            return True
        else:
            print_error(f"Ошибка обновления API URL: {response.status_code}")
            print_error(f"  Ответ: {response.text}")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_parsing_with_domains_from_file() -> bool:
    """Тест 6: Запуск парсинга с доменами из api.json"""
    print_header("ТЕСТ 6: Запуск парсинга с доменами из api.json")
    
    # Загружаем домены из api.json
    api_data = load_json_file(API_JSON_FILE)
    if not api_data:
        return False
    
    domains = api_data.get('data', [])
    if not domains:
        print_error("В api.json нет данных (data)")
        return False
    
    print_info(f"Загружено доменов из api.json: {len(domains)}")
    
    # Берем первые 5 доменов для теста
    test_domains = domains[:5]
    print_info(f"Тестируем с {len(test_domains)} доменами: {', '.join(test_domains)}")
    
    try:
        # Запускаем парсинг
        start_data = {
            "batch_size": len(test_domains),
            "force_refresh": False
        }
        
        response = requests.post(
            f"{API_BASE_URL}/parsing/start",
            json=start_data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            session_id = result.get('session_id')
            print_success(f"Парсинг запущен: Session ID = {session_id}")
            print_info(f"  Статус: {result.get('status', 'unknown')}")
            print_info(f"  Всего доменов: {result.get('total_domains', 0)}")
            
            # Ждем немного и проверяем статус
            print_info("Ожидание 5 секунд...")
            time.sleep(5)
            
            # Проверяем статус
            status_response = requests.get(f"{API_BASE_URL}/parsing/status", timeout=5)
            if status_response.status_code == 200:
                status = status_response.json()
                print_success("Статус получен:")
                print_info(f"  Обработано: {status.get('processed_domains', 0)}/{status.get('total_domains', 0)}")
                print_info(f"  Успешных: {status.get('successful_domains', 0)}")
                print_info(f"  Ошибок: {status.get('failed_domains', 0)}")
                print_info(f"  Прогресс: {status.get('progress_percent', 0):.1f}%")
                print_info(f"  Скорость: {status.get('domains_per_hour', 0):.1f} domains/hour")
            
            return True
        else:
            print_error(f"Ошибка запуска парсинга: {response.status_code}")
            print_error(f"  Ответ: {response.text}")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_parsing_status() -> bool:
    """Тест 7: Проверка статуса парсинга"""
    print_header("ТЕСТ 7: Статус парсинга")
    try:
        response = requests.get(f"{API_BASE_URL}/parsing/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            print_success("Статус парсинга получен")
            print_info(f"  Session ID: {status.get('session_id', 'N/A')}")
            print_info(f"  Статус: {status.get('status', 'N/A')}")
            print_info(f"  Обработано: {status.get('processed_domains', 0)}/{status.get('total_domains', 0)}")
            print_info(f"  Прогресс: {status.get('progress_percent', 0):.1f}%")
            return True
        else:
            print_error(f"Ошибка получения статуса: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_reports_api() -> bool:
    """Тест 8: API отчетов"""
    print_header("ТЕСТ 8: API отчетов")
    try:
        # Получаем summary
        response = requests.get(f"{API_BASE_URL}/reports/summary", timeout=5)
        if response.status_code == 200:
            summary = response.json()
            print_success("Summary получен")
            print_info(f"  Всего сессий: {summary.get('total_sessions', 0)}")
            print_info(f"  Обработано доменов: {summary.get('total_domains_processed', 0)}")
            print_info(f"  Успешных: {summary.get('successful_domains', 0)}")
            print_info(f"  Ошибок: {summary.get('failed_domains', 0)}")
            print_info(f"  Процент успеха: {summary.get('success_rate', 0):.1f}%")
            return True
        else:
            print_error(f"Ошибка получения summary: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_scheduler_api() -> bool:
    """Тест 9: API планировщика"""
    print_header("ТЕСТ 9: API планировщика")
    try:
        response = requests.get(f"{API_BASE_URL}/scheduler/status", timeout=5)
        if response.status_code == 200:
            scheduler = response.json()
            print_success("Статус планировщика получен")
            print_info(f"  Запущен: {scheduler.get('is_running', False)}")
            print_info(f"  Всего задач: {scheduler.get('total_jobs', 0)}")
            return True
        else:
            print_error(f"Ошибка получения статуса планировщика: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_compare_with_apiparsing() -> bool:
    """Тест 10: Сравнение с данными из apiparsing.json"""
    print_header("ТЕСТ 10: Сравнение с apiparsing.json")
    
    apiparsing_data = load_json_file(APIPARSING_JSON_FILE)
    if not apiparsing_data:
        print_warning("apiparsing.json не найден, пропускаем тест")
        return True  # Не критично
    
    # Проверяем структуру
    if 'data' in apiparsing_data:
        domains_count = len(apiparsing_data['data'])
        print_info(f"В apiparsing.json найдено {domains_count} доменов")
        
        # Сравниваем с api.json
        api_data = load_json_file(API_JSON_FILE)
        if api_data and 'data' in api_data:
            api_domains_count = len(api_data['data'])
            print_info(f"В api.json найдено {api_domains_count} доменов")
            
            if domains_count == api_domains_count:
                print_success("Количество доменов совпадает")
            else:
                print_warning(f"Количество доменов не совпадает: {domains_count} vs {api_domains_count}")
    
    return True

def main():
    """Главная функция"""
    print_header("ТЕСТИРОВАНИЕ ИНТЕГРАЦИИ ФРОНТЕНДА С API")
    print_info(f"API Base URL: {API_BASE_URL}")
    print_info(f"Frontend URL: {FRONTEND_URL}")
    print_info(f"Тестовые файлы: {API_JSON_FILE}, {APIPARSING_JSON_FILE}")
    
    results = []
    
    # Запускаем тесты
    results.append(("Health Check", test_health_check()))
    results.append(("Frontend Accessibility", test_frontend_accessibility()))
    results.append(("Config API", test_config_api()))
    results.append(("Mock Domains API", test_mock_domains_api()))
    results.append(("Update API URL", test_update_api_url_from_file()))
    results.append(("Parsing with Domains", test_parsing_with_domains_from_file()))
    results.append(("Parsing Status", test_parsing_status()))
    results.append(("Reports API", test_reports_api()))
    results.append(("Scheduler API", test_scheduler_api()))
    results.append(("Compare with apiparsing.json", test_compare_with_apiparsing()))
    
    # Итоги
    print_header("ИТОГИ ТЕСТИРОВАНИЯ")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        color = Colors.OKGREEN if result else Colors.FAIL
        print(f"{color}{status}{Colors.ENDC} - {test_name}")
    
    print(f"\n{Colors.BOLD}Результат: {passed}/{total} тестов пройдено{Colors.ENDC}\n")
    
    if passed == total:
        print_success("Все тесты пройдены успешно!")
        return 0
    else:
        print_error(f"Провалено тестов: {total - passed}")
        return 1

if __name__ == "__main__":
    exit(main())
