#!/bin/bash

# Скрипт для автоматического запуска Docker и тестирования

set -e

echo "=========================================="
echo "🚀 Запуск Docker и тестирование"
echo "=========================================="
echo ""

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не найден. Установите Docker Desktop для macOS${NC}"
    exit 1
fi

# Проверка docker-compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ docker-compose не найден${NC}"
    exit 1
fi

# Определяем команду для docker-compose
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

echo -e "${YELLOW}📦 Запуск Docker контейнеров...${NC}"
$DOCKER_COMPOSE up -d

echo ""
echo -e "${YELLOW}⏳ Ожидание запуска сервисов (30 секунд)...${NC}"
sleep 30

echo ""
echo -e "${YELLOW}🔍 Проверка статуса контейнеров...${NC}"
$DOCKER_COMPOSE ps

echo ""
echo -e "${YELLOW}🧪 Запуск тестов...${NC}"
echo ""

# Запускаем тесты
python3 test_integration_simple.py

TEST_RESULT=$?

echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ Все тесты пройдены успешно!${NC}"
else
    echo -e "${YELLOW}⚠️  Некоторые тесты не прошли. Проверьте логи выше.${NC}"
fi

echo ""
echo "=========================================="
echo "📊 Полезные команды:"
echo "=========================================="
echo "  Просмотр логов:     $DOCKER_COMPOSE logs -f"
echo "  Остановка:          $DOCKER_COMPOSE down"
echo "  Перезапуск:         $DOCKER_COMPOSE restart"
echo ""
echo "🌐 Ссылки:"
echo "  Frontend:           http://localhost"
echo "  API Docs:           http://localhost:8000/docs"
echo "  API Health:         http://localhost:8000/api/v1/health"
echo ""

exit $TEST_RESULT
