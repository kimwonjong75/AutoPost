@echo off
cd /d "%~dp0"
start http://localhost:8503
streamlit run app.py
pause
