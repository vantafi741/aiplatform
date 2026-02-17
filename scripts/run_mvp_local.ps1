# Run MVP local: env check -> venv (neu chua co) -> pip install -> alembic upgrade head -> uvicorn
# Chay tu thu muc goc repo: .\scripts\run_mvp_local.ps1
# Idempotent: venv tao 1 lan; pip install + alembic chay moi lan de dong bo.
# Can: Python 3.10+, PostgreSQL (DB ai_content_director), ai_content_director\.env

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$ACD = Join-Path $RepoRoot "ai_content_director"

if (-not (Test-Path $ACD)) {
    Write-Error "Khong tim thay thu muc: $ACD"
    exit 1
}

Write-Host "=== MVP Local (entrypoint: ai_content_director) ===" -ForegroundColor Cyan
Write-Host "Repo root: $RepoRoot"
Write-Host "ai_content_director: $ACD"
Write-Host ""

# 1) Kiem tra env
$envPath = Join-Path $ACD ".env"
$envOk = $false
if (Test-Path $envPath) {
    Write-Host "[OK] Ton tai $envPath" -ForegroundColor Green
    $envOk = $true
}
if ($env:DATABASE_URL) {
    Write-Host "[OK] DATABASE_URL da set (env)" -ForegroundColor Green
    $envOk = $true
}
if (-not $envOk) {
    Write-Host "[WARN] Chua co .env hoac DATABASE_URL. Copy ai_content_director\.env.example sang .env va dien DATABASE_URL." -ForegroundColor Yellow
    $confirm = Read-Host "Tiep tuc? (y/N)"
    if ($confirm -ne "y" -and $confirm -ne "Y") { exit 1 }
}

# 2) Venv
$venvPath = Join-Path $ACD ".venv"
$pyExe = Join-Path $venvPath "Scripts" "python.exe"
if (-not (Test-Path $pyExe)) {
    Write-Host "Tao venv: $venvPath ..."
    Set-Location $ACD
    python -m venv .venv
    if (-not (Test-Path $pyExe)) {
        Write-Error "Tao venv that bai. Kiem tra python trong PATH."
        exit 1
    }
    Set-Location $RepoRoot
}
Write-Host "[OK] Venv: $venvPath" -ForegroundColor Green

# 3) Dependencies (luon chay de dong bo deps, idempotent)
$reqPath = Join-Path $ACD "requirements.txt"
if (-not (Test-Path $reqPath)) {
    Write-Error "Khong tim thay $reqPath"
    exit 1
}
Write-Host "Cap nhat dependencies (pip install -r requirements.txt) ..."
& $pyExe -m pip install -r $reqPath -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install that bai."
    exit 1
}
Write-Host "[OK] Dependencies" -ForegroundColor Green

# 4) Migrate
Write-Host "Chay alembic upgrade head ..."
Push-Location $ACD
try {
    & $pyExe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Error "alembic upgrade head that bai. Kiem tra PostgreSQL va DATABASE_URL."
        exit 1
    }
    Write-Host "[OK] Migrations" -ForegroundColor Green
} finally {
    Pop-Location
}

# 5) Start uvicorn (foreground)
Write-Host ""
Write-Host "Khoi dong server: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Dung: Ctrl+C" -ForegroundColor Gray
Write-Host ""
Push-Location $ACD
try {
    & $pyExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}
