@echo off
REM Development only: hot-reload on code changes, laptop-only (127.0.0.1). Models reload on every change.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
pause
