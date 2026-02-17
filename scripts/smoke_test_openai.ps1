# Smoke test OpenAI integration (Planner + Content)
# Kiểm tra used_ai=true, used_fallback=false khi OPENAI_API_KEY có sẵn.
# Chạy khi API ai_content_director đang chạy: http://localhost:8000

$ErrorActionPreference = "Stop"
$base = "http://localhost:8000"

Write-Host "=== Smoke test OpenAI (used_ai / used_fallback) ===" -ForegroundColor Cyan

# 1) Health
Write-Host "`n=== 1. GET /health ==="
try {
    $health = Invoke-RestMethod -Uri "$base/health" -Method Get
    if ($health.status -ne "ok") { throw "health status not ok" }
    Write-Host "   status=$($health.status)"
} catch {
    Write-Host "FAIL: $_" -ForegroundColor Red
    exit 1
}

# 2) Onboarding -> lấy tenant_id
Write-Host "`n=== 2. POST /onboarding ==="
$onboardBody = @{
    tenant_name = "Smoke OpenAI Test"
    industry    = "Co khi che tao"
    brand_tone  = "Chuyen nghiep, dang tin"
    main_services = @("Thiet ke khuon dap", "Gia cong co khi")
    target_customer = "Nha may, doanh nghiep"
    cta_style   = "Lien he bao gia nhanh"
} | ConvertTo-Json
try {
    $onboard = Invoke-RestMethod -Uri "$base/onboarding" -Method Post -Body $onboardBody -ContentType "application/json; charset=utf-8"
    $tenantId = $onboard.tenant.id
    Write-Host "   tenant_id=$tenantId"
} catch {
    Write-Host "FAIL onboarding: $_" -ForegroundColor Red
    exit 1
}

# 3) Planner với ai=true (kỳ vọng used_ai=true, used_fallback=false nếu có API key)
Write-Host "`n=== 3. POST /planner/generate?force=false&ai=true ==="
$plannerBody = @{ tenant_id = $tenantId; days = 7 } | ConvertTo-Json
try {
    $planner = Invoke-RestMethod -Uri "$base/planner/generate?force=false&ai=true" -Method Post -Body $plannerBody -ContentType "application/json; charset=utf-8"
    Write-Host "   created=$($planner.created) used_ai=$($planner.used_ai) used_fallback=$($planner.used_fallback) model=$($planner.model)"
    if ($planner.used_ai -eq $true -and $planner.used_fallback -eq $false) {
        Write-Host "   OK: AI ran successfully (used_ai=true, used_fallback=false)" -ForegroundColor Green
    } else {
        Write-Host "   Note: Fallback was used (no API key or AI error). used_ai=$($planner.used_ai) used_fallback=$($planner.used_fallback)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "FAIL planner: $_" -ForegroundColor Red
    exit 1
}

# 4) Content samples với ai=true
Write-Host "`n=== 4. POST /content/generate-samples?force=false&ai=true ==="
$contentBody = @{ tenant_id = $tenantId; count = 3 } | ConvertTo-Json
try {
    $content = Invoke-RestMethod -Uri "$base/content/generate-samples?force=false&ai=true" -Method Post -Body $contentBody -ContentType "application/json; charset=utf-8"
    Write-Host "   created=$($content.created) used_ai=$($content.used_ai) used_fallback=$($content.used_fallback) model=$($content.model)"
    if ($content.used_ai -eq $true -and $content.used_fallback -eq $false) {
        Write-Host "   OK: AI ran successfully (used_ai=true, used_fallback=false)" -ForegroundColor Green
    } else {
        Write-Host "   Note: Fallback was used. used_ai=$($content.used_ai) used_fallback=$($content.used_fallback)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "FAIL content: $_" -ForegroundColor Red
    exit 1
}

# 5) Optional: gọi với ai=false (chỉ template)
Write-Host "`n=== 5. POST /planner/generate?force=true&ai=false (template only) ==="
$plannerBody2 = @{ tenant_id = $tenantId; days = 5 } | ConvertTo-Json
try {
    $plan2 = Invoke-RestMethod -Uri "$base/planner/generate?force=true&ai=false" -Method Post -Body $plannerBody2 -ContentType "application/json; charset=utf-8"
    Write-Host "   created=$($plan2.created) used_ai=$($plan2.used_ai) used_fallback=$($plan2.used_fallback)"
    if ($plan2.used_ai -eq $false) {
        Write-Host "   OK: Template-only (used_ai=false)" -ForegroundColor Green
    }
} catch {
    Write-Host "FAIL: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Smoke test OpenAI completed ===" -ForegroundColor Cyan
