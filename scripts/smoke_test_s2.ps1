# Smoke test Sprint 2
# Chạy khi API đang chạy: http://localhost:8000
# Flow: onboarding -> bulk ingest 30 FAQ -> POST /kb/query

$base = "http://localhost:8000"
$idemKey = "smoke-s2-" + [guid]::NewGuid().ToString("N").Substring(0, 8)

Write-Host "=== 1. POST /onboarding (Idempotency-Key: $idemKey) ==="
$onboardBody = @{
    tenant = @{ name = "Smoke S2 Tenant"; slug = "smoke-s2-" + (Get-Random -Maximum 99999) }
    brand_profile = @{
        name = "Smoke Brand"
        business_name = "Smoke Business"
        industry = "Technology"
        language = "vi"
    }
} | ConvertTo-Json -Depth 5
try {
    $onboard = Invoke-RestMethod -Uri "$base/onboarding" -Method Post -Body $onboardBody -ContentType "application/json; charset=utf-8" -Headers @{ "Idempotency-Key" = $idemKey }
} catch {
    Write-Host "FAIL onboarding: $_"
    exit 1
}
$tenantId = $onboard.tenant_id
$profileId = $onboard.brand_profile_id
Write-Host "   tenant_id=$tenantId brand_profile_id=$profileId"

Write-Host "=== 2. POST /kb/bulk_ingest (30 items) ==="
$items = @()
for ($i = 1; $i -le 30; $i++) {
    $items += @{
        question = "FAQ question number $i about product and support?"
        answer = "This is answer $i. Product feature and support info."
        tags = @("faq", "s$i")
        source = "smoke_test"
    }
}
$bulkBody = @{ items = $items } | ConvertTo-Json -Depth 5
try {
    $bulk = Invoke-RestMethod -Uri "$base/kb/bulk_ingest?tenant_id=$tenantId" -Method Post -Body $bulkBody -ContentType "application/json; charset=utf-8"
} catch {
    Write-Host "FAIL bulk_ingest: $_"
    exit 1
}
Write-Host "   created=$($bulk.created) ids=$($bulk.ids.Count)"

Write-Host "=== 3. POST /kb/query ==="
$queryBody = @{ query = "product support"; tenant_id = $tenantId; top_k = 5 } | ConvertTo-Json
try {
    $query = Invoke-RestMethod -Uri "$base/kb/query" -Method Post -Body $queryBody -ContentType "application/json; charset=utf-8"
} catch {
    Write-Host "FAIL query: $_"
    exit 1
}
$ctxCount = if ($query.contexts) { $query.contexts.Count } else { 0 }
$citCount = if ($query.citations) { $query.citations.Count } else { 0 }
Write-Host "   contexts=$ctxCount citations=$citCount"
if ($ctxCount -eq 0) {
    Write-Host "   WARN: expected at least 1 context (query 'product support' matches FAQ text)"
}

Write-Host "=== 4. Idempotency: POST /onboarding again with same key ==="
try {
    $onboard2 = Invoke-RestMethod -Uri "$base/onboarding" -Method Post -Body $onboardBody -ContentType "application/json; charset=utf-8" -Headers @{ "Idempotency-Key" = $idemKey }
} catch {
    Write-Host "FAIL idempotent onboarding: $_"
    exit 1
}
if ($onboard2.tenant_id -ne $tenantId) {
    Write-Host "FAIL idempotency: tenant_id changed $tenantId -> $($onboard2.tenant_id)"
    exit 1
}
Write-Host "   OK same tenant_id=$($onboard2.tenant_id)"

Write-Host "Smoke test S2 PASSED."
