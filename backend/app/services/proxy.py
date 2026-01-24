import random
from typing import Optional, Dict, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProxyConfig:
    """Конфігурація проксі"""
    host: str
    http_port: int
    socks_port: int
    login: str
    password: str
    
    def get_http_proxy_url(self) -> str:
        """Отримати HTTP/HTTPS proxy URL"""
        return f"http://{self.login}:{self.password}@{self.host}:{self.http_port}"
    
    def get_socks_proxy_url(self) -> str:
        """Отримати SOCKS5 proxy URL"""
        return f"socks5://{self.login}:{self.password}@{self.host}:{self.socks_port}"


class ProxyRotator:
    """
    Клас для ротації проксі серверів
    
    Підтримує:
    - HTTP/HTTPS проксі
    - SOCKS5 проксі
    - Автоматичну ротацію при помилках
    - Blacklist для неробочих проксі
    """
    
    def __init__(self, proxy_configs: List[ProxyConfig]):
        self.proxy_configs = proxy_configs
        self.current_index = 0
        self.blacklist: set = set()
        self.failed_attempts: Dict[str, int] = {}
        self.max_failures_per_proxy = 3
        
    def get_next_proxy(self, proxy_type: str = "http") -> Optional[str]:
        """
        Отримати наступний доступний проксі
        
        Args:
            proxy_type: "http" або "socks5"
        
        Returns:
            Proxy URL або None якщо всі проксі недоступні
        """
        available_proxies = [p for p in self.proxy_configs if p.host not in self.blacklist]
        
        if not available_proxies:
            logger.warning("Всі проксі в blacklist! Очищаємо blacklist...")
            self.blacklist.clear()
            self.failed_attempts.clear()
            available_proxies = self.proxy_configs
        
        if not available_proxies:
            logger.error("Немає доступних проксі!")
            return None
        
        # Вибираємо випадковий проксі для балансування навантаження
        proxy = random.choice(available_proxies)
        
        if proxy_type == "socks5":
            return proxy.get_socks_proxy_url()
        else:
            return proxy.get_http_proxy_url()
    
    def mark_proxy_failed(self, proxy_url: str):
        """
        Позначити проксі як невдалий
        
        Якщо кількість невдач перевищує максимум - додаємо в blacklist
        """
        # Витягуємо host з proxy URL
        try:
            host = proxy_url.split("@")[1].split(":")[0]
        except (IndexError, AttributeError):
            logger.error(f"Не вдалося розпарсити proxy URL: {proxy_url}")
            return
        
        self.failed_attempts[host] = self.failed_attempts.get(host, 0) + 1
        
        if self.failed_attempts[host] >= self.max_failures_per_proxy:
            logger.warning(f"Проксі {host} додано до blacklist після {self.failed_attempts[host]} невдач")
            self.blacklist.add(host)
    
    def mark_proxy_success(self, proxy_url: str):
        """
        Позначити проксі як успішний - скидаємо лічильник помилок
        """
        try:
            host = proxy_url.split("@")[1].split(":")[0]
            if host in self.failed_attempts:
                self.failed_attempts[host] = 0
        except (IndexError, AttributeError):
            pass
    
    @classmethod
    def from_config(cls, config_dict: Dict) -> "ProxyRotator":
        """
        Створити ProxyRotator з dict конфігурації
        
        Args:
            config_dict: Словник з ключами host, http_port, socks_port, login, password
        """
        proxy_config = ProxyConfig(
            host=config_dict.get("host", ""),
            http_port=config_dict.get("http_port", 59100),
            socks_port=config_dict.get("socks_port", 59101),
            login=config_dict.get("login", ""),
            password=config_dict.get("password", "")
        )
        return cls([proxy_config])
