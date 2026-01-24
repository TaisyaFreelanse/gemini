$baseUrl = "http://localhost:8000/api/v1"
$ErrorActionPreference = "Continue"

Write-Host "`n=== FRONTEND API WORKFLOW TEST ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Health Check
Write-Host "1. Health Check..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$baseUrl/health"
    Write-Host "   OK: Status = $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "   FAILED" -ForegroundColor Red
}

# Test 2: Frontend Accessibility
Write-Host "`n2. Frontend Page..." -ForegroundColor Yellow
try {
    $frontend = Invoke-WebRequest -Uri "http://localhost" -UseBasicParsing
    Write-Host "   OK: HTTP $($frontend.StatusCode), Size: $($frontend.Content.Length) bytes" -ForegroundColor Green
} catch {
    Write-Host "   FAILED" -ForegroundColor Red
}

# Test 3: Get Config
Write-Host "`n3. Get Configuration..." -ForegroundColor Yellow
try {
    $config = Invoke-RestMethod -Uri "$baseUrl/config"
    Write-Host "   OK: Domains API = $($config.domains_api_url)" -ForegroundColor Green
    Write-Host "       Webhook = $($config.webhook_url)" -ForegroundColor DarkGray
} catch {
    Write-Host "   FAILED" -ForegroundColor Red
}

# Test 4: Update Config
Write-Host "`n4. Update Configuration..." -ForegroundColor Yellow
try {
    $newConfig = @{
        domains_api_url = "http://localhost:8000/api/domains"
        webhook_url = "https://webhook.site/test"
        webhook_token = "test_token"
        use_proxy = $false
        proxy_host = ""
        proxy_http_port = 59100
        proxy_socks_port = 59101
        proxy_login = ""
        proxy_password = ""
    } | ConvertTo-Json
    
    $updated = Invoke-RestMethod -Uri "$baseUrl/config" -Method Put -Body $newConfig -ContentType "application/json"
    Write-Host "   OK: Config updated" -ForegroundColor Green
} catch {
    Write-Host "   FAILED: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 5: Start Parsing
Write-Host "`n5. Start Parsing..." -ForegroundColor Yellow
try {
    $parseRequest = @{
        domains = @("example.com")
        use_proxy = $false
        use_cache = $true
    } | ConvertTo-Json
    
    $result = Invoke-RestMethod -Uri "$baseUrl/parsing/start" -Method Post -Body $parseRequest -ContentType "application/json"
    Write-Host "   OK: Session $($result.session_id)" -ForegroundColor Green
    Write-Host "       Status: $($result.status)" -ForegroundColor DarkGray
    
    Write-Host "`n   Waiting 8 seconds..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 8
    
    $status = Invoke-RestMethod -Uri "$baseUrl/parsing/status"
    Write-Host "   Progress: $($status.progress_percent)% ($($status.processed_domains)/$($status.total_domains))" -ForegroundColor Green
    Write-Host "   Speed: $($status.domains_per_hour) domains/hour" -ForegroundColor DarkGray
    
} catch {
    Write-Host "   FAILED: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 6: Reports
Write-Host "`n6. Reports Summary..." -ForegroundColor Yellow
try {
    $summary = Invoke-RestMethod -Uri "$baseUrl/reports/summary"
    Write-Host "   OK: Total sessions = $($summary.total_sessions)" -ForegroundColor Green
    Write-Host "       Total domains = $($summary.total_domains_processed)" -ForegroundColor DarkGray
    Write-Host "       Success rate = $($summary.success_rate)%" -ForegroundColor DarkGray
} catch {
    Write-Host "   FAILED" -ForegroundColor Red
}

# Test 7: Scheduler
Write-Host "`n7. Scheduler Status..." -ForegroundColor Yellow
try {
    $scheduler = Invoke-RestMethod -Uri "$baseUrl/scheduler/status"
    Write-Host "   OK: Running = $($scheduler.running)" -ForegroundColor Green
    Write-Host "       Jobs = $($scheduler.total_jobs)" -ForegroundColor DarkGray
} catch {
    Write-Host "   FAILED" -ForegroundColor Red
}

# Test 8: Cache Stats
Write-Host "`n8. Cache Statistics..." -ForegroundColor Yellow
try {
    $cache = Invoke-RestMethod -Uri "$baseUrl/cache/stats"
    Write-Host "   OK: Cached pages = $($cache.cached_pages)" -ForegroundColor Green
    Write-Host "       TTL = $($cache.ttl_seconds)s" -ForegroundColor DarkGray
    Write-Host "       Memory = $($cache.redis_memory_human)" -ForegroundColor DarkGray
} catch {
    Write-Host "   FAILED" -ForegroundColor Red
}

Write-Host "`n=== TEST COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "Frontend: http://localhost" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
