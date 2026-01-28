# Перегляд логів контейнерів проекту
# Запуск: .\check-logs.ps1
# Перед запуском переконайтеся, що Docker Desktop запущений!

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

# Придушити попередження docker-compose про version
$env:COMPOSE_INTERACTIVE_NO_CLI = "1"

Write-Host "=== Backend (останні 80 рядків) ===" -ForegroundColor Cyan
docker-compose logs --tail=80 backend 2>&1 | Where-Object { $_ -notmatch "version.*obsolete" }

Write-Host "`n=== Celery Worker (останні 80 рядків) ===" -ForegroundColor Cyan
docker-compose logs --tail=80 celery_worker 2>&1 | Where-Object { $_ -notmatch "version.*obsolete" }

Write-Host "`n=== Celery Beat (останні 50 рядків) ===" -ForegroundColor Cyan
docker-compose logs --tail=50 celery_beat 2>&1 | Where-Object { $_ -notmatch "version.*obsolete" }

Write-Host "`n=== Статус контейнерів ===" -ForegroundColor Green
docker-compose ps 2>&1 | Where-Object { $_ -notmatch "version.*obsolete" }
