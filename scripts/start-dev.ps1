<#
  Development start: opens the backend and the frontend in two PowerShell windows.
  Run once before:  backend: python -m venv .venv + pip install -r requirements-dev.txt
                    frontend: npm install
  Then open http://localhost:5173
#>
$root = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle='backend :8000'; cd '$backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle='frontend :5173'; cd '$frontend'; npm run dev"

Write-Host "Backend : http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
