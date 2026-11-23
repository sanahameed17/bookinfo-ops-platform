<#
  Prepares an OFFLINE Docker build (no internet needed inside docker build):
    1. frontend: npm run build                       -> frontend\dist\
    2. backend : pip download Linux wheels (cp311)   -> backend\wheels\
  Run it from the project folder, with the backend .venv activated, then: docker compose up --build
#>
$root = Split-Path $PSScriptRoot -Parent

Write-Host "1/2 Building the React app (npm run build)..." -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
npm run build
$feCode = $LASTEXITCODE
Pop-Location
if ($feCode -ne 0) { Write-Host "npm run build FAILED" -ForegroundColor Red; exit 1 }

Write-Host "2/2 Downloading Linux Python packages for the container (pip download)..." -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
if (Test-Path wheels) { Remove-Item wheels -Recurse -Force }
python -m pip download -r requirements.txt -d wheels `
    --only-binary=:all: --implementation cp --python-version 3.11 `
    --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux_2_28_x86_64 `
    --platform any -i https://pypi.tuna.tsinghua.edu.cn/simple
$beCode = $LASTEXITCODE
$count = (Get-ChildItem wheels -ErrorAction SilentlyContinue | Measure-Object).Count
Pop-Location
if ($beCode -ne 0) { Write-Host "pip download FAILED" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Ready: frontend\dist built, $count packages in backend\wheels" -ForegroundColor Green
Write-Host "Next:  docker compose up --build" -ForegroundColor Green
