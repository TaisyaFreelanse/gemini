"""
Playwright-based scraper для обходу антибот захисту (Cloudflare, DataDome тощо)
Оптимізовано для швидкодії та повторного використання браузера
"""
import asyncio
import logging
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, Page, Playwright, Error as PlaywrightError

logger = logging.getLogger(__name__)

# Константи
DEFAULT_TIMEOUT = 15000
CLOUDFLARE_WAIT_TIMEOUT = 8000
VIEWPORT_WIDTH = 1366
VIEWPORT_HEIGHT = 768

# Блоковані типи ресурсів для прискорення
BLOCKED_RESOURCE_TYPES = {'image', 'font', 'stylesheet', 'media', 'other'}


class PlaywrightScraper:
    """
    Скрапер на базі Playwright для обходу антибот захисту
    
    Використовує справжній браузер (Chromium) для:
    - Обходу Cloudflare, DataDome, PerimeterX
    - Рендерингу JavaScript
    - Емуляції реального користувача
    
    Оптимізації:
    - Повторне використання браузера
    - Блокування зайвих ресурсів (images, fonts, CSS)
    - Правильне очищення ресурсів
    """
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, proxy_config: Optional[dict] = None):
        """
        Args:
            timeout: Таймаут в мілісекундах (за замовчуванням 15с)
            proxy_config: Конфігурація проксі {'host': ..., 'http_port': ..., 'login': ..., 'password': ...}
        """
        self.timeout = timeout
        self.proxy_config = proxy_config
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
    
    async def _get_browser(self) -> Browser:
        """Отримати або створити браузер (з правильним збереженням playwright)"""
        if self._browser is None or not self._browser.is_connected():
            # Створюємо playwright якщо потрібно
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            
            launch_options = {
                'headless': True,
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                    '--disable-blink-features=AutomationControlled',
                    '--single-process',  # Зменшує використання пам'яті
                ]
            }
            
            # Додаємо проксі якщо є
            if self.proxy_config and self.proxy_config.get('host'):
                proxy = {
                    'server': f"http://{self.proxy_config['host']}:{self.proxy_config.get('http_port', 59100)}"
                }
                if self.proxy_config.get('login') and self.proxy_config.get('password'):
                    proxy['username'] = self.proxy_config['login']
                    proxy['password'] = self.proxy_config['password']
                launch_options['proxy'] = proxy
                logger.info(f"Playwright: використовую проксі {self.proxy_config['host']}")
            
            self._browser = await self._playwright.chromium.launch(**launch_options)
        
        return self._browser
    
    async def fetch_with_browser(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Завантажити сторінку через браузер
        
        Args:
            url: URL для завантаження
        
        Returns:
            Tuple[html_content, error_message]
        """
        context = None
        page = None
        
        try:
            browser = await self._get_browser()
            
            # Створюємо новий контекст з реалістичними налаштуваннями
            context = await browser.new_context(
                viewport={'width': VIEWPORT_WIDTH, 'height': VIEWPORT_HEIGHT},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                locale='fr-FR',
                timezone_id='Europe/Paris',
                ignore_https_errors=True,
            )
            
            # Додаємо скрипт для приховування автоматизації
            await context.add_init_script("""
                // Приховуємо webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Приховуємо автоматизацію Chrome
                window.chrome = {
                    runtime: {},
                    csi: function() {},
                    loadTimes: function() {}
                };
                
                // Реалістичний plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => {
                        const plugins = [];
                        plugins.length = 3;
                        return plugins;
                    }
                });
                
                // Фейковий languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['fr-FR', 'fr', 'en-US', 'en']
                });
                
                // Permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
            page = await context.new_page()
            
            # Блокуємо зайві ресурси для прискорення
            await page.route("**/*", self._route_handler)
            
            logger.info(f"Playwright: завантаження {url}")
            
            # Переходимо на сторінку
            response = await page.goto(
                url,
                timeout=self.timeout,
                wait_until='domcontentloaded'
            )
            
            if response is None:
                return None, "Playwright: не вдалося отримати відповідь"
            
            status = response.status
            
            if status == 403:
                # Спробуємо почекати на Cloudflare challenge
                html_content = await self._wait_for_cloudflare(page)
                if html_content:
                    return html_content, None
            
            if status >= 400 and status != 403:
                return None, f"Playwright: HTTP {status}"
            
            # Отримуємо HTML
            html_content = await page.content()
            
            # Перевіряємо чи не Cloudflare challenge page
            if self._is_cloudflare_challenge(html_content):
                return None, "Playwright: застрягли на Cloudflare challenge"
            
            logger.info(f"✓ Playwright: успішно завантажено {url} ({len(html_content)} байт)")
            return html_content, None
            
        except PlaywrightError as e:
            error_msg = f"Playwright помилка: {str(e)[:200]}"
            logger.warning(error_msg)
            return None, error_msg
            
        except asyncio.TimeoutError:
            error_msg = f"Playwright: таймаут {self.timeout}мс"
            logger.warning(error_msg)
            return None, error_msg
            
        except Exception as e:
            error_msg = f"Playwright: {type(e).__name__}: {str(e)[:200]}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
            
        finally:
            # Закриваємо тільки page та context, browser залишаємо для reuse
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
    
    async def _route_handler(self, route):
        """Блокування зайвих ресурсів для прискорення"""
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()
    
    async def _wait_for_cloudflare(self, page: Page) -> Optional[str]:
        """Спробувати пройти Cloudflare challenge"""
        logger.info("Playwright: отримано 403, чекаємо на challenge...")
        
        try:
            # Чекаємо поки зникне challenge сторінка
            await page.wait_for_function(
                """() => {
                    const text = document.body.innerText || '';
                    return !text.includes('Just a moment') && 
                           !text.includes('Checking your browser') &&
                           !text.includes('Please wait');
                }""",
                timeout=CLOUDFLARE_WAIT_TIMEOUT
            )
            
            html_content = await page.content()
            if not self._is_cloudflare_challenge(html_content):
                return html_content
                
        except Exception as e:
            logger.debug(f"Cloudflare wait timeout: {e}")
        
        return None
    
    def _is_cloudflare_challenge(self, html: str) -> bool:
        """Перевірити чи це Cloudflare challenge page"""
        challenge_markers = [
            'Just a moment',
            'Checking your browser',
            'Please wait',
            'cf-browser-verification',
            'challenge-platform'
        ]
        return any(marker in html for marker in challenge_markers)
    
    async def close(self):
        """Закрити браузер та playwright"""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None


# Глобальний інстанс та lock для потокобезпеки
_playwright_scraper: Optional[PlaywrightScraper] = None
_scraper_lock = asyncio.Lock()


def _configs_equal(config1: Optional[dict], config2: Optional[dict]) -> bool:
    """Compare two proxy configs for equality, handling None values."""
    if config1 is None and config2 is None:
        return True
    if config1 is None or config2 is None:
        return False
    # Compare relevant keys
    keys = ['host', 'http_port', 'login', 'password']
    return all(config1.get(k) == config2.get(k) for k in keys)


async def get_playwright_scraper(
    proxy_config: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> PlaywrightScraper:
    """
    Отримати глобальний інстанс scraper (або створити якщо не існує)
    Використовується для повторного використання браузера
    
    If the existing scraper has different timeout or proxy_config,
    the existing scraper is gracefully closed and a new one is created.
    """
    global _playwright_scraper
    
    async with _scraper_lock:
        if _playwright_scraper is not None:
            # Check if parameters match the existing instance
            timeout_matches = _playwright_scraper.timeout == timeout
            proxy_matches = _configs_equal(_playwright_scraper.proxy_config, proxy_config)
            
            if not timeout_matches or not proxy_matches:
                # Parameters differ - gracefully teardown existing scraper and create new one
                logger.info(
                    f"PlaywrightScraper config changed (timeout: {_playwright_scraper.timeout} -> {timeout}, "
                    f"proxy changed: {not proxy_matches}). Recreating scraper..."
                )
                try:
                    await _playwright_scraper.close()
                except Exception as e:
                    logger.warning(f"Error closing old PlaywrightScraper: {e}")
                _playwright_scraper = None
        
        if _playwright_scraper is None:
            _playwright_scraper = PlaywrightScraper(timeout=timeout, proxy_config=proxy_config)
        
        return _playwright_scraper


async def fetch_with_playwright(
    url: str, 
    proxy_config: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> Tuple[Optional[str], Optional[str]]:
    """
    Завантажити сторінку через Playwright (зручна функція)
    
    Використовує глобальний browser instance для швидкодії
    
    Args:
        url: URL для завантаження
        proxy_config: Конфігурація проксі
        timeout: Таймаут в мс
    
    Returns:
        Tuple[html_content, error_message]
    """
    # Загальний timeout на всю операцію (30 секунд максимум)
    overall_timeout = 30.0
    
    try:
        scraper = await get_playwright_scraper(proxy_config=proxy_config, timeout=timeout)
        result = await asyncio.wait_for(
            scraper.fetch_with_browser(url),
            timeout=overall_timeout
        )
        return result
    except asyncio.TimeoutError:
        logger.warning(f"Playwright: загальний таймаут {overall_timeout}с для {url}")
        return None, f"Playwright: загальний таймаут {overall_timeout}с"
    except Exception as e:
        logger.error(f"Playwright fetch error: {e}")
        return None, f"Playwright error: {str(e)[:100]}"


async def close_playwright_scraper():
    """Закрити глобальний scraper (викликати при shutdown)"""
    global _playwright_scraper
    
    async with _scraper_lock:
        if _playwright_scraper:
            await _playwright_scraper.close()
            _playwright_scraper = None
