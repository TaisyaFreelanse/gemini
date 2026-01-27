#!/usr/bin/env python3
"""
Запуск теста с реальными данными из api.json и apiparsing.json
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

def check_files():
    """Проверка наличия файлов с данными"""
    print_header("ПРОВЕРКА ФАЙЛОВ С ДАННЫМИ")
    
    api_json = Path("api.json")
    apiparsing_json = Path("apiparsing.json")
    
    if not api_json.exists():
        print_error("api.json не найден!")
        return False
    print_success(f"api.json найден ({api_json.stat().st_size / 1024:.1f} KB)")
    
    if not apiparsing_json.exists():
        print_error("apiparsing.json не найден!")
        return False
    print_success(f"apiparsing.json найден ({apiparsing_json.stat().st_size / 1024:.1f} KB)")
    
    return True

def check_services():
    """Проверка сервисов"""
    print_header("ПРОВЕРКА СЕРВИСОВ")
    
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

def run_real_data_tests():
    """Запуск тестов с реальными данными"""
    print_header("ЗАПУСК ТЕСТОВ С РЕАЛЬНЫМИ ДАННЫМИ")
    
    test_file = Path(__file__).parent / "tests/e2e/test_real_data_parsing.py"
    
    if not test_file.exists():
        print_error(f"Файл тестов не найден: {test_file}")
        return False
    
    print_info("Запуск тестов с реальными данными из api.json и apiparsing.json...")
    print_info("Проверяется:")
    print_info("  • Загрузка доменов из api.json")
    print_info("  • Настройка API URL")
    print_info("  • Запуск реального парсинга")
    print_info("  • Мониторинг прогресса")
    print_info("  • Отображение результатов в Reports")
    print_info("  • Статистика summary")
    print_info("  • Сравнение с apiparsing.json")
    print_info("  • Автообновление в реальном времени")
    print_info("  • Отображение найденных угод")
    print_info("  • Полный workflow")
    print("")
    
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                str(test_file),
                "-v",
                "-s",
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
    print_header("🧪 ТЕСТ С РЕАЛЬНЫМИ ДАННЫМИ ИЗ API.JSON И APIPARSING.JSON")
    
    # Проверяем файлы
    if not check_files():
        print_error("\nФайлы с данными не найдены!")
        return 1
    
    # Проверяем сервисы
    if not check_services():
        print_error("\nСервисы недоступны!")
        print_info("Убедитесь, что Docker контейнеры запущены: docker compose up -d")
        return 1
    
    print_success("\nВсе предварительные условия выполнены!")
    print_info("Ожидание 5 секунд для полной инициализации...\n")
    time.sleep(5)
    
    # Запускаем тесты
    success = run_real_data_tests()
    
    print_header("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    
    if success:
        print_success("✅ ВСЕ ТЕСТЫ С РЕАЛЬНЫМИ ДАННЫМИ ПРОЙДЕНЫ!")
        print("")
        print_info("Проверено:")
        print_info("  ✓ Загрузка доменов из api.json")
        print_info("  ✓ Настройка API URL")
        print_info("  ✓ Запуск реального парсинга")
        print_info("  ✓ Мониторинг прогресса в реальном времени")
        print_info("  ✓ Отображение результатов в Reports")
        print_info("  ✓ Статистика summary")
        print_info("  ✓ Сравнение с apiparsing.json")
        print_info("  ✓ Автообновление работает")
        print_info("  ✓ Угоды отображаются корректно")
        print_info("  ✓ Полный workflow работает")
        print("")
        print_success("🎉 РЕЗУЛЬТАТЫ ПАРСИНГА ОТОБРАЖАЮТСЯ ВО ФРОНТЕНДЕ!")
        return 0
    else:
        print_error("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("")
        print_info("Проверьте:")
        print_info("  • Логи: docker compose logs backend --tail 50")
        print_info("  • Логи Celery: docker compose logs celery_worker --tail 50")
        print_info("  • БД: docker compose exec postgres psql -U scraper_user -d scraper_db -c 'SELECT COUNT(*) FROM scraped_deals;'")
        return 1

if __name__ == "__main__":
    exit(main())
