"""
Конфигурация для E2E тестов Playwright
"""

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
import os

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")


@pytest.fixture(scope="session")
def playwright():
    """Инициализация Playwright"""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright):
    """Создание браузера"""
    # Проверяем переменную окружения для headless режима
    headless = os.getenv("HEADLESS", "false").lower() == "true"
    browser = playwright.chromium.launch(
        headless=headless,  # Показываем браузер для отладки
        slow_mo=300,  # Замедляем действия для лучшей видимости
    )
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def context(browser):
    """Создание контекста браузера"""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
    )
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context):
    """Создание страницы"""
    page = context.new_page()
    yield page
    page.close()
