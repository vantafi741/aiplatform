# Runbook: 1) Health 2) Onboarding (neu chua co TENANT_ID) 3) Batch 4) In summary + 40 dong dau moi JSON
# Chay tu repo root: .\scripts\run_full_evaluation.ps1
# Can: API dang chay (docker compose up), Python co script run_ai_quality_evaluation_batch.py

$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "=== 1) Health ===" -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
    $health | ConvertTo-Json -Depth 5
} catch {
    Write-Host "ERROR: Server khong phan hoi. Kiem tra: docker compose up -d (trong ai_content_director)" -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}

Write-Host "`n=== 2) TENANT_ID ===" -ForegroundColor Cyan
if (-not $env:TENANT_ID) {
    Write-Host "TENANT_ID chua set. Goi POST /onboarding de tao tenant..."
    $onboardBody = '{"tenant_name":"Eval Tenant","industry":"Marketing","brand_tone":"","main_services":["Content","Ads"],"target_customer":"SME","cta_style":""}'
    try {
        $onboard = Invoke-RestMethod -Uri "$BaseUrl/onboarding" -Method Post -Body $onboardBody -ContentType "application/json; charset=utf-8"
        $env:TENANT_ID = $onboard.tenant.id.ToString()
        Write-Host "Da tao tenant. TENANT_ID = $($env:TENANT_ID)"
    } catch {
        Write-Host "ERROR: Onboarding that bai: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "TENANT_ID = $env:TENANT_ID"
}

Write-Host "`n=== 3) Batch script ===" -ForegroundColor Cyan
Push-Location $RepoRoot
try {
    python $ScriptDir\run_ai_quality_evaluation_batch.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

$PlannerPath = Join-Path $ScriptDir "evaluation_planner_7d.json"
$ContentPath = Join-Path $ScriptDir "evaluation_content_6.json"

Write-Host "`n=== 4) First 40 lines: evaluation_planner_7d.json ===" -ForegroundColor Cyan
if (Test-Path $PlannerPath) {
    Get-Content $PlannerPath -Encoding UTF8 -TotalCount 40
} else {
    Write-Host "(file not found)"
}

Write-Host "`n=== 5) First 40 lines: evaluation_content_6.json ===" -ForegroundColor Cyan
if (Test-Path $ContentPath) {
    Get-Content $ContentPath -Encoding UTF8 -TotalCount 40
} else {
    Write-Host "(file not found)"
}

Write-Host "`nDone. Deliverables: health (above), Tenant ID = $env:TENANT_ID, console summary (above), first 40 lines of each JSON (above)." -ForegroundColor Green
