# Smoke test Auto Scheduler
# Flow: onboarding -> planner -> generate-samples -> approve first -> schedule +2 min -> wait -> verify publish_logs + content published
# Chạy khi API đang chạy: http://localhost:8000

$ErrorActionPreference = "Stop"
$base = "http://localhost:8000"

Write-Host "=== Smoke test Scheduler (schedule +2 min, wait, verify) ===" -ForegroundColor Cyan

# 1) Onboarding
Write-Host "`n=== 1. POST /onboarding ==="
$onboardBody = @{
    tenant_name     = "Scheduler Test"
    industry        = "Test"
    brand_tone      = "OK"
    main_services   = @("A")
    target_customer = "SME"
    cta_style       = "Contact"
} | ConvertTo-Json
$onboard = Invoke-RestMethod -Uri "$base/onboarding" -Method Post -Body $onboardBody -ContentType "application/json; charset=utf-8"
$tenantId = $onboard.tenant.id
Write-Host "   tenant_id=$tenantId"

# 2) Planner
Write-Host "`n=== 2. POST /planner/generate (3 days) ==="
$plannerBody = @{ tenant_id = $tenantId; days = 3 } | ConvertTo-Json
Invoke-RestMethod -Uri "$base/planner/generate?force=false&ai=false" -Method Post -Body $plannerBody -ContentType "application/json; charset=utf-8" | Out-Null
Write-Host "   OK"

# 3) Generate samples
Write-Host "`n=== 3. POST /content/generate-samples (2 items) ==="
$contentBody = @{ tenant_id = $tenantId; count = 2 } | ConvertTo-Json
Invoke-RestMethod -Uri "$base/content/generate-samples?force=false&ai=false" -Method Post -Body $contentBody -ContentType "application/json; charset=utf-8" | Out-Null
Write-Host "   OK"

# 4) Approve first item
$list = Invoke-RestMethod -Uri "$base/content/list?tenant_id=$tenantId" -Method Get
$contentId = $list.items[0].id
Write-Host "`n=== 4. POST /content/$contentId/approve ==="
Invoke-RestMethod -Uri "$base/content/$contentId/approve" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; actor = "HUMAN" } | ConvertTo-Json) | Out-Null
Write-Host "   OK"

# 5) Schedule for now + 2 minutes (ISO format)
$now = [DateTime]::UtcNow
$scheduledAt = $now.AddMinutes(2).ToString("yyyy-MM-ddTHH:mm:ssZ")
Write-Host "`n=== 5. POST /content/$contentId/schedule (scheduled_at=$scheduledAt) ==="
$scheduleBody = @{ tenant_id = $tenantId; scheduled_at = $scheduledAt } | ConvertTo-Json
$scheduleResp = Invoke-RestMethod -Uri "$base/content/$contentId/schedule" -Method Post -ContentType "application/json" -Body $scheduleBody
Write-Host "   schedule_status=$($scheduleResp.schedule_status) scheduled_at=$($scheduleResp.scheduled_at)"

# 6) Scheduler status
Write-Host "`n=== 6. GET /scheduler/status ==="
$schedStatus = Invoke-RestMethod -Uri "$base/scheduler/status" -Method Get
Write-Host "   enabled=$($schedStatus.enabled) interval_seconds=$($schedStatus.interval_seconds) pending_count=$($schedStatus.pending_count)"

Write-Host "`n--- Cho worker chạy ~2-3 phút, sau đó kiểm tra kết quả ---" -ForegroundColor Yellow
Write-Host "   Chờ đến sau $scheduledAt (UTC), rồi chạy:"
Write-Host "   Invoke-RestMethod -Uri `"$base/publish/logs?tenant_id=$tenantId&limit=5`" -Method Get"
Write-Host "   Invoke-RestMethod -Uri `"$base/content/list?tenant_id=$tenantId&status=published`" -Method Get"
Write-Host ""

# Optional: wait 125 seconds then auto-check (2 min + 5 s buffer)
$waitSeconds = 125
Write-Host "   (Tùy chọn: script sẽ đợi $waitSeconds giây rồi tự kiểm tra. Bỏ qua bằng Ctrl+C.)" -ForegroundColor Gray
Start-Sleep -Seconds $waitSeconds

Write-Host "`n=== 7. GET /publish/logs (sau khi đợi) ==="
$logs = Invoke-RestMethod -Uri "$base/publish/logs?tenant_id=$tenantId&limit=5" -Method Get
Write-Host "   logs count=$($logs.logs.Count)"
if ($logs.logs.Count -gt 0) {
    $logs.logs | ForEach-Object { Write-Host "     id=$($_.id) status=$($_.status) post_id=$($_.post_id)" }
}

Write-Host "`n=== 8. GET /content/list?status=published ==="
$published = Invoke-RestMethod -Uri "$base/content/list?tenant_id=$tenantId&status=published" -Method Get
Write-Host "   published count=$($published.items.Count)"
if ($published.items.Count -gt 0) {
    Write-Host "   OK: Content đã chuyển sang status=published (scheduler đã đăng)." -ForegroundColor Green
} else {
    Write-Host "   Chưa có published (có thể chưa đến giờ hoặc Facebook chưa cấu hình)." -ForegroundColor Yellow
}

Write-Host "`n=== Scheduler smoke test completed ===" -ForegroundColor Cyan
