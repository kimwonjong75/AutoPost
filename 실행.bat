@echo off
cd /d "%~dp0"
title AutoPost

set "VENV_PY=.venv\Scripts\python.exe"

if exist "%VENV_PY%" goto run

echo ================================================
echo   AutoPost first-time setup (takes a few minutes)
echo   This runs only once.
echo ================================================
echo.

py -3.12 -V >nul 2>&1
if not errorlevel 1 goto makevenv

echo [1/3] Installing Python 3.12 via winget...
winget install --id Python.Python.3.12 -e --source winget --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
py -3.12 -V >nul 2>&1
if not errorlevel 1 goto makevenv
echo.
echo [ERROR] Python 3.12 not found.
echo   Install it from https://www.python.org/downloads/ then run this again.
echo.
pause
exit /b 1

:makevenv
echo [2/3] Creating virtual environment (.venv)...
py -3.12 -m venv .venv
if errorlevel 1 (
    echo [ERROR] venv creation failed.
    pause
    exit /b 1
)

echo [3/3] Installing packages (a few minutes, needs internet)...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] package install failed. See messages above.
    pause
    exit /b 1
)
echo.
echo   Setup complete!
echo.

:run
echo ================================================
echo   Starting AutoPost...
echo   The browser opens automatically when ready (http://localhost:8501)
echo   To stop the app, press Ctrl+C in this window.
echo ================================================
echo.
rem Wait for the server to be ready, then open the default browser
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i=0; $i -lt 60; $i++) { try { [void](Invoke-WebRequest 'http://localhost:8501/_stcore/health' -UseBasicParsing -TimeoutSec 1); Start-Process 'http://localhost:8501'; break } catch { Start-Sleep -Milliseconds 700 } }"
"%VENV_PY%" -m streamlit run app.py

echo.
echo App stopped.
pause
