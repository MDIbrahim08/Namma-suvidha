@echo off
title Namma Suvidha - Single Localhost (Port 8000)
echo =============================================================
echo   Running Namma Suvidha on ONE SINGLE LOCALHOST (Port 8000)
echo =============================================================
echo.

echo [1/2] Building frontend bundle...
cd /d %~dp0frontend
call npm run build

echo.
echo [2/2] Starting Unified Server on http://127.0.0.1:8000 ...
cd /d %~dp0backend
start http://127.0.0.1:8000/
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

