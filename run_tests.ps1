# PowerShell скрипт для автоматического запуска Docker и тестирования

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🚀 Запуск Docker и тестирование" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Проверка Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker не найден. Установите Docker Desktop для Windows" -ForegroundColor Red
    exit 1
}

# Проверка docker-compose
$dockerComposeCmd = $null
if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    $dockerComposeCmd = "docker-compose"
} elseif (docker compose version 2>$null) {
    $dockerComposeCmd = "docker compose"
} else {
    Write-Host "❌ docker-compose не найден" -ForegroundColor Red
    exit 1
}

Write-Host "📦 Запуск Docker контейнеров..." -ForegroundColor Yellow
& $dockerComposeCmd up -d

Write-Host ""
Write-Host "⏳ Ожидание запуска сервисов (30 секунд)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

Write-Host ""
Write-Host "🔍 Проверка статуса контейнеров..." -ForegroundColor Yellow
& $dockerComposeCmd ps

Write-Host ""
Write-Host "🧪 Запуск тестов..." -ForegroundColor Yellow
Write-Host ""

# Запускаем тесты
python test_integration_simple.py

$testResult = $LASTEXITCODE

Write-Host ""
if ($testResult -eq 0) {
    Write-Host "✅ Все тесты пройдены успешно!" -ForegroundColor Green
} else {
    Write-Host "⚠️  Некоторые тесты не прошли. Проверьте логи выше." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "📊 Полезные команды:" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Просмотр логов:     $dockerComposeCmd logs -f"
Write-Host "  Остановка:          $dockerComposeCmd down"
Write-Host "  Перезапуск:         $dockerComposeCmd restart"
Write-Host ""
Write-Host "🌐 Ссылки:" -ForegroundColor Cyan
Write-Host "  Frontend:           http://localhost"
Write-Host "  API Docs:           http://localhost:8000/docs"
Write-Host "  API Health:         http://localhost:8000/api/v1/health"
Write-Host ""

exit $testResult
