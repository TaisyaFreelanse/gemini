# Повний перезапуск проекту: зупинка, перебудова та запуск контейнерів
# Запуск: .\restart-project.ps1
# Перед запуском переконайтеся, що Docker Desktop запущений!

Set-Location $PSScriptRoot

Write-Host "=== Зупинка контейнерів ===" -ForegroundColor Yellow
docker-compose down

Write-Host "`n=== Перебудова та запуск ===" -ForegroundColor Yellow
docker-compose up -d --build

Write-Host "`n=== Статус контейнерів ===" -ForegroundColor Green
docker-compose ps
