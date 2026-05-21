@echo off
title Botola Pro — Launcher
color 0B
echo.
echo  ============================================================
echo   BOTOLA PRO — Starting Servers
echo  ============================================================
echo.

REM ── Check venv exists ──────────────────────────────────────────
if not exist "%~dp0ChatBot_Botola\venv\Scripts\uvicorn.exe" (
    echo  [ERROR] Virtual environment not found.
    echo  Please run SETUP.BAT first.
    echo.
    pause
    exit /b 1
)

REM ── Kill anything on 5500 / 8000 ──────────────────────────────
echo  Freeing ports 5500 and 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5500 ^| findstr LISTENING 2^>nul') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING 2^>nul') do taskkill /PID %%a /F >nul 2>&1
timeout /t 1 /nobreak >nul

REM ── Start static file server (Dashboard + Prototype) ──────────
echo  Starting Dashboard server on http://localhost:5500 ...
start "Dashboard-Server" cmd /k "python -m http.server 5500 --directory "%~dp0""

REM ── Start ChatBot API ──────────────────────────────────────────
echo  Starting ChatBot API on http://localhost:8000 ...
start "ChatBot-Server" cmd /k "cd /d "%~dp0ChatBot_Botola" && set HF_HOME=%~dp0ChatBot_Botola\models_cache && venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000"

echo.
echo  ============================================================
echo   Both servers are starting in separate windows.
echo.
echo   Dashboard  ^>  http://localhost:5500/dashboard.html
echo   Prototype  ^>  http://localhost:5500/Prototype/prototype copy.html
echo   ChatBot    ^>  http://localhost:8000/chatbot-test
echo.
echo   Wait ~30 seconds for the ChatBot window to show:
echo   "Application startup complete"
echo   Then open the links above in your browser.
echo  ============================================================
echo.

REM ── Open browser after short delay ────────────────────────────
timeout /t 5 /nobreak >nul
start "" "http://localhost:5500/dashboard.html"

echo  Browser opened. Keep this window and the two server
echo  windows open while using the platform.
echo.
pause
