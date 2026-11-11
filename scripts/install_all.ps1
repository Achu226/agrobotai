<#
  AGROBOTAI - one-click installer (run through INSTALL_ALL.bat).

  Installs everything the project needs, skipping whatever is already present:
    1. Python 3.12 + virtual environment (.venv)
    2. PyTorch (CUDA build when an NVIDIA GPU is present) + all Python packages
    3. Ollama + the farm-advisor LLM (gemma3:4b)
    4. Local speech models: Whisper large-v3-turbo + 12 MMS voices
    5. Node.js + the web dashboard build
    6. (optional) Git, Java 17, Android SDK, Flutter -> builds the phone app APK
    7. .env, folders, final checks

  Switches:  -CheckOnly   report what is installed / missing, change nothing
             -SkipFlutter  never ask about Flutter / Android
             -WithFlutter  install Flutter / Android without asking
#>
param([switch]$CheckOnly, [switch]$SkipFlutter, [switch]$WithFlutter)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is 10x faster without the progress bar
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

New-Item -ItemType Directory -Force -Path "$Root\logs", "$Root\outputs", "$Root\_installer_temp" | Out-Null
$LogFile = "$Root\logs\install_$(Get-Date -Format yyyyMMdd_HHmmss).log"
if (-not $CheckOnly) { Start-Transcript -Path $LogFile | Out-Null }

$script:Problems = @()
$Temp = "$Root\_installer_temp"
$Venv = "$Root\.venv"
$VenvPy = "$Venv\Scripts\python.exe"

function Step($n, $text) { Write-Host ""; Write-Host "[$n] $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "    [OK]   $text" -ForegroundColor Green }
function Info($text) { Write-Host "    ..     $text" }
function Warn($text) { Write-Host "    [WARN] $text" -ForegroundColor Yellow; $script:Problems += $text }
function Fail($text) { Write-Host "    [FAIL] $text" -ForegroundColor Red; $script:Problems += $text }

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $extra = "$env:LOCALAPPDATA\Programs\Ollama;C:\Program Files\nodejs;C:\Program Files\Git\cmd;$env:USERPROFILE\development\flutter\bin;$env:LOCALAPPDATA\Android\Sdk\platform-tools"
    $env:Path = "$machine;$user;$extra"
}

function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

function Run($exe, [string[]]$argList) {
    # Runs a program, shows its output, returns its exit code (never throws on non-zero)
    $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & $exe @argList 2>&1 | ForEach-Object { Write-Host "           $_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return $code
}

function Winget-Install($id, $name) {
    if (-not (Have "winget")) { return $false }
    Info "Installing $name with winget (Windows may ask for permission)..."
    $code = Run "winget" @("install", "--id", $id, "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements")
    Refresh-Path
    return ($code -eq 0 -or $code -eq -1978335189)   # -1978335189 = already installed
}

function Download($url, $file) {
    Info "Downloading $url"
    Invoke-WebRequest -Uri $url -OutFile $file -UseBasicParsing
}

function Python-Version($exe, [string[]]$pre = @()) {
    try {
        $v = & $exe @pre -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 10) { return $v }
    } catch {}
    return $null
}

Refresh-Path
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host "  AGROBOTAI installer $(if ($CheckOnly) { '(CHECK ONLY - nothing will be changed)' })" -ForegroundColor Green
Write-Host "  Project: $Root"
Write-Host "====================================================================="

# --------------------------------------------------------------------------- 1. Python
Step 1 "Python and virtual environment"
$venvOk = (Test-Path $VenvPy) -and (Python-Version $VenvPy)
if ($venvOk) {
    Ok "Virtual environment .venv (Python $(Python-Version $VenvPy))"
} else {
    $basePy = $null; $basePre = @()
    if (Have "py") { foreach ($v in "3.12", "3.13", "3.14", "3.11", "3.10") { if (Python-Version "py" @("-$v")) { $basePy = "py"; $basePre = @("-$v"); break } } }
    if (-not $basePy -and (Have "python") -and (Python-Version "python")) { $basePy = "python" }
    if (-not $basePy) {
        if ($CheckOnly) { Warn "Python 3.10+ is not installed" }
        else {
            if (-not (Winget-Install "Python.Python.3.12" "Python 3.12")) {
                $inst = "$Temp\python-3.12.10-amd64.exe"
                Download "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" $inst
                Info "Installing Python 3.12 for this user..."
                Start-Process $inst -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1" -Wait
                Refresh-Path
            }
            if ((Have "py") -and (Python-Version "py" @("-3.12"))) { $basePy = "py"; $basePre = @("-3.12") }
            elseif (Python-Version "python") { $basePy = "python" }
            else { Fail "Python installation did not succeed. Install Python 3.12 from python.org (tick 'Add to PATH') and run this again."; }
        }
    } else { Ok "Python found: $basePy $($basePre -join ' ') ($(Python-Version $basePy $basePre))" }
    if ($basePy -and -not $CheckOnly) {
        if (Test-Path $Venv) { Info "The existing .venv is broken (e.g. the project was moved) - recreating it"; Remove-Item -Recurse -Force $Venv }
        Info "Creating virtual environment .venv"
        Run $basePy ($basePre + @("-m", "venv", $Venv)) | Out-Null
        if (Test-Path $VenvPy) { Ok "Created .venv" } else { Fail "Could not create the virtual environment" }
    } elseif ($CheckOnly) { Warn "Virtual environment .venv is missing or broken" }
}

# --------------------------------------------------------------------------- 2. Python packages
Step 2 "Python packages (PyTorch, FastAPI, OpenCV, Whisper/voices, reports...)"
$hasNvidia = [bool](Get-Command nvidia-smi -ErrorAction SilentlyContinue)
if (Test-Path $VenvPy) {
    $torchState = & $VenvPy -c "import torch; print('cuda' if torch.cuda.is_available() else 'cpu', torch.__version__)" 2>$null
    if ($LASTEXITCODE -ne 0) { $torchState = $null }
    if ($CheckOnly) {
        if ($torchState) { Ok "PyTorch $torchState" } else { Warn "PyTorch is not installed" }
        if ($hasNvidia -and $torchState -and $torchState -notlike "cuda*") { Warn "NVIDIA GPU present but PyTorch is the CPU build" }
    } else {
        Run $VenvPy @("-m", "pip", "install", "--upgrade", "pip", "--quiet") | Out-Null
        if ($hasNvidia -and ($torchState -notlike "cuda*")) {
            foreach ($cu in "cu130", "cu128", "cu126") {
                Info "Installing PyTorch with CUDA ($cu) for the NVIDIA GPU (~3 GB, one time)..."
                Run $VenvPy @("-m", "pip", "install", "--upgrade", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/$cu") | Out-Null
                $torchState = & $VenvPy -c "import torch; print('cuda' if torch.cuda.is_available() else 'cpu', torch.__version__)" 2>$null
                if ($torchState -like "cuda*") { break }
                Info "CUDA not usable with $cu on this driver - trying an older CUDA build"
            }
        } elseif (-not $torchState) {
            Info "No NVIDIA GPU - installing the CPU build of PyTorch"
            Run $VenvPy @("-m", "pip", "install", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cpu") | Out-Null
            $torchState = & $VenvPy -c "import torch; print('cuda' if torch.cuda.is_available() else 'cpu', torch.__version__)" 2>$null
        }
        if ($torchState) { Ok "PyTorch $torchState" } else { Fail "PyTorch failed to install (see the log above)" }

        Info "Installing the project's Python packages (requirements.txt)..."
        $code = Run $VenvPy @("-m", "pip", "install", "-r", "$Root\requirements.txt")
        if ($code -eq 0) { Ok "All Python packages installed" } else { Fail "Some Python packages failed to install (see the log above)" }
    }
    $check = & $VenvPy -c "import fastapi, uvicorn, multipart, numpy, cv2, PIL, torch, torchvision, reportlab, dotenv, transformers, edge_tts, httpx; print('ok')" 2>$null
    if ($check -eq "ok") { Ok "Python imports verified" } elseif (-not $CheckOnly) { Fail "Some Python packages cannot be imported" } else { Warn "Some Python packages are missing" }
} else { Warn "Skipped - no Python environment" }

# --------------------------------------------------------------------------- 3. Ollama + LLM
Step 3 "Ollama and the farm-advisor AI model (gemma3:4b, ~3.3 GB)"
$advisorModel = "gemma3:4b"
if (Test-Path "$Root\.env") {
    $line = Select-String -Path "$Root\.env" -Pattern '^\s*ADVISOR_MODEL\s*=\s*(\S+)' | Select-Object -First 1
    if ($line) { $advisorModel = $line.Matches[0].Groups[1].Value }
}
if (-not (Have "ollama")) {
    if ($CheckOnly) { Warn "Ollama is not installed" }
    else {
        if (-not (Winget-Install "Ollama.Ollama" "Ollama")) {
            $inst = "$Temp\OllamaSetup.exe"
            if (Test-Path "$Root\OllamaSetup.exe") { $inst = "$Root\OllamaSetup.exe" } else { Download "https://ollama.com/download/OllamaSetup.exe" $inst }
            Info "Running the Ollama installer..."
            Start-Process $inst -ArgumentList "/VERYSILENT", "/NORESTART" -Wait
            Refresh-Path
        }
    }
}
if (Have "ollama") {
    Ok "Ollama installed"
    $running = $false
    try { Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 3 | Out-Null; $running = $true } catch {}
    if (-not $running -and -not $CheckOnly) {
        Info "Starting the Ollama service"
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
        for ($i = 0; $i -lt 20 -and -not $running; $i++) {
            Start-Sleep -Seconds 1
            try { Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 | Out-Null; $running = $true } catch {}
        }
    }
    if ($running) {
        $models = (Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5).models.name
        if ($models -contains $advisorModel) { Ok "Advisor model $advisorModel is installed" }
        elseif ($CheckOnly) { Warn "Advisor model $advisorModel is not downloaded" }
        else {
            Info "Downloading $advisorModel (one time, a few minutes)..."
            $code = Run "ollama" @("pull", $advisorModel)
            if ($code -eq 0) { Ok "Advisor model $advisorModel downloaded" } else { Fail "Could not download $advisorModel - run 'ollama pull $advisorModel' later" }
        }
    } elseif (-not $CheckOnly) { Fail "The Ollama service did not start - restart the laptop and run this again" }
    else { Warn "Ollama is installed but not running (start.bat starts it)" }
} elseif (-not $CheckOnly) { Fail "Ollama could not be installed - download it from https://ollama.com/download" }

# --------------------------------------------------------------------------- 4. Speech + vision models
Step 4 "AI models: crop disease/pest (in project) + Whisper speech-to-text + 12 voices (~3.4 GB)"
if (Test-Path $VenvPy) {
    $argsList = @("$Root\scripts\download_models.py")
    if ($CheckOnly) { $argsList += "--check" }
    $code = Run $VenvPy $argsList
    if ($code -eq 0) { Ok "All AI models present" } elseif ($CheckOnly) { Warn "Some AI models are not downloaded yet" } else { Fail "Some AI models could not be downloaded (re-run this installer to resume)" }
} else { Warn "Skipped - no Python environment" }

# --------------------------------------------------------------------------- 5. Node.js + dashboard
Step 5 "Node.js and the laptop web dashboard"
if (-not (Have "node")) {
    if ($CheckOnly) { Warn "Node.js is not installed (only needed to rebuild the web dashboard)" }
    elseif (-not (Winget-Install "OpenJS.NodeJS.LTS" "Node.js LTS")) {
        $inst = "$Temp\node-v22.15.0-x64.msi"
        Download "https://nodejs.org/dist/v22.15.0/node-v22.15.0-x64.msi" $inst
        Start-Process "msiexec.exe" -ArgumentList "/i", "`"$inst`"", "/qn" -Wait
        Refresh-Path
    }
}
if (Have "node") {
    Ok "Node.js $(node --version)"
    if (-not $CheckOnly -and -not (Test-Path "$Root\frontend\node_modules")) {
        Push-Location "$Root\frontend"; Info "npm install"; Run "npm.cmd" @("install", "--no-audit", "--no-fund") | Out-Null; Pop-Location
    }
    if (-not $CheckOnly -and -not (Test-Path "$Root\frontend\dist\index.html")) {
        Push-Location "$Root\frontend"; Info "Building the dashboard"; Run "npm.cmd" @("run", "build") | Out-Null; Pop-Location
    }
}
if (Test-Path "$Root\frontend\dist\index.html") { Ok "Web dashboard built (frontend\dist)" } else { Warn "Web dashboard is not built" }

# --------------------------------------------------------------------------- 6. Flutter + Android (optional)
Step 6 "Phone app build tools: Git, Java 17, Android SDK, Flutter (optional, ~6 GB)"
$flutterBat = "$env:USERPROFILE\development\flutter\bin\flutter.bat"
if (Have "flutter") { $flutterBat = (Get-Command flutter).Source }
$sdk = "$env:LOCALAPPDATA\Android\Sdk"
$wantFlutter = $WithFlutter
if (-not $CheckOnly -and -not $SkipFlutter -and -not $WithFlutter) {
    if ((Test-Path $flutterBat) -and (Test-Path "$sdk\platform-tools\adb.exe")) { $wantFlutter = $true }
    else {
        $answer = Read-Host "    Install Flutter + Android tools to build the phone app (needed only to rebuild the APK)? [Y/N]"
        $wantFlutter = $answer -match '^[Yy]'
    }
}
if ($CheckOnly) {
    if (Test-Path $flutterBat) { Ok "Flutter: $flutterBat" } else { Warn "Flutter is not installed (only needed to rebuild the phone app)" }
    if (Test-Path "$sdk\platform-tools\adb.exe") { Ok "Android SDK: $sdk" } else { Warn "Android SDK is not installed" }
    $java = Get-ChildItem "C:\Program Files\Eclipse Adoptium\jdk-17*" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($java -or $env:JAVA_HOME) { Ok "Java 17 present" } else { Warn "Java 17 is not installed" }
} elseif ($wantFlutter) {
    if (-not (Have "git")) { [void](Winget-Install "Git.Git" "Git") }
    if (Have "git") { Ok "Git" } else { Fail "Git is required for Flutter - install it from https://git-scm.com" }

    $jdk = Get-ChildItem "C:\Program Files\Eclipse Adoptium\jdk-17*" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $jdk) { [void](Winget-Install "EclipseAdoptium.Temurin.17.JDK" "Java 17 (Temurin)"); $jdk = Get-ChildItem "C:\Program Files\Eclipse Adoptium\jdk-17*" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1 }
    if ($jdk) { $env:JAVA_HOME = $jdk.FullName; $env:Path = "$($jdk.FullName)\bin;$env:Path"; Ok "Java 17: $($jdk.FullName)" } else { Fail "Java 17 could not be installed" }

    if (-not (Test-Path "$sdk\cmdline-tools\latest\bin\sdkmanager.bat")) {
        $zip = "$Temp\cmdline-tools.zip"
        Download "https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip" $zip
        Expand-Archive -Path $zip -DestinationPath "$Temp\cmdline" -Force
        New-Item -ItemType Directory -Force -Path "$sdk\cmdline-tools" | Out-Null
        if (Test-Path "$sdk\cmdline-tools\latest") { Remove-Item -Recurse -Force "$sdk\cmdline-tools\latest" }
        Move-Item "$Temp\cmdline\cmdline-tools" "$sdk\cmdline-tools\latest"
    }
    $sdkmanager = "$sdk\cmdline-tools\latest\bin\sdkmanager.bat"
    if (Test-Path $sdkmanager) {
        Info "Installing Android SDK packages (platform-tools, Android 36, build-tools)..."
        Run $sdkmanager @("--sdk_root=$sdk", "platform-tools", "platforms;android-36", "build-tools;36.0.0") | Out-Null
        [Environment]::SetEnvironmentVariable("ANDROID_HOME", $sdk, "User"); $env:ANDROID_HOME = $sdk
        if (Test-Path "$sdk\platform-tools\adb.exe") { Ok "Android SDK: $sdk" } else { Fail "Android SDK packages did not install" }
    } else { Fail "Android command-line tools could not be set up" }

    if (-not (Test-Path $flutterBat) -and (Have "git")) {
        New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\development" | Out-Null
        Info "Downloading Flutter (stable)..."
        Run "git" @("clone", "--depth", "1", "-b", "stable", "https://github.com/flutter/flutter.git", "$env:USERPROFILE\development\flutter") | Out-Null
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($userPath -notlike "*development\flutter\bin*") {
            [Environment]::SetEnvironmentVariable("Path", "$userPath;$env:USERPROFILE\development\flutter\bin", "User")
        }
        Refresh-Path
    }
    if (Test-Path $flutterBat) {
        Ok "Flutter: $flutterBat"
        Run $flutterBat @("config", "--android-sdk", $sdk, "--no-analytics") | Out-Null
        Write-Host ""
        Write-Host "    Android needs you to read and accept its SDK licences once. Type 'y' for each one." -ForegroundColor Yellow
        & $flutterBat doctor --android-licenses
        Push-Location "$Root\agrobot_flutter_app"
        Info "flutter pub get"; Run $flutterBat @("pub", "get") | Out-Null
        Info "Building the phone app (release APK, 5-10 minutes the first time)..."
        $code = Run $flutterBat @("build", "apk", "--release")
        Pop-Location
        $apk = "$Root\agrobot_flutter_app\build\app\outputs\flutter-apk\app-release.apk"
        if ($code -eq 0 -and (Test-Path $apk)) {
            Copy-Item $apk "$Root\AGROBOTAI.apk" -Force
            Ok "Phone app built: $Root\AGROBOTAI.apk"
            $adb = "$sdk\platform-tools\adb.exe"
            $devices = & $adb devices 2>$null | Select-String "\tdevice$"
            if ($devices) {
                $answer = Read-Host "    An Android phone is connected by USB. Install AGROBOTAI on it now? [Y/N]"
                if ($answer -match '^[Yy]') { Run $adb @("install", "-r", "$Root\AGROBOTAI.apk") | Out-Null }
            } else { Info "To install on a phone later: copy AGROBOTAI.apk to the phone and open it" }
        } else { Fail "The phone app build failed (see the log above)" }
    } else { Fail "Flutter could not be installed" }
} else { Info "Skipped (run INSTALL_ALL.bat again and answer Y to build the phone app)" }

# --------------------------------------------------------------------------- 7. Config + final check
Step 7 "Configuration and final check"
if (-not (Test-Path "$Root\.env")) {
    if ($CheckOnly) { Warn ".env is missing (start.bat creates it from .env.example)" }
    else { Copy-Item "$Root\.env.example" "$Root\.env"; Ok "Created .env from .env.example" }
} else { Ok ".env present" }
if ((Test-Path $VenvPy) -and -not $CheckOnly) {
    Info "Server start-up check (a 'Port 8000 is already in use' line only means AGROBOTAI is already running):"
    Run $VenvPy @("$Root\scripts\preflight.py") | Out-Null
}

Remove-Item -Recurse -Force "$Temp\*" -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Green
if ($script:Problems.Count -eq 0) {
    Write-Host "  Everything is installed." -ForegroundColor Green
} else {
    Write-Host "  Finished with $($script:Problems.Count) item(s) to look at:" -ForegroundColor Yellow
    $script:Problems | ForEach-Object { Write-Host "   - $_" -ForegroundColor Yellow }
}
Write-Host "  Start the server any time with start.bat"
if (-not $CheckOnly) { Write-Host "  Install log: $LogFile"; Stop-Transcript | Out-Null }
Write-Host "====================================================================="
if ($script:Problems.Count -gt 0) { exit 1 } else { exit 0 }
