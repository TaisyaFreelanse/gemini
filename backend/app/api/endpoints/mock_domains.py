"""
Mock endpoint для получения доменов из api.json
Используется для тестирования интеграции
"""

from fastapi import APIRouter
from typing import Dict, List
import json
import os
from pathlib import Path

router = APIRouter()

# Путь к api.json (относительно корня проекта)
# Пробуем несколько вариантов путей
_possible_paths = [
    Path("/app/api.json"),  # Абсолютный путь в контейнере (приоритет)
    Path(__file__).parent.parent.parent.parent.parent / "api.json",  # Из контейнера
    Path("/Users/admin/Desktop/demidpidor/gemini/api.json"),  # Локальный путь
]

# Находим первый существующий путь
API_JSON_PATH = None
for path in _possible_paths:
    if path.exists():
        API_JSON_PATH = path
        break

# Если не нашли, используем первый вариант
if API_JSON_PATH is None:
    API_JSON_PATH = _possible_paths[0]


@router.get("/mock-domains")
async def get_mock_domains() -> Dict:
    """
    Mock endpoint для получения доменов из api.json
    Возвращает данные в формате, аналогичном реальному API
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Попытка загрузить api.json из: {API_JSON_PATH}")
        logger.info(f"Файл существует: {API_JSON_PATH.exists()}")
        
        if API_JSON_PATH.exists():
            logger.info(f"Чтение файла: {API_JSON_PATH}")
            with open(API_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Файл прочитан, тип данных: {type(data)}")
            
            # Проверяем структуру
            domains_list = []
            
            if isinstance(data, dict) and 'data' in data:
                raw_data = data['data']
            elif isinstance(data, list):
                raw_data = data
            else:
                raw_data = []
            
            # Преобразуем в список доменов (может быть массив строк или объектов)
            for item in raw_data:
                if isinstance(item, str):
                    # Просто домен как строка
                    domains_list.append(item)
                elif isinstance(item, dict):
                    # Объект с полем url или domain
                    domain = item.get('url') or item.get('domain') or item.get('name', '')
                    if domain:
                        # Извлекаем домен из URL если нужно
                        if '://' in domain:
                            from urllib.parse import urlparse
                            parsed = urlparse(domain)
                            domain = parsed.netloc or parsed.path
                        domains_list.append(domain)
            
            return {
                "status": True,
                "message": "Domains loaded from api.json",
                "data": domains_list,
                "total": len(domains_list)
            }
        else:
            # Если файл не найден, возвращаем тестовые данные
            return {
                "status": True,
                "message": "Using test domains (api.json not found)",
                "data": [
                    "example.com",
                    "test.com",
                    "demo.org"
                ],
                "total": 3
            }
    except Exception as e:
        return {
            "status": False,
            "message": f"Error loading domains: {str(e)}",
            "data": [],
            "total": 0
        }
