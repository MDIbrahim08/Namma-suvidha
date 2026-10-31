Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Starting Namma Suvidha (Backend + Frontend)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$root = $PSScriptRoot

# 1. Start backend in a new PowerShell window
Write-Host "[1/2] Starting Backend API on http://127.0.0.1:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

# 2. Start frontend in a new PowerShell window
Write-Host "[2/2] Starting Frontend App on http://127.0.0.1:5173 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev -- --host 127.0.0.1 --port 5173"

# 3. Open browser
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173/"

Write-Host "Both servers launched and browser opened!" -ForegroundColor Yellow

