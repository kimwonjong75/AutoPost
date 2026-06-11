@echo off
cd /d "%~dp0"
REM 비밀 정보 커밋 차단 훅 활성화 (idempotent)
git config core.hooksPath .githooks >nul 2>&1
start http://localhost:8503
streamlit run app.py
pause
