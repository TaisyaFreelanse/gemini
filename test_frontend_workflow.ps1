# =====================================================
# ТЕСТУВАННЯ ПОВНОГО WORKFLOW ЧЕРЕЗ FRONTEND API
# =====================================================

$baseUrl = "http://localhost:8000/api/v1"
$ErrorActionPreference = "Continue"

Write-Host "`n" -NoNewline
Write-Host "╔═══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                                   ║" -ForegroundColor Cyan
Write-Host "║          🧪  ТЕСТУВАННЯ FRONTEND WORKFLOW  🧪                    ║" -ForegroundColor Cyan
Write-Host "║                                                                   ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# =====================================================
# ТЕСТ 1: HEALTH CHECK
# =====================================================
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "ТЕСТ 1: Health Check + Frontend Accessibility" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

try {
    $health = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get
    Write-Host "✅ Backend Health: " -NoNewline -ForegroundColor Green
    Write-Host "$($health.status)" -ForegroundColor White
} catch {
    Write-Host "❌ Backend Health: FAILED" -ForegroundColor Red
}

try {
    $frontend = Invoke-WebRequest -Uri "http://localhost" -UseBasicParsing
    Write-Host "✅ Frontend: " -NoNewline -ForegroundColor Green
    Write-Host "Status $($frontend.StatusCode), Size $($frontend.Content.Length) bytes" -ForegroundColor White
} catch {
    Write-Host "❌ Frontend: FAILED" -ForegroundColor Red
}

Start-Sleep -Seconds 1

# =====================================================
# ТЕСТ 2: CONFIGURATION PAGE (GET/UPDATE CONFIG)
# =====================================================
Write-Host "`n"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "ТЕСТ 2: Configuration Management" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

# GET current config
try {
    $config = Invoke-RestMethod -Uri "$baseUrl/config" -Method Get
    Write-Host "✅ GET Config: " -NoNewline -ForegroundColor Green
    Write-Host "Domains API: $($config.domains_api_url)" -ForegroundColor White
    Write-Host "   Webhook: $($config.webhook_url)" -ForegroundColor DarkGray
    Write-Host "   Use Proxy: $($config.use_proxy)" -ForegroundColor DarkGray
} catch {
    Write-Host "❌ GET Config: FAILED" -ForegroundColor Red
}

# UPDATE config
try {
    $newConfig = @{
        domains_api_url = "http://localhost:8000/api/domains"
        webhook_url = "https://webhook.site/test-frontend"
        webhook_token = "test_token_frontend"
        use_proxy = $false
        proxy_host = ""
        proxy_http_port = 59100
        proxy_socks_port = 59101
        proxy_login = ""
        proxy_password = ""
    }
    
    $body = $newConfig | ConvertTo-Json
    $updated = Invoke-RestMethod -Uri "$baseUrl/config" -Method Put -Body $body -ContentType "application/json"
    Write-Host "✅ UPDATE Config: " -NoNewline -ForegroundColor Green
    Write-Host "Success" -ForegroundColor White
} catch {
    Write-Host "❌ UPDATE Config: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

Start-Sleep -Seconds 1

# =====================================================
# ТЕСТ 3: ЗАПУСК ПАРСИНГУ (як з Dashboard)
# =====================================================
Write-Host "`n"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "ТЕСТ 3: Start Parsing (Dashboard Action)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

# Створити список тестових доменів
$testDomains = @("example.com", "test.com", "demo.org")

try {
    $startRequest = @{
        domains = $testDomains
        use_proxy = $false
        use_cache = $true
    }
    
    $body = $startRequest | ConvertTo-Json
    $parseResult = Invoke-RestMethod -Uri "$baseUrl/parsing/start" -Method Post -Body $body -ContentType "application/json"
    
    Write-Host "✅ Parsing Started: " -NoNewline -ForegroundColor Green
    Write-Host "Session ID: $($parseResult.session_id)" -ForegroundColor White
    Write-Host "   Total domains: $($parseResult.total_domains)" -ForegroundColor DarkGray
    Write-Host "   Status: $($parseResult.status)" -ForegroundColor DarkGray
    
    $sessionId = $parseResult.session_id
    
    # Зачекати трохи
    Write-Host "`n   Чекаємо 5 секунд..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 5
    
    # Перевірити прогрес
    $status = Invoke-RestMethod -Uri "$baseUrl/parsing/status" -Method Get
    Write-Host "`n✅ Parsing Progress: " -NoNewline -ForegroundColor Green
    Write-Host "$($status.progress_percent)% ($($status.processed_domains)/$($status.total_domains))" -ForegroundColor White
    
} catch {
    Write-Host "❌ Parsing Start: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

Start-Sleep -Seconds 2

# =====================================================
# ТЕСТ 4: ОТРИМАННЯ ЗВІТІВ (Reports Page)
# =====================================================
Write-Host "`n"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "ТЕСТ 4: Reports & Statistics" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

try {
    $summary = Invoke-RestMethod -Uri "$baseUrl/reports/summary" -Method Get
    Write-Host "✅ Reports Summary:" -ForegroundColor Green
    Write-Host "   Total sessions: $($summary.total_sessions)" -ForegroundColor White
    Write-Host "   Total domains: $($summary.total_domains_processed)" -ForegroundColor White
    Write-Host "   Success rate: $($summary.success_rate)%" -ForegroundColor White
    Write-Host "   Total deals found: $($summary.total_deals_found)" -ForegroundColor White
} catch {
    Write-Host "❌ Reports Summary: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

try {
    $deals = Invoke-RestMethod -Uri "$baseUrl/reports/deals?limit=5" -Method Get
    Write-Host "`n✅ Recent Deals: " -NoNewline -ForegroundColor Green
    Write-Host "$($deals.Count) items" -ForegroundColor White
    
    if ($deals.Count -gt 0) {
        foreach ($deal in $deals | Select-Object -First 3) {
            Write-Host "   • Domain: $($deal.domain) | Deals: $($deal.deals_count)" -ForegroundColor DarkGray
        }
    }
} catch {
    Write-Host "❌ Recent Deals: FAILED" -ForegroundColor Red
}

Start-Sleep -Seconds 1

# =====================================================
# ТЕСТ 5: SCHEDULER (Cron Jobs)
# =====================================================
Write-Host "`n"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "ТЕСТ 5: Scheduler Management" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

try {
    $schedulerStatus = Invoke-RestMethod -Uri "$baseUrl/scheduler/status" -Method Get
    Write-Host "✅ Scheduler Status: " -NoNewline -ForegroundColor Green
    Write-Host "Running: $($schedulerStatus.running)" -ForegroundColor White
    Write-Host "   Total jobs: $($schedulerStatus.total_jobs)" -ForegroundColor DarkGray
} catch {
    Write-Host "❌ Scheduler Status: FAILED" -ForegroundColor Red
}

try {
    $jobs = Invoke-RestMethod -Uri "$baseUrl/scheduler/jobs" -Method Get
    Write-Host "`n✅ Cron Jobs: " -NoNewline -ForegroundColor Green
    Write-Host "$($jobs.Count) jobs" -ForegroundColor White
    
    if ($jobs.Count -gt 0) {
        foreach ($job in $jobs | Select-Object -First 3) {
            Write-Host "   • $($job.name): $($job.schedule)" -ForegroundColor DarkGray
        }
    }
} catch {
    Write-Host "❌ Cron Jobs List: FAILED" -ForegroundColor Red
}

Start-Sleep -Seconds 1

# =====================================================
# ТЕСТ 6: CACHE MANAGEMENT
# =====================================================
Write-Host "`n"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "ТЕСТ 6: Cache Management" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

try {
    $cacheStats = Invoke-RestMethod -Uri "$baseUrl/cache/stats" -Method Get
    Write-Host "✅ Cache Statistics:" -ForegroundColor Green
    Write-Host "   Cached pages: $($cacheStats.cached_pages)" -ForegroundColor White
    Write-Host "   TTL: $($cacheStats.ttl_seconds)s ($([math]::Round($cacheStats.ttl_seconds/3600, 1))h)" -ForegroundColor White
    Write-Host "   Redis memory: $($cacheStats.redis_memory_human)" -ForegroundColor White
} catch {
    Write-Host "❌ Cache Stats: FAILED" -ForegroundColor Red
}

# =====================================================
# ТЕСТ 7: REAL SCRAPING TEST
# =====================================================
Write-Host "`n"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "ТЕСТ 7: Real Domain Scraping (Frontend Simulation)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

# Запустити реальний парсинг одного домену
$realDomain = "example.com"

try {
    Write-Host "Запуск парсингу для: $realDomain" -ForegroundColor Cyan
    
    $parseBody = @{
        domains = @($realDomain)
        use_proxy = $false
        use_cache = $true
    } | ConvertTo-Json
    
    $parseStart = Invoke-RestMethod -Uri "$baseUrl/parsing/start" -Method Post -Body $parseBody -ContentType "application/json"
    Write-Host "✅ Session створено: $($parseStart.session_id)" -ForegroundColor Green
    
    # Зачекати виконання
    Write-Host "`n   Очікування результатів (10 секунд)..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 10
    
    # Перевірити результати
    $finalStatus = Invoke-RestMethod -Uri "$baseUrl/parsing/status" -Method Get
    
    Write-Host "`n✅ Результати парсингу:" -ForegroundColor Green
    Write-Host "   Оброблено: $($finalStatus.processed_domains)/$($finalStatus.total_domains)" -ForegroundColor White
    Write-Host "   Успішно: $($finalStatus.successful_domains)" -ForegroundColor White
    Write-Host "   Помилки: $($finalStatus.failed_domains)" -ForegroundColor White
    Write-Host "   Прогрес: $($finalStatus.progress_percent)%" -ForegroundColor White
    Write-Host "   Швидкість: $($finalStatus.domains_per_hour) domains/hour" -ForegroundColor White
    
} catch {
    Write-Host "❌ Real Scraping Test: FAILED - $($_.Exception.Message)" -ForegroundColor Red
}

# =====================================================
# ПІДСУМКИ
# =====================================================
Write-Host "`n"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "ПІДСУМКИ ТЕСТУВАННЯ" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""
Write-Host "✅ Протестовані компоненти Frontend:" -ForegroundColor Green
Write-Host "   1. Health Check & Accessibility" -ForegroundColor White
Write-Host "   2. Configuration Management (GET/PUT)" -ForegroundColor White
Write-Host "   3. Parsing Workflow (Start/Status)" -ForegroundColor White
Write-Host "   4. Reports & Statistics" -ForegroundColor White
Write-Host "   5. Scheduler Management" -ForegroundColor White
Write-Host "   6. Cache Management" -ForegroundColor White
Write-Host "   7. Real Domain Scraping" -ForegroundColor White
Write-Host ""
Write-Host "🌐 Frontend доступний на:" -ForegroundColor Cyan
Write-Host "   → http://localhost" -ForegroundColor White
Write-Host ""
Write-Host "📚 API Documentation:" -ForegroundColor Cyan
Write-Host "   → http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                                                                   ║" -ForegroundColor Green
Write-Host "║              🎉  FRONTEND ТЕСТУВАННЯ ЗАВЕРШЕНО!  🎉              ║" -ForegroundColor Green
Write-Host "║                                                                   ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
