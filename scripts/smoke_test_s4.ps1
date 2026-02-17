# Smoke test Sprint 4 - Text Content Factory
# Flow: onboarding -> kb ingest -> planner/generate -> content/generate -> content/regenerate -> approve
# Chạy khi API đang chạy: http://localhost:8000

$base = "http://localhost:8000"
$idemKey = "smoke-s4-" + [guid]::NewGuid().ToString("N").Substring(0, 8)

Write-Host "=== 1. POST /onboarding ==="
$onboardBody = @{
    tenant = @{ name = "Smoke S4 Tenant"; slug = "smoke-s4-" + (Get-Random -Maximum 99999) }
    brand_profile = @{ name = "Smoke S4 Brand"; industry = "Tech"; language = "vi" }
} | ConvertTo-Json -Depth 5
try {
    $onboard = Invoke-RestMethod -Uri "$base/onboarding" -Method Post -Body $onboardBody -ContentType "application/json; charset=utf-8" -Headers @{ "Idempotency-Key" = $idemKey }
} catch {
    Write-Host "FAIL onboarding: $_"
    exit 1
}
$tenantId = $onboard.tenant_id
Write-Host "   tenant_id=$tenantId"

Write-Host "=== 2. POST /kb/bulk_ingest ==="
$items = @(
    @{ question = "What is product?"; answer = "Our product helps you."; tags = @("product"); source = "s4" },
    @{ question = "Support?"; answer = "Contact us."; tags = @("support"); source = "s4" }
)
$bulkBody = @{ items = $items } | ConvertTo-Json -Depth 5
try {
    $bulk = Invoke-RestMethod -Uri "$base/kb/bulk_ingest?tenant_id=$tenantId" -Method Post -Body $bulkBody -ContentType "application/json; charset=utf-8"
} catch {
    Write-Host "FAIL bulk_ingest: $_"
    exit 1
}
Write-Host "   created=$($bulk.created)"

Write-Host "=== 3. POST /planner/generate ==="
$planBody = @{ tenant_id = $tenantId } | ConvertTo-Json
try {
    $plan = Invoke-RestMethod -Uri "$base/planner/generate" -Method Post -Body $planBody -ContentType "application/json; charset=utf-8"
} catch {
    Write-Host "FAIL planner/generate: $_"
    exit 1
}
$planId = $plan.plan_id
$planItemId = $plan.items[0].id
Write-Host "   plan_id=$planId plan_item_id=$planItemId"

Write-Host "=== 4. POST /content/generate ==="
$genBody = @{ tenant_id = $tenantId; plan_id = $planId; plan_item_id = $planItemId } | ConvertTo-Json
try {
    $content = Invoke-RestMethod -Uri "$base/content/generate" -Method Post -Body $genBody -ContentType "application/json; charset=utf-8"
} catch {
    Write-Host "FAIL content/generate: $_"
    exit 1
}
$assetId = $content.asset_id
Write-Host "   asset_id=$assetId version=$($content.version.version)"

Write-Host "=== 5. POST /content/$assetId/regenerate ==="
try {
    $reg = Invoke-RestMethod -Uri "$base/content/$assetId/regenerate" -Method Post
} catch {
    Write-Host "FAIL content/regenerate: $_"
    exit 1
}
Write-Host "   new version=$($reg.version.version)"

Write-Host "=== 6. PUT /content/$assetId/status (approve) ==="
$statusBody = @{ status = "approved" } | ConvertTo-Json
try {
    $updated = Invoke-RestMethod -Uri "$base/content/$assetId/status" -Method Put -Body $statusBody -ContentType "application/json; charset=utf-8"
} catch {
    Write-Host "FAIL status update: $_"
    exit 1
}
if ($updated.status -ne "approved") {
    Write-Host "FAIL expected status=approved got $($updated.status)"
    exit 1
}
Write-Host "   status=$($updated.status)"

Write-Host "Smoke test S4 PASSED."
