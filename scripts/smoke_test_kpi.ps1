# Smoke test KPI (post metrics)
# Flow: onboarding -> planner -> generate-samples -> approve -> publish -> GET /kpi/summary
# Lưu ý: Metrics được worker thu thập mỗi 360 phút; có thể gọi /kpi/summary ngay (sẽ trống hoặc có dữ liệu cũ).

$ErrorActionPreference = "Stop"
$base = "http://localhost:8000"

Write-Host "=== Smoke test KPI (publish -> kpi/summary) ===" -ForegroundColor Cyan

# 1) Onboarding
Write-Host "`n=== 1. POST /onboarding ==="
$onboardBody = @{
    tenant_name     = "KPI Test"
    industry        = "Test"
    brand_tone      = "OK"
    main_services   = @("A")
    target_customer = "SME"
    cta_style       = "Contact"
} | ConvertTo-Json
$onboard = Invoke-RestMethod -Uri "$base/onboarding" -Method Post -Body $onboardBody -ContentType "application/json; charset=utf-8"
$tenantId = $onboard.tenant.id
Write-Host "   tenant_id=$tenantId"

# 2) Planner + Generate samples
Write-Host "`n=== 2. Planner + generate-samples ==="
$plannerBody = @{ tenant_id = $tenantId; days = 2 } | ConvertTo-Json
Invoke-RestMethod -Uri "$base/planner/generate?force=false&ai=false" -Method Post -Body $plannerBody -ContentType "application/json; charset=utf-8" | Out-Null
$contentBody = @{ tenant_id = $tenantId; count = 1 } | ConvertTo-Json
Invoke-RestMethod -Uri "$base/content/generate-samples?force=false&ai=false" -Method Post -Body $contentBody -ContentType "application/json; charset=utf-8" | Out-Null
Write-Host "   OK"

# 3) Approve + Publish
$list = Invoke-RestMethod -Uri "$base/content/list?tenant_id=$tenantId" -Method Get
$contentId = $list.items[0].id
Invoke-RestMethod -Uri "$base/content/$contentId/approve" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; actor = "HUMAN" } | ConvertTo-Json) | Out-Null
Write-Host "`n=== 3. POST /publish/facebook ==="
try {
    $pub = Invoke-RestMethod -Uri "$base/publish/facebook" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; content_id = $contentId } | ConvertTo-Json)
    Write-Host "   status=$($pub.status) post_id=$($pub.post_id)"
} catch {
    Write-Host "   (503 nếu chưa cấu hình FACEBOOK_* - bỏ qua)" -ForegroundColor Yellow
}

# 4) Fetch metrics ngay (POST /kpi/fetch-now)
Write-Host "`n=== 4. POST /kpi/fetch-now ==="
$fetchBody = @{ tenant_id = $tenantId; days = 7; limit = 20 } | ConvertTo-Json
try {
    $fetchResp = Invoke-RestMethod -Uri "$base/kpi/fetch-now" -Method Post -ContentType "application/json" -Body $fetchBody
    Write-Host "   fetched=$($fetchResp.fetched) success=$($fetchResp.success) fail=$($fetchResp.fail)"
} catch {
    Write-Host "   (Lỗi: $_)" -ForegroundColor Yellow
}

# 5) KPI summary
Write-Host "`n=== 5. GET /kpi/summary?tenant_id=...&days=7 ==="
$kpi = Invoke-RestMethod -Uri "$base/kpi/summary?tenant_id=$tenantId&days=7" -Method Get
Write-Host "   range_days=$($kpi.range_days) totals.reach=$($kpi.totals.reach) totals.impressions=$($kpi.totals.impressions)"
Write-Host "   posts count=$($kpi.posts.Count)"
if ($kpi.posts.Count -gt 0) {
    Write-Host "   OK: Có dữ liệu KPI." -ForegroundColor Green
} else {
    Write-Host "   (posts trống nếu chưa có bài đăng success hoặc token thiếu quyền insights.)" -ForegroundColor Yellow
}

Write-Host "`n=== KPI smoke test completed ===" -ForegroundColor Cyan
