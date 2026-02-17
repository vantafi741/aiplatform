# Smoke test HITL Approval + Audit
# Flow: onboarding -> planner -> generate-samples -> list drafts -> approve -> list approved -> audit events
# Chạy khi API ai_content_director đang chạy: http://localhost:8000

$ErrorActionPreference = "Stop"
$base = "http://localhost:8000"

Write-Host "=== Smoke test HITL Approval ===" -ForegroundColor Cyan

# 1) Onboarding
Write-Host "`n=== 1. POST /onboarding ==="
$onboardBody = @{
    tenant_name     = "HITL Test Tenant"
    industry        = "Marketing"
    brand_tone      = "Than thien"
    main_services   = @("Content", "Ads")
    target_customer = "SME"
    cta_style       = "Lien he"
} | ConvertTo-Json
$onboard = Invoke-RestMethod -Uri "$base/onboarding" -Method Post -Body $onboardBody -ContentType "application/json; charset=utf-8"
$tenantId = $onboard.tenant.id
Write-Host "   tenant_id=$tenantId"

# 2) Planner
Write-Host "`n=== 2. POST /planner/generate (7 days) ==="
$plannerBody = @{ tenant_id = $tenantId; days = 7 } | ConvertTo-Json
Invoke-RestMethod -Uri "$base/planner/generate?force=false&ai=false" -Method Post -Body $plannerBody -ContentType "application/json; charset=utf-8" | Out-Null
Write-Host "   OK"

# 3) Generate samples
Write-Host "`n=== 3. POST /content/generate-samples (5 items) ==="
$contentBody = @{ tenant_id = $tenantId; count = 5 } | ConvertTo-Json
$gen = Invoke-RestMethod -Uri "$base/content/generate-samples?force=false&ai=false" -Method Post -Body $contentBody -ContentType "application/json; charset=utf-8"
Write-Host "   created=$($gen.created). Items have review_state (auto_approved/needs_review/escalate_required)."

# 4) List drafts
Write-Host "`n=== 4. GET /content/list?status=draft ==="
$drafts = Invoke-RestMethod -Uri "$base/content/list?tenant_id=$tenantId&status=draft" -Method Get
Write-Host "   drafts count=$($drafts.items.Count)"

# 5) Approve first draft (if any)
if ($drafts.items.Count -gt 0) {
    $contentId = $drafts.items[0].id
    Write-Host "`n=== 5. POST /content/$contentId/approve ==="
    $approved = Invoke-RestMethod -Uri "$base/content/$contentId/approve" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; actor = "HUMAN" } | ConvertTo-Json)
    Write-Host "   status=$($approved.status) review_state=$($approved.review_state)"
} else {
    Write-Host "`n=== 5. (No drafts - all may be auto_approved) ==="
}

# 6) List approved
Write-Host "`n=== 6. GET /content/list?status=approved ==="
$approvedList = Invoke-RestMethod -Uri "$base/content/list?tenant_id=$tenantId&status=approved" -Method Get
Write-Host "   approved count=$($approvedList.items.Count)"

# 7) Audit events
Write-Host "`n=== 7. GET /audit/events ==="
$audit = Invoke-RestMethod -Uri "$base/audit/events?tenant_id=$tenantId&limit=20" -Method Get
Write-Host "   events count=$($audit.events.Count). Types: $(($audit.events | ForEach-Object { $_.event_type }) -join ', ')"

Write-Host "`n=== HITL smoke test completed ===" -ForegroundColor Cyan
