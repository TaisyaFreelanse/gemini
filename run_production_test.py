#!/usr/bin/env python3
"""
Запуск полноценного боевого теста перед выходом в прод
"""

import subprocess
import sys
import time
import requests
from pathlib import Path

# Цвета
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
CYAN = '\033[96m'
ENDC = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{BOLD}{CYAN}{'='*80}{ENDC}")
    print(f"{BOLD}{CYAN}{text:^80}{ENDC}")
    print(f"{BOLD}{CYAN}{'='*80}{ENDC}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{ENDC}")

def print_error(text):
    print(f"{RED}✗ {text}{ENDC}")

def print_info(text):
    print(f"{YELLOW}ℹ {text}{ENDC}")

def print_warning(text):
    print(f"{YELLOW}⚠ {text}{ENDC}")

def check_prerequisites():
    """Проверка предварительных условий"""
    print_header("ПРОВЕРКА ПРЕДВАРИТЕЛЬНЫХ УСЛОВИЙ")
    
    # Проверка файлов
    api_json = Path("api.json")
    apiparsing_json = Path("apiparsing.json")
    
    if not api_json.exists():
        print_error("api.json не найден!")
        return False
    print_success(f"api.json найден ({api_json.stat().st_size / 1024:.1f} KB)")
    
    if not apiparsing_json.exists():
        print_warning("apiparsing.json не найден (опционально)")
    else:
        print_success(f"apiparsing.json найден ({apiparsing_json.stat().st_size / 1024:.1f} KB)")
    
    # Проверка сервисов
    services = {
        "Frontend": "http://localhost",
        "API": "http://localhost:8000/api/v1/health",
        "Mock Domains": "http://localhost:8000/api/v1/mock-domains",
    }
    
    all_ok = True
    for name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print_success(f"{name}: доступен")
            else:
                print_error(f"{name}: вернул статус {response.status_code}")
                all_ok = False
        except Exception as e:
            print_error(f"{name}: недоступен - {e}")
            all_ok = False
    
    return all_ok

def run_production_tests():
    """Запуск боевых тестов"""
    print_header("ЗАПУСК БОЕВЫХ ТЕСТОВ")
    
    test_file = Path(__file__).parent / "tests/e2e/test_production_ready.py"
    
    if not test_file.exists():
        print_error(f"Файл тестов не найден: {test_file}")
        return False
    
    print_info("Запуск полноценного боевого теста...")
    print_info("Проверяется:")
    print_info("  • Загрузка и навигация")
    print_info("  • Настройка конфигурации")
    print_info("  • Работа с реальными доменами")
    print_info("  • Запуск парсинга и синхронизация")
    print_info("  • Все UI элементы и кнопки")
    print_info("  • Отчеты и планировщик")
    print_info("  • Синхронизация данных")
    print_info("  • Обработка ошибок")
    print_info("  • Производительность")
    print("")
    
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                str(test_file),
                "-v",
                "-s",  # Показываем print statements
                "--tb=short",
                "--color=yes",
            ],
            cwd=Path(__file__).parent,
            timeout=600,  # 10 минут
        )
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print_error("Тесты превысили лимит времени (10 минут)")
        return False
    except Exception as e:
        print_error(f"Ошибка запуска тестов: {e}")
        return False

def main():
    """Главная функция"""
    print_header("🚀 БОЕВОЙ ТЕСТ ПЕРЕД ВЫХОДОМ В ПРОД")
    
    # Проверяем предварительные условия
    if not check_prerequisites():
        print_error("\nПредварительные условия не выполнены!")
        print_info("Убедитесь, что:")
        print_info("  1. Docker контейнеры запущены: docker compose up -d")
        print_info("  2. Файл api.json находится в корне проекта")
        print_info("  3. Все сервисы доступны")
        return 1
    
    print_success("\nВсе предварительные условия выполнены!")
    print_info("Ожидание 5 секунд для полной инициализации...\n")
    time.sleep(5)
    
    # Запускаем тесты
    success = run_production_tests()
    
    print_header("РЕЗУЛЬТАТЫ БОЕВОГО ТЕСТИРОВАНИЯ")
    
    if success:
        print_success("✅ ВСЕ БОЕВЫЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("")
        print_info("Проверено:")
        print_info("  ✓ Полная загрузка и навигация")
        print_info("  ✓ Настройка конфигурации (API, Proxy, Gemini)")
        print_info("  ✓ Загрузка реальных доменов из api.json")
        print_info("  ✓ Запуск парсинга и синхронизация статуса")
        print_info("  ✓ Все UI элементы и кнопки работают")
        print_info("  ✓ Отчеты и планировщик функциональны")
        print_info("  ✓ Синхронизация данных фронтенд-бэкенд")
        print_info("  ✓ Обработка ошибок работает")
        print_info("  ✓ Производительность в норме")
        print("")
        print_success("🎉 ПРОЕКТ ГОТОВ К ВЫХОДУ В ПРОДАКШЕН!")
        print("")
        print_info("Доступные сервисы:")
        print_info("  Frontend: http://localhost")
        print_info("  API Docs: http://localhost:8000/docs")
        print_info("  Mock Domains: http://localhost:8000/api/v1/mock-domains")
        return 0
    else:
        print_error("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("")
        print_warning("Проверьте:")
        print_warning("  • Логи контейнеров: docker compose logs")
        print_warning("  • Доступность сервисов")
        print_warning("  • Наличие файла api.json")
        print_warning("  • Ошибки в консоли браузера")
        return 1

if __name__ == "__main__":
    exit(main())
