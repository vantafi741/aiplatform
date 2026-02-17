# Smoke test Facebook Publish (Graph API)
# Cần: FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN trong .env
# Flow: onboarding -> planner -> generate-samples -> approve 1 item -> publish -> logs

$ErrorActionPreference = "Stop"
$base = "http://localhost:8000"

Write-Host "=== Smoke test Facebook Publish ===" -ForegroundColor Cyan

# 1) Onboarding
Write-Host "`n=== 1. POST /onboarding ==="
$onboardBody = @{
    tenant_name     = "FB Publish Test"
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

# 4) Approve first item (draft or first in list)
$list = Invoke-RestMethod -Uri "$base/content/list?tenant_id=$tenantId" -Method Get
$contentId = $list.items[0].id
Write-Host "`n=== 4. POST /content/$contentId/approve ==="
Invoke-RestMethod -Uri "$base/content/$contentId/approve" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; actor = "HUMAN" } | ConvertTo-Json) | Out-Null
Write-Host "   OK"

# 5) Publish to Facebook
Write-Host "`n=== 5. POST /publish/facebook ==="
try {
    $pub = Invoke-RestMethod -Uri "$base/publish/facebook" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; content_id = $contentId } | ConvertTo-Json)
    Write-Host "   status=$($pub.status) post_id=$($pub.post_id) error_message=$($pub.error_message)"
    if ($pub.status -eq "success") {
        Write-Host "   OK: Published to Facebook" -ForegroundColor Green
    } else {
        Write-Host "   Fail (check FACEBOOK_* env): $($pub.error_message)" -ForegroundColor Yellow
    }
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 503) {
        Write-Host "   503: Facebook chưa cấu hình (FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN)" -ForegroundColor Yellow
    } else {
        throw
    }
}

# 6) Publish logs
Write-Host "`n=== 6. GET /publish/logs ==="
$logs = Invoke-RestMethod -Uri "$base/publish/logs?tenant_id=$tenantId&limit=10" -Method Get
Write-Host "   logs count=$($logs.logs.Count)"

Write-Host "`n=== Facebook Publish smoke test completed ===" -ForegroundColor Cyan
