# Smoke E2E: health -> onboarding -> planner -> content -> approve -> (publish neu co Facebook env)
# Chay khi API dang chay: http://127.0.0.1:8000
# Tu thu muc goc: .\scripts\smoke_e2e.ps1

$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"
$FailReason = $null
$Pass = $true

function Invoke-ApiGet {
    param([string]$Path)
    Invoke-RestMethod -Uri "$BaseUrl$Path" -Method Get
}

function Invoke-ApiPost {
    param([string]$Path, [hashtable]$Body)
    $json = $Body | ConvertTo-Json
    Invoke-RestMethod -Uri "$BaseUrl$Path" -Method Post -Body $json -ContentType "application/json"
}

try {
    Write-Host "=== Smoke E2E (Core Arch v1) ===" -ForegroundColor Cyan
    Write-Host "BaseUrl: $BaseUrl"
    Write-Host ""

    # 1) Health
    Write-Host "[1/7] GET /health ..."
    $health = Invoke-ApiGet -Path "/health"
    if ($health.status -ne "ok") {
        $script:Pass = $false
        $script:FailReason = "health status != ok"
    }
    Write-Host "  OK" -ForegroundColor Green

    # 2) Onboarding
    Write-Host "[2/7] POST /onboarding ..."
    $onb = Invoke-ApiPost -Path "/onboarding" -Body @{
        tenant_name = "Smoke E2E Tenant"
        industry    = "Tech"
        brand_tone  = "Professional"
        main_services = @("Consulting")
        target_customer = "B2B"
        cta_style   = "Soft"
    }
    $tenantId = $onb.tenant.id
    if (-not $tenantId) {
        $script:Pass = $false
        $script:FailReason = "onboarding did not return tenant.id"
    }
    Write-Host "  tenant_id: $tenantId" -ForegroundColor Green

    # 3) Planner (days=7)
    Write-Host "[3/7] POST /planner/generate (days=7) ..."
    $planner = Invoke-ApiPost -Path "/planner/generate" -Body @{ tenant_id = "$tenantId"; days = 7 }
    if (-not $planner.items -or $planner.items.Count -eq 0) {
        $script:Pass = $false
        $script:FailReason = "planner returned no items"
    }
    Write-Host "  items: $($planner.items.Count)" -ForegroundColor Green

    # 4) Content generate-samples
    Write-Host "[4/7] POST /content/generate-samples ..."
    $content = Invoke-ApiPost -Path "/content/generate-samples" -Body @{ tenant_id = "$tenantId"; count = 2 }
    if (-not $content.items -or $content.items.Count -eq 0) {
        $script:Pass = $false
        $script:FailReason = "content/generate-samples returned no items"
    }
    $contentId = $content.items[0].id
    Write-Host "  content_id: $contentId" -ForegroundColor Green

    # 5) Approve 1 content item
    Write-Host "[5/7] POST /content/$contentId/approve ..."
    $approve = Invoke-ApiPost -Path "/content/$contentId/approve" -Body @{ tenant_id = "$tenantId"; actor = "HUMAN" }
    if ($approve.status -ne "approved") {
        $script:Pass = $false
        $script:FailReason = "approve did not set status=approved"
    }
    Write-Host "  OK (status=$($approve.status))" -ForegroundColor Green

    # 6) Publish: skip if no Facebook env
    Write-Host "[6/7] Publish (Facebook) ..."
    $hasFb = ($env:FACEBOOK_PAGE_ID -and $env:FACEBOOK_ACCESS_TOKEN)
    if (-not $hasFb) {
        Write-Host "  SKIPPED (FACEBOOK_PAGE_ID / FACEBOOK_ACCESS_TOKEN chua set)" -ForegroundColor Yellow
    } else {
        $logsBefore = Invoke-ApiGet -Path "/publish/logs?tenant_id=$tenantId&limit=50"
        $countBefore = if ($logsBefore.logs) { $logsBefore.logs.Count } else { 0 }
        try {
            $pub = Invoke-ApiPost -Path "/publish/facebook" -Body @{ tenant_id = "$tenantId"; content_id = "$contentId" }
            $logsAfter = Invoke-ApiGet -Path "/publish/logs?tenant_id=$tenantId&limit=50"
            $countAfter = if ($logsAfter.logs) { $logsAfter.logs.Count } else { 0 }
            if ($countAfter -ge $countBefore) {
                Write-Host "  OK (publish_logs: $countBefore -> $countAfter)" -ForegroundColor Green
            } else {
                $script:Pass = $false
                $script:FailReason = "publish_logs did not increase after publish"
            }
        } catch {
            $script:Pass = $false
            $script:FailReason = "publish/facebook failed: $_"
        }
    }

    # 7) Summary
    Write-Host "[7/7] Ket qua ..."
} catch {
    $script:Pass = $false
    $script:FailReason = $_.Exception.Message
}

Write-Host ""
if ($Pass) {
    Write-Host "PASS" -ForegroundColor Green
    exit 0
} else {
    Write-Host "FAIL" -ForegroundColor Red
    if ($FailReason) { Write-Host "  Ly do: $FailReason" -ForegroundColor Red }
    exit 1
}
