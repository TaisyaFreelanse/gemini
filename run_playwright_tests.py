#!/usr/bin/env python3
"""
Скрипт для запуска Playwright E2E тестов
Проверяет весь функционал проекта через фронтенд
"""

import subprocess
import sys
import time
import requests
from pathlib import Path

# Цвета для вывода
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
ENDC = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*70}{ENDC}")
    print(f"{BOLD}{BLUE}{text:^70}{ENDC}")
    print(f"{BOLD}{BLUE}{'='*70}{ENDC}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{ENDC}")

def print_error(text):
    print(f"{RED}✗ {text}{ENDC}")

def print_info(text):
    print(f"{YELLOW}ℹ {text}{ENDC}")

def check_services():
    """Проверка доступности сервисов"""
    print_header("ПРОВЕРКА СЕРВИСОВ")
    
    services = {
        "Frontend": "http://localhost",
        "API Health": "http://localhost:8000/api/v1/health",
        "Mock Domains API": "http://localhost:8000/api/v1/mock-domains",
    }
    
    all_ok = True
    for name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print_success(f"{name}: доступен ({url})")
            else:
                print_error(f"{name}: вернул статус {response.status_code}")
                all_ok = False
        except Exception as e:
            print_error(f"{name}: недоступен - {e}")
            all_ok = False
    
    return all_ok

def run_tests():
    """Запуск Playwright тестов"""
    print_header("ЗАПУСК PLAYWRIGHT ТЕСТОВ")
    
    test_file = Path(__file__).parent / "tests/e2e/test_frontend_full.py"
    
    if not test_file.exists():
        print_error(f"Файл тестов не найден: {test_file}")
        return False
    
    print_info(f"Запуск тестов из: {test_file}")
    print_info("Браузер будет открыт для визуальной проверки\n")
    
    try:
        # Запускаем pytest с Playwright
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                str(test_file),
                "-v",
                "--tb=short",  # Короткий traceback
                "-s",  # Показываем print statements
            ],
            cwd=Path(__file__).parent,
            timeout=600,  # 10 минут максимум
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
    print_header("E2E ТЕСТИРОВАНИЕ ПРОЕКТА ЧЕРЕЗ PLAYWRIGHT")
    
    # Проверяем сервисы
    if not check_services():
        print_error("\nНекоторые сервисы недоступны!")
        print_info("Убедитесь, что Docker контейнеры запущены:")
        print_info("  docker compose up -d")
        print_info("\nПодождите 30-60 секунд после запуска контейнеров")
        return 1
    
    print_success("\nВсе сервисы доступны!")
    print_info("Ожидание 5 секунд для полной инициализации...\n")
    time.sleep(5)
    
    # Запускаем тесты
    success = run_tests()
    
    print_header("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    
    if success:
        print_success("Все тесты пройдены успешно!")
        print_info("\nПроверено:")
        print_info("  ✓ Доступность фронтенда и навигация")
        print_info("  ✓ Настройка API для получения доменов")
        print_info("  ✓ Настройка прокси")
        print_info("  ✓ Настройка Gemini API")
        print_info("  ✓ Просмотр статуса процесса")
        print_info("  ✓ Редактирование промпта и JSON")
        print_info("  ✓ Отчеты результатов")
        print_info("  ✓ Автоматизация через планировщик")
        print_info("  ✓ Полный workflow парсинга")
        print_info("  ✓ Интеграция с API")
        return 0
    else:
        print_error("Некоторые тесты не прошли")
        print_info("\nПроверьте:")
        print_info("  - Логи контейнеров: docker compose logs")
        print_info("  - Доступность сервисов: curl http://localhost:8000/api/v1/health")
        print_info("  - Фронтенд: http://localhost")
        return 1

if __name__ == "__main__":
    exit(main())
