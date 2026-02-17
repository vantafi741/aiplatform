# Push Revenue MVP Module 2 len GitHub: https://github.com/vantafi741/aiplatform.git
# Chay tu thu muc repo: .\scripts\push_revenue_mv2_to_github.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "REPO_PATH: $RepoRoot"
Set-Location $RepoRoot

# 1) Remote origin
$originUrl = "https://github.com/vantafi741/aiplatform.git"
$current = git remote get-url origin 2>$null
if (-not $current -or $current -ne $originUrl) {
    if ($current) { git remote remove origin }
    git remote add origin $originUrl
    Write-Host "Origin set: $originUrl"
}
git remote -v

# 2) Branch main (neu dang master)
$branch = git branch --show-current
if ($branch -eq "master") {
    git branch -m master main
    Write-Host "Renamed branch master -> main"
}
git branch

# 3) Xoa lock neu co
if (Test-Path "$RepoRoot\.git\index.lock") {
    Remove-Item "$RepoRoot\.git\index.lock" -Force
}

# 4) Add, commit, push
git add -A
git status --short
git commit -m "feat(revenue-mv2): content generator + migration 011"
git push -u origin main

# 5) Output
Write-Host ""
Write-Host "=== Ket qua ==="
git log -1 --oneline
git status
Get-ChildItem ai_content_director\alembic\versions -Filter "011*" | Select-Object Name
$commitHash = (git rev-parse HEAD)
Write-Host "Commit link: https://github.com/vantafi741/aiplatform/commit/$commitHash"
