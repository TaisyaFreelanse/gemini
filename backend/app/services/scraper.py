import aiohttp
import asyncio
import ssl
import random
from bs4 import BeautifulSoup
from typing import Optional, Dict, Tuple, Any
import logging
from urllib.parse import urlparse, urljoin
import re
from app.services.proxy import ProxyRotator, ProxyConfig
from app.core.config import settings
from app.core.cache import get_cache

logger = logging.getLogger(__name__)

# Константи
MAX_TEXT_LENGTH = 50000
MAX_LINKS_COUNT = 100
MAX_HTML_LENGTH = 100000
BACKOFF_BASE = 2
BACKOFF_MAX = 30
BACKOFF_JITTER = 0.1


class WebScraper:
    """
    Веб-скрапер з підтримкою проксі для парсингу сайтів
    
    Основні можливості:
    - Підтримка HTTP/HTTPS та SOCKS5 проксі
    - Автоматична ротація проксі при помилках
    - Витягування тільки видимого HTML контенту
    - Обробка тільки першого рівня (головна сторінка)
    - Timeout: 30 секунд
    - Retry logic: максимум 3 спроби
    """
    
    # Список реалістичних User-Agent для ротації
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    ]
    
    def __init__(self, proxy_rotator: Optional[ProxyRotator] = None):
        self.proxy_rotator = proxy_rotator
        self.timeout = aiohttp.ClientTimeout(
            total=settings.SCRAPING_TIMEOUT,
            connect=15,
            sock_connect=15,
        )
        self.max_retries = settings.SCRAPING_MAX_RETRIES
        
        # Separate session pools for proxy and non-proxy connections
        # This avoids issues with SSL context being shared between different modes
        self._session_no_proxy: Optional[aiohttp.ClientSession] = None
        self._session_with_proxy: Optional[aiohttp.ClientSession] = None
        self._connector_no_proxy: Optional[aiohttp.TCPConnector] = None
        self._connector_with_proxy: Optional[aiohttp.TCPConnector] = None
        self._ssl_context_no_proxy: Optional[ssl.SSLContext] = None
        self._ssl_context_with_proxy: Optional[ssl.SSLContext] = None
    
    def _create_ssl_context(self, for_proxy: bool = False) -> ssl.SSLContext:
        """
        Create a proper SSL context.
        Never disables SSL verification - uses system CA bundle.
        For proxy scenarios, still uses proper SSL with system certificates.
        """
        ssl_context = ssl.create_default_context()
        # Always use proper SSL verification with system CA bundle
        # ssl_context.check_hostname = True  # Already default
        # ssl_context.verify_mode = ssl.CERT_REQUIRED  # Already default
        
        # Load system certificates
        ssl_context.load_default_certs()
        
        return ssl_context
    
    async def _get_session(self, use_proxy: bool = False) -> aiohttp.ClientSession:
        """
        Отримати або створити HTTP сесію з connection pooling.
        Maintains separate sessions for proxy and non-proxy connections.
        """
        if use_proxy:
            if self._session_with_proxy is None or self._session_with_proxy.closed:
                # Create proper SSL context (never disable verification)
                self._ssl_context_with_proxy = self._create_ssl_context(for_proxy=True)
                
                # Connector з пулом з'єднань for proxy
                self._connector_with_proxy = aiohttp.TCPConnector(
                    ssl=self._ssl_context_with_proxy,
                    limit=100,              # Максимум з'єднань
                    limit_per_host=10,      # На хост
                    ttl_dns_cache=300,      # DNS кеш 5 хв
                    enable_cleanup_closed=True
                )
                self._session_with_proxy = aiohttp.ClientSession(
                    timeout=self.timeout,
                    connector=self._connector_with_proxy
                )
            return self._session_with_proxy
        else:
            if self._session_no_proxy is None or self._session_no_proxy.closed:
                # Create proper SSL context
                self._ssl_context_no_proxy = self._create_ssl_context(for_proxy=False)
                
                # Connector з пулом з'єднань for non-proxy
                self._connector_no_proxy = aiohttp.TCPConnector(
                    ssl=self._ssl_context_no_proxy,
                    limit=100,              # Максимум з'єднань
                    limit_per_host=10,      # На хост
                    ttl_dns_cache=300,      # DNS кеш 5 хв
                    enable_cleanup_closed=True
                )
                self._session_no_proxy = aiohttp.ClientSession(
                    timeout=self.timeout,
                    connector=self._connector_no_proxy
                )
            return self._session_no_proxy
    
    async def close(self):
        """Закрити сесії та звільнити ресурси"""
        # Close non-proxy session
        if self._session_no_proxy and not self._session_no_proxy.closed:
            await self._session_no_proxy.close()
        self._session_no_proxy = None
        self._connector_no_proxy = None
        
        # Close proxy session
        if self._session_with_proxy and not self._session_with_proxy.closed:
            await self._session_with_proxy.close()
        self._session_with_proxy = None
        self._connector_with_proxy = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    def _get_headers(self, url: str) -> dict:
        """Отримати headers з випадковим User-Agent"""
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Referer': f'https://www.google.com/search?q={domain}',
        }
    
    async def _try_playwright(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Спробувати завантажити сторінку через Playwright (headless browser)
        Використовується як fallback при 403 помилках
        """
        try:
            from app.services.playwright_scraper import fetch_with_playwright
            
            # Отримуємо proxy config якщо є
            proxy_config = None
            if self.proxy_rotator and self.proxy_rotator.proxy_configs:
                proxy = self.proxy_rotator.proxy_configs[0]
                proxy_config = {
                    'host': proxy.host,
                    'http_port': proxy.http_port,
                    'login': proxy.login,
                    'password': proxy.password
                }
            
            return await fetch_with_playwright(url, proxy_config=proxy_config, timeout=15000)
        except Exception as e:
            logger.error(f"Playwright fallback помилка: {e}")
            return None, f"Playwright error: {str(e)[:100]}"
    
    async def fetch_website(self, url: str, use_proxy: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """
        Завантажити HTML контент з вказаного URL
        
        Args:
            url: URL сайту для парсингу
            use_proxy: Використовувати проксі (за замовчуванням True)
        
        Returns:
            Tuple[html_content, error_message]
            - html_content: HTML контент або None при помилці
            - error_message: Повідомлення про помилку або None при успіху
        """
        # Нормалізуємо URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Отримуємо сесію один раз
        session = await self._get_session(use_proxy=use_proxy and self.proxy_rotator is not None)
        
        for attempt in range(self.max_retries):
            proxy_base_url = None
            proxy_auth = None

            try:
                # Отримуємо проксі
                if use_proxy and self.proxy_rotator:
                    parts = self.proxy_rotator.get_next_proxy_for_aiohttp(proxy_type="http")
                    if not parts:
                        logger.error("Не вдалося отримати проксі")
                        return None, "Всі проксі недоступні"
                    proxy_base_url, login, password = parts
                    proxy_auth = aiohttp.BasicAuth(login, password) if (login and password) else None

                headers = self._get_headers(url)
                kwargs = {'headers': headers}
                if proxy_base_url:
                    kwargs['proxy'] = proxy_base_url
                    if proxy_auth:
                        kwargs['proxy_auth'] = proxy_auth

                logger.info(
                    f"Спроба {attempt + 1}/{self.max_retries}: Завантаження {url}" +
                    (f" через проксі {proxy_base_url}" if proxy_base_url else "")
                )

                async with session.get(url, **kwargs) as response:
                        if response.status == 200:
                            html_content = await response.text()
                            
                            # Успішне завантаження - відмічаємо проксі як робочий
                            if proxy_base_url and self.proxy_rotator:
                                self.proxy_rotator.mark_proxy_success(proxy_base_url)
                            
                            logger.info(f"✓ Успішно завантажено {url} ({len(html_content)} байт)")
                            return html_content, None
                        
                        else:
                            error_msg = f"HTTP {response.status}: {response.reason}"
                            logger.warning(f"✗ {error_msg} для {url}")
                            
                            # 403 - антибот захист, пробуємо Playwright
                            if response.status == 403:
                                logger.info(f"🌐 Пробуємо Playwright для {url} (антибот 403)")
                                playwright_html, playwright_error = await self._try_playwright(url)
                                if playwright_html:
                                    return playwright_html, None
                                else:
                                    logger.warning(f"Playwright теж не зміг: {playwright_error}")
                                    return None, f"403 + Playwright failed: {playwright_error}"
                            
                            # 429 - rate limit, повторюємо
                            if response.status == 429:
                                if proxy_base_url and self.proxy_rotator:
                                    self.proxy_rotator.mark_proxy_failed(proxy_base_url)
                                # Продовжуємо retry loop
                            # Інші 4xx помилки - не повторюємо
                            elif 400 <= response.status < 500:
                                return None, error_msg
                            else:
                                # 5xx помилки - позначаємо проксі як невдалий
                                if proxy_base_url and self.proxy_rotator:
                                    self.proxy_rotator.mark_proxy_failed(proxy_base_url)

            except asyncio.TimeoutError:
                error_msg = f"Timeout після {settings.SCRAPING_TIMEOUT} секунд"
                logger.warning(f"✗ {error_msg} для {url}")
                if proxy_base_url and self.proxy_rotator:
                    self.proxy_rotator.mark_proxy_failed(proxy_base_url)

            except aiohttp.ClientError as e:
                error_msg = f"Помилка з'єднання ({type(e).__name__}): {str(e)}"
                logger.warning(f"✗ {error_msg} для {url}" + (f" (проксі {proxy_base_url})" if proxy_base_url else ""))
                if proxy_base_url and self.proxy_rotator:
                    self.proxy_rotator.mark_proxy_failed(proxy_base_url)

            except Exception as e:
                error_msg = f"Неочікувана помилка: {str(e)}"
                logger.error(f"✗ {error_msg} для {url}", exc_info=True)
                if proxy_base_url and self.proxy_rotator:
                    self.proxy_rotator.mark_proxy_failed(proxy_base_url)
            
            # Чекаємо перед наступною спробою (exponential backoff з jitter)
            if attempt < self.max_retries - 1:
                base_wait = min(BACKOFF_BASE ** attempt, BACKOFF_MAX)
                jitter = random.uniform(0, base_wait * BACKOFF_JITTER)
                wait_time = base_wait + jitter
                logger.info(f"Чекаємо {wait_time:.1f}с перед наступною спробою...")
                await asyncio.sleep(wait_time)
        
        return None, f"Не вдалося завантажити після {self.max_retries} спроб"
    
    def extract_visible_content(self, html: str, base_url: str) -> Dict[str, Any]:
        """
        Витягнути видимий контент з HTML
        
        Args:
            html: HTML контент
            base_url: Базовий URL для резолюції відносних посилань
        
        Returns:
            Dict з витягнутими даними:
            - title: Заголовок сторінки
            - text: Видимий текст
            - links: Список посилань
            - meta_description: Meta опис
            - clean_html: Очищений HTML (без scripts, styles)
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Видаляємо непотрібні теги
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript']):
            tag.decompose()
        
        # Витягуємо title
        title = soup.title.string if soup.title else ""
        
        # Витягуємо meta description
        meta_desc = ""
        meta_tag = soup.find('meta', attrs={'name': 'description'})
        if meta_tag and meta_tag.get('content'):
            meta_desc = meta_tag.get('content')
        
        # Витягуємо видимий текст
        text = soup.get_text(separator=' ', strip=True)
        # Очищаємо множинні пробіли та переноси рядків
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Витягуємо посилання
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Резолвимо відносні посилання
            absolute_url = urljoin(base_url, href)
            link_text = link.get_text(strip=True)
            if link_text:
                links.append({
                    'url': absolute_url,
                    'text': link_text
                })
        
        # Очищений HTML (для Gemini)
        clean_html = str(soup)
        
        return {
            'title': title.strip() if title else "",
            'text': text[:MAX_TEXT_LENGTH],
            'links': links[:MAX_LINKS_COUNT],
            'meta_description': meta_desc.strip() if meta_desc else "",
            'clean_html': clean_html[:MAX_HTML_LENGTH]
        }
    
    async def scrape_domain(self, domain: str, use_proxy: bool = True, use_cache: bool = True) -> Dict[str, Any]:
        """
        Повний цикл парсингу домену з підтримкою кешування
        
        Args:
            domain: Домен для парсингу (можна з або без https://)
            use_proxy: Використовувати проксі
            use_cache: Використовувати Redis кеш (TTL: 1 година)
        
        Returns:
            Dict з результатами:
            - success: bool - чи успішний парсинг
            - domain: str - домен
            - url: str - повний URL
            - html_raw: str - сирий HTML (може бути None)
            - content: dict - витягнутий контент (може бути None)
            - error: str - повідомлення про помилку (може бути None)
            - cached: bool - чи отримано з кешу
        """
        # Нормалізуємо домен
        if not domain.startswith(('http://', 'https://')):
            url = 'https://' + domain
        else:
            url = domain
            domain = urlparse(url).netloc
        
        result = {
            'success': False,
            'domain': domain,
            'url': url,
            'html_raw': None,
            'content': None,
            'error': None,
            'cached': False
        }
        
        # Отримуємо кеш один раз
        cache = None
        if use_cache:
            try:
                cache = await get_cache()
            except Exception as e:
                logger.warning(f"Помилка ініціалізації кешу: {e}")
        
        # Спробувати отримати з кешу
        if cache:
            try:
                cached_data = await cache.get_html(domain)
                if cached_data:
                    result['success'] = True
                    result['html_raw'] = cached_data.get('html_raw')
                    result['content'] = cached_data.get('content')
                    result['cached'] = True
                    logger.info(f"✓ Використано кеш для {domain}")
                    return result
            except Exception as e:
                logger.warning(f"Помилка читання кешу: {e}")
        
        # Завантажуємо HTML
        html, error = await self.fetch_website(url, use_proxy=use_proxy)
        
        if html:
            result['success'] = True
            result['html_raw'] = html
            result['content'] = self.extract_visible_content(html, url)
            
            # Зберегти в кеш
            if cache:
                try:
                    await cache.set_html(domain, {
                        'html_raw': html,
                        'content': result['content']
                    })
                except Exception as e:
                    logger.warning(f"Помилка запису в кеш: {e}")
        else:
            result['error'] = error
        
        return result
    
    @classmethod
    def create_with_config(cls, proxy_config: Optional[Dict] = None) -> "WebScraper":
        """
        Створити WebScraper з конфігурацією проксі
        
        Args:
            proxy_config: Dict з налаштуваннями проксі або None
        
        Returns:
            WebScraper instance
        """
        proxy_rotator = None
        
        if proxy_config:
            proxy_rotator = ProxyRotator.from_config(proxy_config)
        
        return cls(proxy_rotator=proxy_rotator)
