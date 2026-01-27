#!/usr/bin/env python3
"""
Упрощенный тестовый скрипт без внешних зависимостей
Использует только встроенные библиотеки Python
"""

import json
import urllib.request
import urllib.error
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

def make_request(url: str, method: str = 'GET', data: Optional[Dict] = None, timeout: int = 5) -> Optional[Dict]:
    """Выполнить HTTP запрос"""
    try:
        req_data = None
        headers = {'Content-Type': 'application/json'}
        
        if data:
            req_data = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read().decode('utf-8')
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        print_error(f"HTTP {e.code}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        print_error(f"Ошибка подключения: {e.reason}")
        return None
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return None

def test_health_check() -> bool:
    """Тест 1: Проверка здоровья API"""
    print_header("ТЕСТ 1: Health Check")
    try:
        result = make_request(f"{API_BASE_URL}/health")
        if result and result.get('status') == 'healthy':
            print_success(f"API доступен: {result.get('status', 'unknown')}")
            return True
        else:
            print_error("API недоступен или вернул неожиданный ответ")
            print_info("Убедитесь, что бэкенд запущен: docker-compose up -d")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_frontend_accessibility() -> bool:
    """Тест 2: Проверка доступности фронтенда"""
    print_header("ТЕСТ 2: Доступность фронтенда")
    try:
        req = urllib.request.Request(FRONTEND_URL)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                print_success(f"Фронтенд доступен: HTTP {response.status}")
                return True
            else:
                print_error(f"Фронтенд вернул статус {response.status}")
                return False
    except urllib.error.URLError as e:
        print_error(f"Не удалось подключиться к фронтенду: {e.reason}")
        print_info("Убедитесь, что фронтенд запущен: docker-compose up -d")
        return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_config_api() -> bool:
    """Тест 3: Работа с конфигурацией"""
    print_header("ТЕСТ 3: API конфигурации")
    try:
        result = make_request(f"{API_BASE_URL}/config")
        if result:
            print_success("Конфигурация получена")
            print_info(f"  API URL: {result.get('api_url', 'N/A')}")
            print_info(f"  Webhook URL: {result.get('webhook_url', 'N/A')}")
            return True
        else:
            print_error("Ошибка получения конфигурации")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_mock_domains_api() -> bool:
    """Тест 4: Проверка mock domains API"""
    print_header("ТЕСТ 4: Mock Domains API")
    try:
        result = make_request(f"{API_BASE_URL}/mock-domains")
        if result:
            domains_count = len(result.get('data', []))
            print_success(f"Mock domains API работает")
            print_info(f"  Загружено доменов: {domains_count}")
            print_info(f"  Статус: {result.get('status', 'unknown')}")
            return True
        else:
            print_error("Ошибка получения доменов")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

def test_api_json_file() -> bool:
    """Тест 5: Проверка файла api.json"""
    print_header("ТЕСТ 5: Проверка api.json")
    api_data = load_json_file(API_JSON_FILE)
    if api_data:
        # Проверяем разные форматы данных
        domains = []
        if isinstance(api_data, dict) and 'data' in api_data:
            domains = api_data['data']
        elif isinstance(api_data, list):
            domains = api_data
        
        if domains:
            # Берем первые 5 доменов, преобразуя в строки
            first_domains = [str(d) if not isinstance(d, dict) else d.get('domain', str(d)) for d in domains[:5]]
            print_success(f"Файл api.json загружен: {len(domains)} доменов")
            print_info(f"  Первые 5 доменов: {', '.join(first_domains)}")
            return True
        else:
            print_error("В api.json нет данных")
            return False
    else:
        return False

def test_parsing_status() -> bool:
    """Тест 6: Проверка статуса парсинга"""
    print_header("ТЕСТ 6: Статус парсинга")
    try:
        result = make_request(f"{API_BASE_URL}/parsing/status")
        if result:
            print_success("Статус парсинга получен")
            print_info(f"  Session ID: {result.get('session_id', 'N/A')}")
            print_info(f"  Статус: {result.get('status', 'N/A')}")
            print_info(f"  Обработано: {result.get('processed_domains', 0)}/{result.get('total_domains', 0)}")
            return True
        else:
            print_error("Ошибка получения статуса")
            return False
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return False

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
    results.append(("API JSON File", test_api_json_file()))
    results.append(("Parsing Status", test_parsing_status()))
    
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
        print_warning(f"Провалено тестов: {total - passed}")
        print_info("\nДля запуска сервисов выполните:")
        print_info("  docker-compose up -d")
        print_info("\nИли откройте в браузере:")
        print_info(f"  Frontend: {FRONTEND_URL}")
        print_info(f"  API Docs: {API_BASE_URL.replace('/api/v1', '')}/docs")
        return 1

if __name__ == "__main__":
    exit(main())
