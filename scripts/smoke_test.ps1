# Smoke test - chạy khi API đang chạy tại http://localhost:8000
# PowerShell: .\scripts\smoke_test.ps1

$base = "http://localhost:8000"

Write-Host "1. GET /health..."
$r = Invoke-RestMethod -Uri "$base/health" -Method Get
if ($r.status -ne "ok") { Write-Host "FAIL health"; exit 1 }
Write-Host "   OK"

Write-Host "2. POST /tenants..."
$body = '{"name":"Smoke Tenant","slug":"smoke-tenant"}'
$tenant = Invoke-RestMethod -Uri "$base/tenants" -Method Post -Body $body -ContentType "application/json"
$tenantId = $tenant.id
Write-Host "   tenant_id=$tenantId"

Write-Host "3. POST /jobs..."
$body = "{`"tenant_id`":`"$tenantId`",`"type`":`"smoke_test`",`"payload`":{`"step`":1}}"
$job = Invoke-RestMethod -Uri "$base/jobs" -Method Post -Body $body -ContentType "application/json"
$jobId = $job.id
Write-Host "   job_id=$jobId status=$($job.status)"

Write-Host "4. Waiting 4s for worker..."
Start-Sleep -Seconds 4

Write-Host "5. GET /jobs/$jobId..."
$job2 = Invoke-RestMethod -Uri "$base/jobs/$jobId" -Method Get
if ($job2.status -ne "success") { Write-Host "   FAIL expected status=success got $($job2.status)"; exit 1 }
Write-Host "   OK status=$($job2.status)"

Write-Host "Smoke test PASSED."
