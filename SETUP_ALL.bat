@echo off
REM =====================================================================
REM  AGROBOTAI - complete setup for a new Windows 10/11 PC
REM  Installs only what is missing (safe to run again):
REM    Python 3.12 + all packages (CUDA PyTorch on NVIDIA GPUs), AI models check,
REM    Ollama + gemma3:4b advisor, voice models, web dashboard,
REM    Git + Flutter SDK + Java 17 + Android SDK, phone/firewall access, admin account.
REM
REM  Double-click to run.  Options:
REM    SETUP_ALL.bat -SkipFlutter   server only (no Flutter / Android tools)
REM    SETUP_ALL.bat -TestOnly      check everything, install nothing
REM  Needs internet. First run downloads about 10 GB and can take 30-60 minutes.
REM =====================================================================
cd /d "%~dp0"
chcp 65001 >nul 2>&1
title AGROBOTAI - Complete Setup
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_all.ps1" %*
set RESULT=%errorlevel%
echo.
if "%RESULT%"=="0" (
    echo Setup finished successfully.
) else (
    echo Setup finished with %RESULT% problem^(s^) - see the summary above.
)
pause
exit /b %RESULT%
