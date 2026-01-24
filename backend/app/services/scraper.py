import aiohttp
import asyncio
from bs4 import BeautifulSoup
from typing import Optional, Dict, Tuple
import logging
from urllib.parse import urlparse, urljoin
import re
from app.services.proxy import ProxyRotator, ProxyConfig
from app.core.config import settings
from app.core.cache import get_cache

logger = logging.getLogger(__name__)


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
    
    def __init__(self, proxy_rotator: Optional[ProxyRotator] = None):
        self.proxy_rotator = proxy_rotator
        self.timeout = aiohttp.ClientTimeout(total=settings.SCRAPING_TIMEOUT)
        self.max_retries = settings.SCRAPING_MAX_RETRIES
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
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
        
        for attempt in range(self.max_retries):
            proxy_url = None
            
            try:
                # Отримуємо проксі якщо потрібно
                if use_proxy and self.proxy_rotator:
                    proxy_url = self.proxy_rotator.get_next_proxy(proxy_type="http")
                    if not proxy_url:
                        logger.error("Не вдалося отримати проксі")
                        return None, "Всі проксі недоступні"
                
                # Виконуємо HTTP запит
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    kwargs = {'headers': self.headers}
                    if proxy_url:
                        kwargs['proxy'] = proxy_url
                    
                    logger.info(f"Спроба {attempt + 1}/{self.max_retries}: Завантаження {url}" + 
                               (f" через проксі {proxy_url.split('@')[1]}" if proxy_url else ""))
                    
                    async with session.get(url, **kwargs) as response:
                        if response.status == 200:
                            html_content = await response.text()
                            
                            # Успішне завантаження - відмічаємо проксі як робочий
                            if proxy_url and self.proxy_rotator:
                                self.proxy_rotator.mark_proxy_success(proxy_url)
                            
                            logger.info(f"✓ Успішно завантажено {url} ({len(html_content)} байт)")
                            return html_content, None
                        
                        else:
                            error_msg = f"HTTP {response.status}: {response.reason}"
                            logger.warning(f"✗ {error_msg} для {url}")
                            
                            # Якщо помилка клієнта (4xx) - не повторюємо
                            if 400 <= response.status < 500:
                                return None, error_msg
                            
                            # Для інших помилок - позначаємо проксі як невдалий
                            if proxy_url and self.proxy_rotator:
                                self.proxy_rotator.mark_proxy_failed(proxy_url)
            
            except asyncio.TimeoutError:
                error_msg = f"Timeout після {settings.SCRAPING_TIMEOUT} секунд"
                logger.warning(f"✗ {error_msg} для {url}")
                if proxy_url and self.proxy_rotator:
                    self.proxy_rotator.mark_proxy_failed(proxy_url)
            
            except aiohttp.ClientError as e:
                error_msg = f"Помилка з'єднання: {str(e)}"
                logger.warning(f"✗ {error_msg} для {url}")
                if proxy_url and self.proxy_rotator:
                    self.proxy_rotator.mark_proxy_failed(proxy_url)
            
            except Exception as e:
                error_msg = f"Неочікувана помилка: {str(e)}"
                logger.error(f"✗ {error_msg} для {url}", exc_info=True)
                if proxy_url and self.proxy_rotator:
                    self.proxy_rotator.mark_proxy_failed(proxy_url)
            
            # Чекаємо перед наступною спробою (exponential backoff)
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.info(f"Чекаємо {wait_time}с перед наступною спробою...")
                await asyncio.sleep(wait_time)
        
        return None, f"Не вдалося завантажити після {self.max_retries} спроб"
    
    def extract_visible_content(self, html: str, base_url: str) -> Dict[str, any]:
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
            'text': text[:50000],  # Обмежуємо розмір тексту
            'links': links[:100],  # Обмежуємо кількість посилань
            'meta_description': meta_desc.strip() if meta_desc else "",
            'clean_html': clean_html[:100000]  # Обмежуємо розмір HTML для Gemini
        }
    
    async def scrape_domain(self, domain: str, use_proxy: bool = True, use_cache: bool = True) -> Dict[str, any]:
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
        
        # Спробувати отримати з кешу
        if use_cache:
            try:
                cache = await get_cache()
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
            if use_cache:
                try:
                    cache = await get_cache()
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
