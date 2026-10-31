@echo off
title Namma Suvidha Launcher
echo ===================================================
echo   Starting Namma Suvidha MVP (Backend + Frontend)
echo ===================================================
echo.

:: 1. Launch Backend in a dedicated window
echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "Namma Suvidha - Backend API (Port 8000)" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: 2. Launch Frontend in a dedicated window
echo [2/2] Starting React + Vite Frontend on http://127.0.0.1:5173 ...
start "Namma Suvidha - Frontend Web (Port 5173)" cmd /k "cd /d %~dp0frontend && npm run dev -- --host 127.0.0.1 --port 5173"

:: 3. Wait briefly and open browser
echo.
echo Waiting 3 seconds for services to initialize...
timeout /t 3 /nobreak >nul

echo Opening webapp in your default browser...
start http://127.0.0.1:5173/

echo.
echo ===================================================
echo   Both services are now running!
echo   Frontend : http://127.0.0.1:5173/
echo   Backend  : http://127.0.0.1:8000/docs
echo ===================================================

