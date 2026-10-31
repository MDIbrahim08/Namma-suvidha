Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  Running Namma Suvidha on ONE SINGLE LOCALHOST (Port 8000)" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan

$root = $PSScriptRoot

Write-Host "`n[1/2] Building frontend bundle..." -ForegroundColor Green
Set-Location "$root\frontend"
npm run build

Write-Host "`n[2/2] Starting Unified Server on http://127.0.0.1:8000 ..." -ForegroundColor Green
Set-Location "$root\backend"
Start-Process "http://127.0.0.1:8000/"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

