@echo off
title Botola Pro — Setup
color 0A
echo.
echo  ============================================================
echo   BOTOLA PRO — First-Time Setup
echo  ============================================================
echo.

REM ── Check Python 3.10 ──────────────────────────────────────────
python --version 2>nul | findstr /C:"3.10" >nul
if errorlevel 1 (
    echo  [ERROR] Python 3.10 not found in PATH.
    echo.
    echo  Please install Python 3.10 from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
echo  [OK] Python 3.10 found.

REM ── Create virtual environment ─────────────────────────────────
echo.
echo  [1/3] Creating virtual environment...
cd /d "%~dp0ChatBot_Botola"
if exist venv (
    echo       venv already exists, skipping.
) else (
    python -m venv venv
    echo  [OK] venv created.
)

REM ── Install dependencies ───────────────────────────────────────
echo.
echo  [2/3] Installing dependencies (this takes 2-5 minutes)...
venv\Scripts\pip.exe install --upgrade pip -q
venv\Scripts\pip.exe install ^
    fastapi==0.109.0 ^
    "uvicorn[standard]==0.27.0" ^
    python-multipart==0.0.6 ^
    pydantic==2.5.0 ^
    httpx==0.26.0 ^
    python-dotenv==1.0.0 ^
    "numpy==1.26.4" ^
    PyPDF2==3.0.1 ^
    python-docx==1.1.0 ^
    sqlalchemy==2.0.25 ^
    langdetect==1.0.9 ^
    redis==5.0.1 ^
    rank-bm25==0.2.2 ^
    "sentence-transformers==2.3.0" ^
    "faiss-cpu==1.7.4" ^
    -q

if errorlevel 1 (
    echo  [ERROR] pip install failed. Check your internet connection.
    pause
    exit /b 1
)
echo  [OK] All packages installed.

REM ── Verify models cache ────────────────────────────────────────
echo.
echo  [3/3] Checking bundled AI models...
if exist "%~dp0ChatBot_Botola\models_cache\hub" (
    echo  [OK] AI models found in bundle — no download needed.
) else (
    echo  [WARN] models_cache folder missing. Models will download on first run (~90 MB).
)

echo.
echo  ============================================================
echo   Setup complete! Run START.BAT to launch everything.
echo  ============================================================
echo.
pause
