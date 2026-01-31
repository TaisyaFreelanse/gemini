"""
Playwright-based scraper для обходу антибот захисту (Cloudflare, DataDome тощо)
"""
import asyncio
import logging
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


class PlaywrightScraper:
    """
    Скрапер на базі Playwright для обходу антибот захисту
    
    Використовує справжній браузер (Chromium) для:
    - Обходу Cloudflare, DataDome, PerimeterX
    - Рендерингу JavaScript
    - Емуляції реального користувача
    """
    
    def __init__(self, timeout: int = 15000, proxy_config: Optional[dict] = None):
        """
        Args:
            timeout: Таймаут в мілісекундах (за замовчуванням 15с)
            proxy_config: Конфігурація проксі {'host': ..., 'http_port': ..., 'login': ..., 'password': ...}
        """
        self.timeout = timeout
        self.proxy_config = proxy_config
        self._browser: Optional[Browser] = None
    
    async def _get_browser(self) -> Browser:
        """Отримати або створити браузер"""
        if self._browser is None or not self._browser.is_connected():
            playwright = await async_playwright().start()
            
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
            
            self._browser = await playwright.chromium.launch(**launch_options)
        
        return self._browser
    
    async def fetch_with_browser(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Завантажити сторінку через браузер
        
        Args:
            url: URL для завантаження
        
        Returns:
            Tuple[html_content, error_message]
        """
        browser = None
        context = None
        page = None
        
        try:
            browser = await self._get_browser()
            
            # Створюємо новий контекст з реалістичними налаштуваннями
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                locale='fr-FR',
                timezone_id='Europe/Paris',
                # Ігноруємо HTTPS помилки
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
                    runtime: {}
                };
                
                // Фейковий plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Фейковий languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['fr-FR', 'fr', 'en-US', 'en']
                });
            """)
            
            page = await context.new_page()
            
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
                # Спробуємо почекати - можливо Cloudflare challenge
                logger.info("Playwright: отримано 403, чекаємо на challenge...")
                await asyncio.sleep(3)
                
                # Перевіряємо чи пройшов challenge
                html = await page.content()
                if 'Just a moment' in html or 'Checking your browser' in html:
                    # Ще чекаємо
                    await asyncio.sleep(5)
                    html = await page.content()
            
            if status >= 400 and status != 403:
                return None, f"Playwright: HTTP {status}"
            
            # Отримуємо HTML
            html_content = await page.content()
            
            # Перевіряємо чи не Cloudflare challenge page
            if 'Just a moment' in html_content or 'Checking your browser' in html_content:
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
            # Закриваємо ресурси
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
    
    async def close(self):
        """Закрити браузер"""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None


# Глобальний інстанс для повторного використання
_playwright_scraper: Optional[PlaywrightScraper] = None


async def fetch_with_playwright(
    url: str, 
    proxy_config: Optional[dict] = None,
    timeout: int = 15000
) -> Tuple[Optional[str], Optional[str]]:
    """
    Завантажити сторінку через Playwright (зручна функція)
    
    Args:
        url: URL для завантаження
        proxy_config: Конфігурація проксі
        timeout: Таймаут в мс
    
    Returns:
        Tuple[html_content, error_message]
    """
    scraper = PlaywrightScraper(timeout=timeout, proxy_config=proxy_config)
    try:
        return await scraper.fetch_with_browser(url)
    finally:
        await scraper.close()
