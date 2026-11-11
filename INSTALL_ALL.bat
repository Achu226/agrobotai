@echo off
REM =====================================================================
REM  AGROBOTAI - INSTALL EVERYTHING (double-click once on a new laptop)
REM
REM  Installs, skipping anything already present:
REM    Python 3.12 + .venv, PyTorch (GPU build on NVIDIA), all Python packages,
REM    Ollama + gemma3:4b advisor model, Whisper speech-to-text + 12 offline voices,
REM    Node.js + web dashboard, and (optional) Git, Java 17, Android SDK and
REM    Flutter to build the phone app (AGROBOTAI.apk).
REM
REM  Needs internet. First run: about 10 GB download, 20-60 minutes.
REM  Options:  INSTALL_ALL.bat check       -> only show what is installed / missing
REM            INSTALL_ALL.bat noflutter   -> skip the phone-app build tools
REM            INSTALL_ALL.bat flutter     -> install the phone-app build tools without asking
REM  Afterwards start the server with start.bat
REM =====================================================================
cd /d "%~dp0"
chcp 65001 >nul 2>&1
title AGROBOTAI installer

set "PS_ARGS="
if /i "%~1"=="check" set "PS_ARGS=-CheckOnly"
if /i "%~1"=="noflutter" set "PS_ARGS=-SkipFlutter"
if /i "%~1"=="flutter" set "PS_ARGS=-WithFlutter"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_all.ps1" %PS_ARGS%
set "RESULT=%errorlevel%"

echo.
if "%RESULT%"=="0" (
    if /i not "%~1"=="check" (
        choice /c YN /n /m "Start AGROBOTAI now? [Y/N] "
        if not errorlevel 2 (
            start "AGROBOTAI AI Server" cmd /c "%~dp0start.bat"
        )
    )
) else (
    echo Some steps need attention - read the list above. You can run INSTALL_ALL.bat again at any time;
    echo it resumes and skips everything that is already installed.
)
pause
exit /b %RESULT%
