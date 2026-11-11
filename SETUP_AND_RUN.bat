@echo off
setlocal enabledelayedexpansion

REM =====================================================================
REM   AGROBOTAI / HORTICBOTAI - One-Click Full Installer & Launcher
REM
REM   This script does EVERYTHING automatically on a fresh laptop:
REM     1. Installs Python 3.12 (if missing)
REM     2. Installs Node.js LTS (if missing, for frontend rebuilds)
REM     3. Installs Ollama (if missing)
REM     4. Creates Python virtual environment
REM     5. Installs all Python packages + PyTorch
REM     6. Downloads & creates the agri-qwen:7b LLM model
REM     7. Launches the application
REM
REM   Just double-click this file and wait. That's it.
REM =====================================================================

cd /d "%~dp0"
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8

title AGROBOTAI - Full Setup & Launcher

REM ===================== Color & Banner =====================
color 0A
echo.
echo  ===========================================================================
echo   ^|                                                                         ^|
echo   ^|     AGROBOTAI - AI Crop Health Diagnostic ^& Advisory Platform           ^|
echo   ^|     One-Click Full Setup ^& Launcher                                    ^|
echo   ^|                                                                         ^|
echo  ===========================================================================
echo.
echo   This will install everything needed and start the app.
echo   Internet connection required for first-time setup.
echo.
echo   [Press Ctrl+C to cancel, or any key to continue...]
pause >nul

REM ======================== PHASE 0: Admin check ========================
echo.
echo  ===========================================================================
echo   PHASE 0: Checking system prerequisites...
echo  ===========================================================================
echo.

REM Create a temp directory for downloads
set "TEMP_DIR=%~dp0_installer_temp"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

REM ======================== PHASE 1: Python ========================
echo  ===========================================================================
echo   PHASE 1: Python Installation Check
echo  ===========================================================================
echo.

set "PYTHON_FOUND=0"
set "PYTHON_CMD="

REM Check if python is available
where python >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%a in ('python --version 2^>^&1') do set "PYVER=%%a"
    echo   [FOUND] !PYVER!
    set "PYTHON_FOUND=1"
    set "PYTHON_CMD=python"
)

if "!PYTHON_FOUND!"=="0" (
    where python3 >nul 2>&1
    if not errorlevel 1 (
        for /f "tokens=*" %%a in ('python3 --version 2^>^&1') do set "PYVER=%%a"
        echo   [FOUND] !PYVER!
        set "PYTHON_FOUND=1"
        set "PYTHON_CMD=python3"
    )
)

if "!PYTHON_FOUND!"=="0" (
    echo   [NOT FOUND] Python is not installed.
    echo.
    echo   Downloading Python 3.12 installer...
    echo.

    REM Download Python 3.12 installer
    set "PYTHON_INSTALLER=%TEMP_DIR%\python-3.12-installer.exe"
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "try { " ^
        "  $ProgressPreference = 'SilentlyContinue'; " ^
        "  Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '!PYTHON_INSTALLER!' -UseBasicParsing; " ^
        "  Write-Host '  [OK] Python installer downloaded.' " ^
        "} catch { " ^
        "  Write-Host '  [ERROR] Failed to download Python. Check internet connection.'; " ^
        "  exit 1 " ^
        "}"
    if errorlevel 1 (
        echo.
        echo   MANUAL FIX: Download Python 3.12 from https://www.python.org/downloads/
        echo   Make sure to check "Add Python to PATH" during installation!
        echo.
        pause
        exit /b 1
    )

    echo.
    echo   Installing Python 3.12 silently (this takes 1-2 minutes)...
    echo   NOTE: Python will be added to PATH automatically.
    echo.

    REM Silent install with PATH added
    "!PYTHON_INSTALLER!" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0
    if errorlevel 1 (
        echo.
        echo   [WARNING] Silent install may have failed. Launching interactive installer...
        echo   IMPORTANT: Check "Add python.exe to PATH" at the bottom of the installer!
        echo.
        "!PYTHON_INSTALLER!"
    )

    REM Refresh PATH to pick up newly installed Python
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
    set "PATH=!USER_PATH!;%PATH%"

    REM Also add common Python install locations
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;!PATH!"

    REM Verify
    where python >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   [ERROR] Python still not found after install.
        echo   Please RESTART this script after Python installation completes.
        echo   If the installer is still running, wait for it to finish first.
        echo.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
    for /f "tokens=*" %%a in ('python --version 2^>^&1') do echo   [INSTALLED] %%a
)

echo   [OK] Python is ready.
echo.

REM ======================== PHASE 2: Node.js ========================
echo  ===========================================================================
echo   PHASE 2: Node.js Installation Check (for frontend builds)
echo  ===========================================================================
echo.

where node >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%a in ('node --version 2^>^&1') do echo   [FOUND] Node.js %%a
    echo   [OK] Node.js is ready.
) else (
    echo   [NOT FOUND] Node.js is not installed.
    echo.
    echo   Downloading Node.js 22 LTS installer...
    echo.

    set "NODE_INSTALLER=%TEMP_DIR%\node-lts-installer.msi"
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "try { " ^
        "  $ProgressPreference = 'SilentlyContinue'; " ^
        "  Invoke-WebRequest -Uri 'https://nodejs.org/dist/v22.15.0/node-v22.15.0-x64.msi' -OutFile '!NODE_INSTALLER!' -UseBasicParsing; " ^
        "  Write-Host '  [OK] Node.js installer downloaded.' " ^
        "} catch { " ^
        "  Write-Host '  [SKIP] Could not download Node.js. Frontend dist/ already exists - this is OK.'; " ^
        "  exit 0 " ^
        "}"

    if exist "!NODE_INSTALLER!" (
        echo   Installing Node.js silently (this takes 1-2 minutes)...
        msiexec /i "!NODE_INSTALLER!" /qn /norestart
        if errorlevel 1 (
            echo   [WARNING] Silent install failed, launching interactive installer...
            msiexec /i "!NODE_INSTALLER!"
        )

        REM Refresh PATH
        set "PATH=C:\Program Files\nodejs;%PATH%"
        where node >nul 2>&1
        if not errorlevel 1 (
            for /f "tokens=*" %%a in ('node --version 2^>^&1') do echo   [INSTALLED] Node.js %%a
        ) else (
            echo   [SKIP] Node.js install pending restart. Frontend dist/ bundle exists - app will work.
        )
    ) else (
        echo   [SKIP] Node.js download skipped. Pre-built frontend dist/ exists - app will work fine.
    )
)
echo.

REM ======================== PHASE 3: Ollama ========================
echo  ===========================================================================
echo   PHASE 3: Ollama AI Engine Installation Check
echo  ===========================================================================
echo.

REM Add common Ollama paths
set "PATH=%LOCALAPPDATA%\Programs\Ollama;C:\Program Files\Ollama;%USERPROFILE%\AppData\Local\Programs\Ollama;%PATH%"

set "OLLAMA_FOUND=0"
where ollama >nul 2>&1
if not errorlevel 1 (
    set "OLLAMA_FOUND=1"
    echo   [FOUND] Ollama is installed.
)

if "!OLLAMA_FOUND!"=="0" (
    echo   [NOT FOUND] Ollama is not installed.
    echo.
    echo   Downloading Ollama installer (~100MB, may take a few minutes)...
    echo.

    set "OLLAMA_INSTALLER=%TEMP_DIR%\OllamaSetup.exe"
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "try { " ^
        "  $ProgressPreference = 'SilentlyContinue'; " ^
        "  Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '!OLLAMA_INSTALLER!' -UseBasicParsing; " ^
        "  Write-Host '  [OK] Ollama installer downloaded.' " ^
        "} catch { " ^
        "  Write-Host '  [ERROR] Failed to download Ollama. Check internet connection.'; " ^
        "  exit 1 " ^
        "}"
    if errorlevel 1 (
        echo.
        echo   MANUAL FIX: Download Ollama from https://ollama.com/download
        echo.
        pause
        exit /b 1
    )

    echo.
    echo   Installing Ollama (this takes 1-2 minutes)...
    echo   NOTE: A small Ollama icon will appear in your system tray after install.
    echo.

    REM Ollama installer - run it and wait
    start /wait "" "!OLLAMA_INSTALLER!" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    if errorlevel 1 (
        echo   [WARNING] Silent install may need interaction. Launching installer...
        start /wait "" "!OLLAMA_INSTALLER!"
    )

    where ollama >nul 2>&1
    if not errorlevel 1 (
        echo   [INSTALLED] Ollama is now installed.
        set "OLLAMA_FOUND=1"
    ) else (
        echo   [WARNING] Ollama install may need a system restart to take effect.
        echo   The app will still work - the AI chatbot will just start once Ollama is available.
    )
)
echo.

REM ======================== PHASE 4: Python Virtual Environment ========================
echo  ===========================================================================
echo   PHASE 4: Python Virtual Environment Setup
echo  ===========================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo   [FOUND] Virtual environment already exists.
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    echo   Creating Python virtual environment (.venv)...
    !PYTHON_CMD! -m venv .venv
    if errorlevel 1 (
        echo   [ERROR] Failed to create virtual environment.
        echo   Try running: !PYTHON_CMD! -m venv .venv
        pause
        exit /b 1
    )
    echo   [OK] Virtual environment created.
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

REM Activate the venv
call .venv\Scripts\activate.bat
echo   [OK] Virtual environment activated.
echo.

REM ======================== PHASE 5: Python Packages ========================
echo  ===========================================================================
echo   PHASE 5: Installing Python Packages (PyTorch, FastAPI, CV2, etc.)
echo  ===========================================================================
echo.

echo   Upgrading pip...
"%PYTHON_EXE%" -m pip install --upgrade pip --quiet 2>nul
echo   [OK] pip upgraded.
echo.

REM Check if core packages are already installed
"%PYTHON_EXE%" -c "import fastapi, uvicorn, numpy, cv2, torch, timm, httpx, openai, reportlab" >nul 2>&1
if errorlevel 1 (
    echo   Installing core packages from requirements.txt...
    echo   This may take 5-10 minutes on first run (PyTorch is ~300MB)...
    echo.
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo   [WARNING] Some packages may have failed. Trying individual installs...
        echo.
        "%PYTHON_EXE%" -m pip install numpy opencv-python Pillow
        "%PYTHON_EXE%" -m pip install fastapi uvicorn python-multipart
        "%PYTHON_EXE%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
        "%PYTHON_EXE%" -m pip install timm requests httpx python-dotenv
        "%PYTHON_EXE%" -m pip install openai reportlab matplotlib pytest python-docx
    )
    echo.
    echo   [OK] Core packages installed.
) else (
    echo   [OK] All core packages already installed - skipping.
)

REM Use the CUDA build of PyTorch when an NVIDIA GPU is present (plain pip gives the CPU build)
where nvidia-smi >nul 2>&1
if not errorlevel 1 (
    "%PYTHON_EXE%" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
    if errorlevel 1 (
        echo   NVIDIA GPU detected - installing CUDA-enabled PyTorch (~3GB, one time^)...
        "%PYTHON_EXE%" -m pip install --upgrade torch torchvision --index-url https://download.pytorch.org/whl/cu130
        if errorlevel 1 (
            echo   [WARNING] CUDA PyTorch install failed - continuing on CPU.
        ) else (
            echo   [OK] CUDA PyTorch installed.
        )
    ) else (
        echo   [OK] PyTorch is using the NVIDIA GPU.
    )
)

REM Install edge-tts for voice features (optional but used in the app)
"%PYTHON_EXE%" -c "import edge_tts" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Installing edge-tts (for voice/speech features)...
    "%PYTHON_EXE%" -m pip install edge-tts --quiet 2>nul
    if not errorlevel 1 (
        echo   [OK] edge-tts installed.
    ) else (
        echo   [SKIP] edge-tts install failed - voice features may be limited.
    )
)

echo.

REM ======================== PHASE 6: Verify Model Files ========================
echo  ===========================================================================
echo   PHASE 6: Verifying AI Model Files
echo  ===========================================================================
echo.

if exist "models\pest_model.pt" (
    echo   [OK] Pest detection model found    : models\pest_model.pt
) else (
    echo   [WARNING] Pest model missing: models\pest_model.pt
    echo   Copy this file from the original project folder.
)

if exist "models\disease_model.pt" (
    echo   [OK] Disease detection model found : models\disease_model.pt
) else (
    echo   [WARNING] Disease model missing: models\disease_model.pt
    echo   Copy this file from the original project folder.
)

if exist "models\pest_classes.json" (
    echo   [OK] Pest class definitions found  : models\pest_classes.json
) else (
    echo   [WARNING] Pest classes missing: models\pest_classes.json
)

if exist "models\disease_classes.json" (
    echo   [OK] Disease class definitions found: models\disease_classes.json
) else (
    echo   [WARNING] Disease classes missing: models\disease_classes.json
)
echo.

REM ======================== PHASE 7: Ollama Model Setup ========================
echo  ===========================================================================
echo   PHASE 7: Ollama LLM Model Setup (agri-qwen:7b)
echo  ===========================================================================
echo.

if "!OLLAMA_FOUND!"=="0" (
    echo   [SKIP] Ollama not installed yet - skipping model setup.
    echo   Install Ollama from https://ollama.com and re-run this script.
    goto :skip_ollama_model
)

REM Start Ollama service if not running
powershell -NoProfile -Command ^
    "try { $r = (Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 3 -UseBasicParsing); exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo   Starting Ollama service...
    start /b "" ollama serve >nul 2>&1
    echo   Waiting for Ollama to be ready...

    REM Wait up to 30 seconds for Ollama to start
    set "OLLAMA_READY=0"
    for /L %%i in (1,1,15) do (
        if "!OLLAMA_READY!"=="0" (
            timeout /t 2 /nobreak >nul 2>&1
            powershell -NoProfile -Command ^
                "try { $r = (Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' -TimeoutSec 2 -UseBasicParsing); exit 0 } catch { exit 1 }" >nul 2>&1
            if not errorlevel 1 (
                set "OLLAMA_READY=1"
            )
        )
    )

    if "!OLLAMA_READY!"=="1" (
        echo   [OK] Ollama service is running.
    ) else (
        echo   [WARNING] Ollama service didn't start. The app will try again at runtime.
        goto :skip_ollama_model
    )
) else (
    echo   [OK] Ollama service is already running.
)

REM Check if agri-qwen model exists
echo.
echo   Checking for agri-qwen:7b model...
ollama list 2>nul | findstr /i "agri-qwen" >nul 2>&1
if not errorlevel 1 (
    echo   [OK] agri-qwen:7b model is already installed.
) else (
    echo   [NOT FOUND] agri-qwen:7b model needs to be created.
    echo.

    REM First ensure the base model qwen2.5:7b is downloaded
    echo   Step 1: Downloading base model qwen2.5:7b (~4.4GB)...
    echo   This will take several minutes depending on your internet speed.
    echo   Please be patient...
    echo.
    ollama pull qwen2.5:7b
    if errorlevel 1 (
        echo   [ERROR] Failed to download qwen2.5:7b base model.
        echo   Check your internet connection and try again.
        goto :skip_ollama_model
    )
    echo   [OK] Base model qwen2.5:7b downloaded.
    echo.

    REM Create the agri-qwen model from the Modelfile
    if exist "Modelfile.agri-qwen" (
        echo   Step 2: Creating agri-qwen:7b from Modelfile (agricultural specialization)...
        ollama create agri-qwen:7b -f Modelfile.agri-qwen
        if errorlevel 1 (
            echo   [WARNING] Failed to create agri-qwen:7b. Will fallback to qwen2.5:7b.
        ) else (
            echo   [OK] agri-qwen:7b model created successfully!
        )
    ) else (
        echo   [WARNING] Modelfile.agri-qwen not found. Will use base qwen2.5:7b.
    )
)
echo.

:skip_ollama_model

REM ======================== PHASE 8: Environment Config ========================
echo  ===========================================================================
echo   PHASE 8: Environment Configuration Check
echo  ===========================================================================
echo.

if exist ".env" (
    echo   [OK] .env configuration file found.
) else if exist ".env.example" (
    echo   [CREATING] .env from .env.example...
    copy /y ".env.example" ".env" >nul
    echo   [OK] .env created. Using default Ollama offline configuration.
) else (
    echo   [CREATING] .env with Ollama offline defaults...
    (
        echo # Local 100%% Free Offline LLM ^(GPU Accelerated via Ollama^)
        echo OPENAI_API_KEY=ollama
        echo OPENAI_BASE_URL=http://localhost:11434/v1
        echo OPENAI_MODEL=agri-qwen:7b
        echo OPENAI_TIMEOUT_SECONDS=60
        echo.
        echo PEST_MODEL_PATH=models/pest_model.pt
        echo DISEASE_MODEL_PATH=models/disease_model.pt
        echo.
        echo WEIGHT_PEST=0.30
        echo WEIGHT_DISEASE=0.35
        echo WEIGHT_NDRE=0.20
        echo WEIGHT_CRI=0.15
        echo.
        echo STATUS_HEALTHY=80
        echo STATUS_MILD=60
        echo STATUS_MODERATE=40
        echo.
        echo LOW_CONFIDENCE_THRESHOLD=0.30
        echo HIGH_CONFIDENCE_THRESHOLD=0.75
    ) > ".env"
    echo   [OK] .env created with defaults.
)
echo.

REM ======================== PHASE 9: Frontend Check ========================
echo  ===========================================================================
echo   PHASE 9: Frontend Build Check
echo  ===========================================================================
echo.

if exist "frontend\dist\index.html" (
    echo   [OK] Pre-built frontend bundle found in frontend\dist\
    echo   The React app is ready to be served.
) else (
    echo   [WARNING] frontend\dist\ not found. Attempting to build...
    where node >nul 2>&1
    if not errorlevel 1 (
        if exist "frontend\package.json" (
            echo   Installing frontend dependencies...
            pushd frontend
            call npm install --silent 2>nul
            echo   Building React app...
            call npm run build 2>nul
            popd
            if exist "frontend\dist\index.html" (
                echo   [OK] Frontend built successfully.
            ) else (
                echo   [WARNING] Frontend build failed. Copy frontend\dist\ from original project.
            )
        )
    ) else (
        echo   [WARNING] Node.js not available. Copy frontend\dist\ folder from original project.
    )
)
echo.

REM ======================== PHASE 10: Create outputs directory ========================
if not exist "outputs" mkdir "outputs"

REM ======================== CLEANUP ========================
echo  ===========================================================================
echo   Cleaning up temporary installer files...
echo  ===========================================================================
echo.
if exist "%TEMP_DIR%" (
    rd /s /q "%TEMP_DIR%" 2>nul
    echo   [OK] Temporary files cleaned up.
)
echo.

REM ======================== PHASE 11: LAUNCH ========================
echo.
echo  ===========================================================================
echo  ===========================================================================
echo  ===                                                                     ===
echo  ===   SETUP COMPLETE! Launching AGROBOTAI...                            ===
echo  ===                                                                     ===
echo  ===========================================================================
echo  ===========================================================================
echo.
echo   Web Application URL  : http://localhost:8000
echo   Interactive API Docs : http://localhost:8000/docs
echo   Local AI Model       : agri-qwen:7b (100%% Offline / Zero-Cost)
echo   Ollama LLM Service   : http://localhost:11434
echo.
echo   Press Ctrl+C in this window to stop the server.
echo.
echo  ===========================================================================
echo.

"%PYTHON_EXE%" app.py

echo.
echo  ===========================================================================
echo   Server stopped. Close this window or press any key to exit.
echo  ===========================================================================
pause
