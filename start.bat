@echo off
setlocal enabledelayedexpansion

REM =====================================================================
REM  AGROBOTAI - laptop AI inference server for the phone app (LAN mode)
REM  Double-click to start. Close this window (or press Ctrl+C) to stop.
REM =====================================================================

cd /d "%~dp0"
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
title AGROBOTAI AI Server

echo =====================================================================
echo   AGROBOTAI - AI Crop Disease ^& Pest Inference Server
echo =====================================================================
echo.

REM ---- 1. Python ------------------------------------------------------
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo [1/6] Using virtual environment .venv
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python is not installed or not on PATH.
        echo         Install Python 3.12+ from https://www.python.org/downloads/ ^(tick "Add Python to PATH"^)
        echo         or run SETUP_AND_RUN.bat once for a full automatic install.
        pause
        exit /b 1
    )
    echo [1/6] Creating virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

REM ---- 2. Dependencies (installed only when something is missing) -------
echo [2/6] Checking Python packages ...
"%PYTHON_EXE%" -c "import fastapi, uvicorn, multipart, numpy, cv2, PIL, torch, torchvision, reportlab, dotenv, transformers, edge_tts" >nul 2>&1
if errorlevel 1 (
    echo       Some packages are missing - installing from requirements.txt ...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Package installation failed. Read the messages above, check the internet connection and retry.
        pause
        exit /b 1
    )
)

REM ---- 3. Configuration -----------------------------------------------
if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo [3/6] Created .env from .env.example - review it later for weather / sensor settings.
    )
) else (
    echo [3/6] Configuration .env found
)

REM ---- 4. Preflight: models, GPU, port, LAN address, firewall, admin -----
echo [4/6] Running startup checks ...
echo.
"%PYTHON_EXE%" scripts\preflight.py
set PREFLIGHT=%errorlevel%
echo.
if "%PREFLIGHT%"=="2" (
    echo [STOP] The server port is busy - AGROBOTAI is probably already running in another window.
    pause
    exit /b 2
)
if "%PREFLIGHT%"=="1" (
    echo [STOP] A required component is missing ^(see [FAIL] lines above^).
    pause
    exit /b 1
)
if "%PREFLIGHT%"=="3" (
    echo [5/6] Creating the first administrator account ^(needed to review farmer scans^)...
    "%PYTHON_EXE%" manage_users.py ensure-admin
    if errorlevel 1 (
        echo [ERROR] Administrator account was not created.
        pause
        exit /b 1
    )
) else (
    echo [5/6] Accounts OK
)

REM ---- 4b. Can phones on the Wi-Fi reach the server? (firewall / Public network) ----
"%PYTHON_EXE%" scripts\phone_access.py --check >nul 2>&1
if errorlevel 4 (
    echo.
    echo  !!! The phone app is BLOCKED by Windows Firewall ^(see [WARN] lines above^).
    echo      Fix: mark this Wi-Fi as a Private ^(home^) network and allow port 8000 for phones.
    echo      ^(Press N if you will connect the phone with a USB cable instead - that works without this fix.^)
    choice /c YN /n /m "     Fix it now? Windows will ask for admin permission. [Y/N] "
    if not errorlevel 2 (
        "%PYTHON_EXE%" scripts\phone_access.py --fix
    ) else (
        echo      Skipped - phones will not connect until this is fixed. Run start.bat again to retry.
    )
    echo.
)

REM ---- 5. Optional offline LLM advisor (Ollama) -------------------------
set "PATH=%LOCALAPPDATA%\Programs\Ollama;C:\Program Files\Ollama;%PATH%"
where ollama >nul 2>&1
if not errorlevel 1 (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
    if errorlevel 1 (
        echo       Starting Ollama for the offline AI advisor ...
        start "" /b ollama serve >nul 2>&1
    )
) else (
    echo       [Note] Ollama not installed - advice falls back to the built-in rule book ^(reported as such^).
)

REM ---- 5b. USB phone link: works even when the firewall blocks the Wi-Fi ----
REM  "adb reverse" makes 127.0.0.1:PORT on a USB-connected phone reach this laptop over the cable.
for /f %%p in ('"%PYTHON_EXE%" -c "from src.config import SERVER_PORT; print(SERVER_PORT)" 2^>nul') do set "AGROBOT_PORT_NUM=%%p"
if not defined AGROBOT_PORT_NUM set "AGROBOT_PORT_NUM=8000"
set "ADB_EXE="
if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" set "ADB_EXE=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not defined ADB_EXE (
    where adb >nul 2>&1
    if not errorlevel 1 set "ADB_EXE=adb"
)
if defined ADB_EXE (
    "!ADB_EXE!" reverse tcp:!AGROBOT_PORT_NUM! tcp:!AGROBOT_PORT_NUM! >nul 2>&1
    if not errorlevel 1 (
        echo       USB phone link ON - the phone on the USB cable reaches this server ^(no Wi-Fi/firewall needed^).
    ) else (
        echo       [Note] No phone on USB. To use the cable link: enable USB debugging, plug in, run start.bat again.
    )
)

REM ---- 6. Start the server on the LAN -----------------------------------
echo.
echo [6/6] Starting server on all network interfaces ^(LAN mode, no auto-reload^).
echo       Laptop dashboard : http://localhost:8000   ^(port from AGROBOT_PORT in .env, default 8000^)
echo       Phone app        : open AGROBOTAI on the phone ^(same Wi-Fi^) - it finds this laptop automatically.
echo                          If asked for an address, use the PHONE SERVER URL shown in the box below.
echo       Health check     : http://localhost:8000/health
echo       Logs             : logs\server.log
echo       Stop the server  : press Ctrl+C or close this window
echo =====================================================================
echo.

"%PYTHON_EXE%" app.py --lan
set EXITCODE=%errorlevel%
echo.
if not "%EXITCODE%"=="0" echo [ERROR] The server stopped with exit code %EXITCODE%. Read the error above.
pause
exit /b %EXITCODE%
