<#
AGROBOTAI - complete setup for a new Windows 10/11 PC (run through SETUP_ALL.bat).

Installs only what is missing, so it is safe to run again at any time:
  1  winget check                     6  AI advisor model (Ollama + gemma3:4b)
  2  Python 3.12                      7  Voice models (Whisper + Tamil/English voices)
  3  .venv + all Python packages      8  Web dashboard build (only if missing)
     (CUDA PyTorch when an NVIDIA GPU is present)
  4  .env configuration               9  Flutter SDK + Git + JDK 17 + Android SDK
  5  AI models present + loadable    10  Phone access (firewall) + admin account + final check

Options:  -SkipFlutter   server only (no Flutter / Android tools)
          -TestOnly      check every step and download link, install nothing
#>
param([switch]$SkipFlutter, [switch]$TestOnly)

# PowerShell 5.1 turns normal stderr output of native tools (java -version, git, sdkmanager) into fatal errors
# under 'Stop', so only cmdlets stop on errors; native tools are checked by their exit code.
$ErrorActionPreference = 'Continue'
$PSDefaultParameterValues['*:ErrorAction'] = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is 10x slower with the progress bar
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$Results = [ordered]@{}
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Downloads = Join-Path $env:TEMP 'agrobotai_setup'
New-Item -ItemType Directory -Force $Downloads | Out-Null

function Say($text, $color = 'Gray') { Write-Host "  $text" -ForegroundColor $color }

function Step($name, [scriptblock]$body) {
    Write-Host ''
    Write-Host "=== $name ===" -ForegroundColor Cyan
    try {
        $msg = & $body | Select-Object -Last 1
        $Results[$name] = @('OK', "$msg")
        Say "[OK] $msg" Green
    } catch {
        $Results[$name] = @('FAIL', $_.Exception.Message)
        Say "[FAIL] $($_.Exception.Message)" Red
    }
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

function Add-UserPath($dir) {
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not (($user -split ';') -contains $dir)) {
        [Environment]::SetEnvironmentVariable('Path', ($user.TrimEnd(';') + ';' + $dir).TrimStart(';'), 'User')
    }
    if (-not (($env:Path -split ';') -contains $dir)) { $env:Path = "$env:Path;$dir" }
}

function Winget-Install($id, $what) {
    if ($TestOnly) { Say "would install $what with winget ($id)" Yellow; return }
    if (-not (Has 'winget')) { throw "winget is missing. Install 'App Installer' from the Microsoft Store, then run SETUP_ALL.bat again." }
    Say "Installing $what (winget $id) ..."
    & winget install --id $id -e --silent --accept-source-agreements --accept-package-agreements --scope user 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        # Some packages only offer a machine-wide installer
        & winget install --id $id -e --silent --accept-source-agreements --accept-package-agreements 2>&1 | Out-Host
    }
    Refresh-Path
}

function Download($url, $file) {
    if ($TestOnly) {
        $r = Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing
        Say "download link works ($([math]::Round($r.Headers.'Content-Length' / 1MB)) MB): $url"
        return
    }
    Say "Downloading $url ..."
    try { Start-BitsTransfer -Source $url -Destination $file -ErrorAction Stop }
    catch { Invoke-WebRequest -Uri $url -OutFile $file -UseBasicParsing }
}

function Run-Py([string[]]$pyArgs) {
    & $Py @pyArgs
    if ($LASTEXITCODE -ne 0) { throw "python $($pyArgs -join ' ') failed (exit $LASTEXITCODE)" }
}

Write-Host ''
Write-Host '=====================================================================' -ForegroundColor Green
Write-Host '  AGROBOTAI - complete setup (server, AI models, Flutter, Android)' -ForegroundColor Green
if ($TestOnly) { Write-Host '  TEST MODE: checking only, nothing is installed' -ForegroundColor Yellow }
Write-Host '=====================================================================' -ForegroundColor Green

# ------------------------------------------------------------------ 1. winget
Step '1. Windows package manager (winget)' {
    if (-not (Has 'winget')) { throw "winget not found. Install 'App Installer' from the Microsoft Store (free), then run again." }
    "winget $((& winget --version) -join '')"
}

# ------------------------------------------------------------------ 2. Python
$BasePython = $null
Step '2. Python 3.12' {
    if ((Test-Path $Py) -and ((& $Py -c "import sys; print(sys.version_info >= (3, 11))" 2>$null) -eq 'True')) {
        return "using existing project environment ($((& $Py --version) -join ''))"
    }
    foreach ($v in '3.12', '3.13', '3.11') {
        if ((Has 'py') -and ((& py "-$v" -c 'print(1)' 2>$null) -eq '1')) { $script:BasePython = @('py', "-$v"); return "found Python $v" }
    }
    $local = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (-not (Test-Path $local)) { Winget-Install 'Python.Python.3.12' 'Python 3.12' }
    if ($TestOnly) { return 'Python 3.12 would be installed' }
    if (-not (Test-Path $local)) { throw 'Python 3.12 did not install. Install it from https://www.python.org/downloads/ (tick "Add to PATH") and run again.' }
    $script:BasePython = @($local)
    'installed Python 3.12'
}

# ------------------------------------------------------------------ 3. venv + packages
Step '3. Python environment and packages' {
    $venvOk = (Test-Path $Py) -and ((& $Py -c 'print(1)' 2>$null) -eq '1')
    if (-not $venvOk) {
        if ($TestOnly) { return '.venv would be created' }
        if (Test-Path '.venv') {
            $old = ".venv_broken_$(Get-Date -Format yyyyMMddHHmm)"
            Say "The existing .venv does not start (moved or copied from another PC); keeping it as $old"
            Rename-Item '.venv' $old
        }
        $exe = $BasePython[0]; $pre = @($BasePython | Select-Object -Skip 1)
        & $exe @pre -m venv .venv
        if (-not (Test-Path $Py)) { throw 'could not create .venv' }
    }
    if ($TestOnly) {
        $missing = & $Py -c "import importlib.util as u; m=[x for x in ('torch','torchvision','fastapi','uvicorn','cv2','PIL','transformers','openai','reportlab','edge_tts','multipart','dotenv','timm') if u.find_spec(x) is None]; print(','.join(m))"
        if ($missing) { return "would install missing packages: $missing" } else { return 'all packages present' }
    }
    Run-Py @('-m', 'pip', 'install', '--upgrade', 'pip', '--quiet', '--disable-pip-version-check')
    $hasTorch = (& $Py -c "import torch; print('ok')" 2>$null) -eq 'ok'
    if (-not $hasTorch) {
        # PyTorch wheel matching the NVIDIA driver; CPU build when there is no NVIDIA GPU
        $index = 'https://download.pytorch.org/whl/cpu'
        if (Has 'nvidia-smi') {
            $m = [regex]::Match((& nvidia-smi 2>$null | Out-String), 'CUDA Version:\s*([\d.]+)')
            if ($m.Success) {
                $cuda = [version]$m.Groups[1].Value
                if ($cuda -ge [version]'13.0') { $index = 'https://download.pytorch.org/whl/cu130' }
                elseif ($cuda -ge [version]'12.8') { $index = 'https://download.pytorch.org/whl/cu128' }
                elseif ($cuda -ge [version]'12.6') { $index = 'https://download.pytorch.org/whl/cu126' }
            }
        }
        Say "Installing PyTorch from $index (about 2-3 GB, please wait) ..."
        Run-Py @('-m', 'pip', 'install', 'torch', 'torchvision', '--index-url', $index, '--disable-pip-version-check')
    }
    Say 'Installing the other packages from requirements.txt ...'
    Run-Py @('-m', 'pip', 'install', '-r', 'requirements.txt', '--disable-pip-version-check', '--quiet')
    $info = & $Py -c "import torch, fastapi, transformers, cv2; print(f'torch {torch.__version__}, GPU: {torch.cuda.is_available()}')"
    if ($LASTEXITCODE -ne 0) { throw 'packages installed but cannot be imported' }
    "$info"
}

# ------------------------------------------------------------------ 4. .env
Step '4. Configuration (.env)' {
    if (Test-Path '.env') { return '.env exists (kept as it is)' }
    if ($TestOnly) { return '.env would be created from .env.example' }
    Copy-Item '.env.example' '.env'
    'created .env from .env.example'
}

# ------------------------------------------------------------------ 5. AI models
Step '5. Disease and pest models' {
    foreach ($f in 'models\disease_model.pt', 'models\pest_model.pt') {
        if (-not (Test-Path $f)) { throw "$f is missing. Copy the models folder from the original laptop." }
    }
    $out = & $Py -c "import sys; sys.path.insert(0, '.'); from src import model_registry as m; s = m.load_all(); bad = [k for k, v in s.items() if not v.get('ready')]; print('FAILED ' + ', '.join(bad) if bad else 'disease + pest models load correctly on ' + m.runtime_info()['inference_device'])" 2>$null | Select-Object -Last 1
    if ("$out" -like 'FAILED*' -or -not $out) { throw "model check: $out" }
    "$out"
}

# ------------------------------------------------------------------ 6. Ollama + advisor model
Step '6. AI advisor (Ollama + gemma3:4b)' {
    $ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollama) {
        $guess = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
        if (Test-Path $guess) { $ollama = $guess } else {
            Winget-Install 'Ollama.Ollama' 'Ollama'
            if ($TestOnly) { return 'Ollama and gemma3:4b would be installed (about 3.3 GB)' }
            if (Test-Path $guess) { $ollama = $guess } else { $ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source }
            if (-not $ollama) { throw 'Ollama did not install. Get it from https://ollama.com/download and run again.' }
        }
    }
    $up = $false
    try { Invoke-WebRequest 'http://127.0.0.1:11434/api/tags' -UseBasicParsing -TimeoutSec 3 | Out-Null; $up = $true } catch { }
    if (-not $up) {
        if ($TestOnly) { return 'Ollama installed but not running (setup would start it)' }
        Start-Process $ollama 'serve' -WindowStyle Hidden
        foreach ($i in 1..30) { Start-Sleep 1; try { Invoke-WebRequest 'http://127.0.0.1:11434/api/tags' -UseBasicParsing -TimeoutSec 2 | Out-Null; $up = $true; break } catch { } }
        if (-not $up) { throw 'Ollama is installed but did not start. Start the Ollama app once, then run again.' }
    }
    $model = (& $Py -c "import sys; sys.path.insert(0, '.'); from src import config; print(config.ADVISOR_MODEL)" 2>$null | Select-Object -Last 1)
    if (-not $model) { $model = 'gemma3:4b' }
    $tags = (Invoke-WebRequest 'http://127.0.0.1:11434/api/tags' -UseBasicParsing).Content | ConvertFrom-Json
    if ($tags.models.name -contains $model) { return "Ollama running, $model installed" }
    if ($TestOnly) { return "$model would be downloaded (about 3.3 GB)" }
    Say "Downloading the advisor model $model (about 3.3 GB) ..."
    & $ollama pull $model | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "ollama pull $model failed (check the internet connection and run again)" }
    "$model installed"
}

# ------------------------------------------------------------------ 7. voice models
Step '7. Voice models (speech-to-text + Tamil/English voices)' {
    if ($TestOnly) { return 'would pre-download Whisper turbo + Tamil and English voices (about 2 GB); other languages download on first use' }
    Say 'Downloading voice models (about 2 GB the first time) ...'
    Run-Py @('-c', "from huggingface_hub import snapshot_download as d; [d(r) for r in ('openai/whisper-large-v3-turbo', 'facebook/mms-tts-tam', 'facebook/mms-tts-eng')]; print('ok')")
    'Whisper + Tamil/English voices ready (other languages download on first use)'
}

# ------------------------------------------------------------------ 8. web dashboard
Step '8. Web dashboard' {
    if (Test-Path 'frontend\dist\index.html') { return 'already built (frontend\dist)' }
    if (-not (Has 'npm')) { Winget-Install 'OpenJS.NodeJS.LTS' 'Node.js LTS' }
    if ($TestOnly) { return 'dashboard would be built with npm' }
    Push-Location frontend
    try {
        & npm ci --no-audit --no-fund | Out-Host; if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
        & npm run build | Out-Host; if ($LASTEXITCODE -ne 0) { throw 'npm run build failed' }
    } finally { Pop-Location }
    'built frontend\dist'
}

# ------------------------------------------------------------------ 9. Flutter + Android
if ($SkipFlutter) {
    $Results['9. Flutter + Android tools'] = @('SKIP', 'skipped (-SkipFlutter)')
} else {
    Step '9a. Git (needed by Flutter)' {
        if (Has 'git') { return (& git --version) -join '' }
        Winget-Install 'Git.Git' 'Git'
        if ($TestOnly) { return 'Git would be installed' }
        Add-UserPath 'C:\Program Files\Git\cmd'
        if (-not (Has 'git')) { throw 'Git did not install. Get it from https://git-scm.com/download/win and run again.' }
        (& git --version) -join ''
    }

    $FlutterHome = Join-Path $env:USERPROFILE 'development\flutter'
    Step '9b. Flutter SDK' {
        if (-not (Has 'flutter') -and (Test-Path "$FlutterHome\bin\flutter.bat")) { Add-UserPath "$FlutterHome\bin" }
        if (-not (Has 'flutter')) {
            $rel = Invoke-RestMethod 'https://storage.googleapis.com/flutter_infra_release/releases/releases_windows.json'
            $stable = $rel.releases | Where-Object { $_.hash -eq $rel.current_release.stable } | Select-Object -First 1
            $url = "$($rel.base_url)/$($stable.archive)"
            $zip = Join-Path $Downloads (Split-Path $stable.archive -Leaf)
            Download $url $zip
            if ($TestOnly) { return "Flutter $($stable.version) would be installed to $FlutterHome" }
            New-Item -ItemType Directory -Force (Split-Path $FlutterHome) | Out-Null
            Say "Unpacking Flutter $($stable.version) to $FlutterHome (a few minutes) ..."
            & "$env:SystemRoot\System32\tar.exe" -xf $zip -C (Split-Path $FlutterHome)
            if (-not (Test-Path "$FlutterHome\bin\flutter.bat")) { throw "Flutter did not unpack to $FlutterHome" }
            Add-UserPath "$FlutterHome\bin"
        }
        if ($TestOnly) { return "Flutter found: $((Get-Command flutter).Source)" }
        & flutter config --no-analytics 2>&1 | Out-Null
        ((& flutter --version 2>&1 | Select-String '^Flutter') -replace '\s+', ' ').Trim()
    }

    Step '9c. Java 17 (needed to build the Android app)' {
        $studioJbr = 'C:\Program Files\Android\Android Studio\jbr'
        if (Test-Path "$studioJbr\bin\java.exe") { return "using Android Studio's Java ($studioJbr)" }
        $java = Get-Command java -ErrorAction SilentlyContinue
        if ($java) {
            $v = (& java -version 2>&1 | Out-String)
            if ($v -match 'version "(\d+)') { if ([int]$Matches[1] -ge 17) { return "Java $($Matches[1]) found" } }
        }
        Winget-Install 'Microsoft.OpenJDK.17' 'Java 17 (Microsoft OpenJDK)'
        if ($TestOnly) { return 'Java 17 would be installed' }
        $jdk = Get-ChildItem 'C:\Program Files\Microsoft' -Directory -Filter 'jdk-17*' -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $jdk) { throw 'Java 17 did not install. Get it from https://learn.microsoft.com/java/openjdk/download and run again.' }
        [Environment]::SetEnvironmentVariable('JAVA_HOME', $jdk.FullName, 'User'); $env:JAVA_HOME = $jdk.FullName
        Add-UserPath "$($jdk.FullName)\bin"
        if (Has 'flutter') { & flutter config --jdk-dir $jdk.FullName 2>&1 | Out-Null }
        "installed $($jdk.Name)"
    }

    Step '9d. Android SDK (platform-tools + licenses)' {
        $sdk = $env:ANDROID_HOME
        if (-not $sdk) { $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
        $sdkmanager = Get-ChildItem "$sdk\cmdline-tools" -Recurse -Filter 'sdkmanager.bat' -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $sdkmanager) {
            $repo = [xml](Invoke-WebRequest 'https://dl.google.com/android/repository/repository2-3.xml' -UseBasicParsing).Content
            $file = ($repo.SelectNodes('//url') | ForEach-Object { $_.InnerText } | Where-Object { $_ -match '^commandlinetools-win-\d+_latest\.zip$' } | Select-Object -First 1)
            if (-not $file) { throw 'could not find the Android command-line tools download' }
            $zip = Join-Path $Downloads $file
            Download "https://dl.google.com/android/repository/$file" $zip
            if ($TestOnly) { return "Android SDK would be installed to $sdk" }
            $tmp = Join-Path $Downloads 'cmdline-tools-unpacked'
            if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
            New-Item -ItemType Directory -Force $tmp | Out-Null
            & "$env:SystemRoot\System32\tar.exe" -xf $zip -C $tmp
            New-Item -ItemType Directory -Force "$sdk\cmdline-tools" | Out-Null
            if (Test-Path "$sdk\cmdline-tools\latest") { Remove-Item "$sdk\cmdline-tools\latest" -Recurse -Force }
            Move-Item "$tmp\cmdline-tools" "$sdk\cmdline-tools\latest"
            $sdkmanager = Get-Item "$sdk\cmdline-tools\latest\bin\sdkmanager.bat"
        }
        if ($TestOnly) { return "Android SDK found at $sdk" }
        [Environment]::SetEnvironmentVariable('ANDROID_HOME', $sdk, 'User'); $env:ANDROID_HOME = $sdk
        Add-UserPath "$sdk\platform-tools"
        if (-not (Test-Path "$sdk\platform-tools\adb.exe")) {
            Say 'Installing Android platform-tools ...'
            ('y' + "`n") * 20 | & $sdkmanager.FullName "--sdk_root=$sdk" 'platform-tools' 2>&1 | Out-Host
        }
        # Licenses must be accepted once, or the first APK build fails
        ('y' + "`n") * 20 | & $sdkmanager.FullName "--sdk_root=$sdk" --licenses 2>&1 | Out-Null
        if (Has 'flutter') { & flutter config --android-sdk $sdk 2>&1 | Out-Null }
        if (-not (Test-Path "$sdk\platform-tools\adb.exe")) { throw 'platform-tools (adb) did not install' }
        "Android SDK ready at $sdk (other parts download automatically on the first build)"
    }

    Step '9e. Flutter app packages' {
        if ($TestOnly) { return 'would run flutter pub get' }
        Push-Location agrobot_flutter_app
        try { & flutter pub get 2>&1 | Out-Host; if ($LASTEXITCODE -ne 0) { throw 'flutter pub get failed' } } finally { Pop-Location }
        'flutter pub get done'
    }
}

# ------------------------------------------------------------------ 10. phone access, admin, final check
Step '10a. Phone access (Windows Firewall)' {
    & $Py scripts\phone_access.py --check | Out-Host
    if ($LASTEXITCODE -eq 0) { return 'phones on this Wi-Fi can reach the server' }
    if ($TestOnly) { return 'phones are blocked; setup would offer the fix' }
    $answer = Read-Host '  Phones are blocked by the firewall. Fix now? Windows will ask for admin permission [Y/N]'
    if ($answer -match '^[Yy]') { & $Py scripts\phone_access.py --fix | Out-Host }
    if ($LASTEXITCODE -eq 0) { return 'fixed: phones on this Wi-Fi can reach the server' }
    'still blocked: use a USB cable (start.bat sets it up) or set the Wi-Fi to Private'
}

Step '10b. Administrator account' {
    $admins = & $Py -c "import sys; sys.path.insert(0, '.'); from src import store; store.migrate(); print(store.count_admins())" 2>$null | Select-Object -Last 1
    if ([int]$admins -gt 0) { return "$admins administrator account(s) exist" }
    if ($TestOnly) { return 'no administrator yet; setup would ask you to create one' }
    Say 'Create the administrator account (used for the website admin page and reviewing scans):' Yellow
    & $Py manage_users.py ensure-admin
    if ($LASTEXITCODE -ne 0) { throw 'administrator account was not created (run: .venv\Scripts\python.exe manage_users.py create-admin)' }
    'administrator account created'
}

Step '10c. Final startup check' {
    & $Py scripts\preflight.py | Out-Host
    switch ($LASTEXITCODE) {
        0 { 'all startup checks passed' }
        2 { 'all set (the server is already running on this PC)' }
        3 { throw 'no administrator account yet' }
        default { throw 'a required component is missing (see the [FAIL] lines above)' }
    }
}

# ------------------------------------------------------------------ summary
Write-Host ''
Write-Host '=====================================================================' -ForegroundColor Green
Write-Host '  SETUP SUMMARY' -ForegroundColor Green
Write-Host '=====================================================================' -ForegroundColor Green
$failed = 0
foreach ($k in $Results.Keys) {
    $state, $msg = $Results[$k]
    $color = @{ OK = 'Green'; FAIL = 'Red'; SKIP = 'Yellow' }[$state]
    if ($state -eq 'FAIL') { $failed++ }
    Write-Host ("  [{0,-4}] {1,-52} {2}" -f $state, $k, $msg) -ForegroundColor $color
}
Write-Host ''
if ($failed -eq 0) {
    Write-Host '  Everything is ready.' -ForegroundColor Green
    Write-Host '  - Start the server:      double-click start.bat' -ForegroundColor Green
    Write-Host '  - Phone app:             install AGROBOTAI.apk on the phone' -ForegroundColor Green
    Write-Host '  - Rebuild the phone app: cd agrobot_flutter_app  then  flutter build apk --release' -ForegroundColor Green
    Write-Host '  - Admin page:            http://localhost:8000/#admin' -ForegroundColor Green
    Write-Host '  NOTE: open a NEW terminal window to use flutter / adb (PATH was updated).' -ForegroundColor Yellow
} else {
    Write-Host "  $failed step(s) failed - read the [FAIL] lines above, fix them, then run SETUP_ALL.bat again." -ForegroundColor Red
    Write-Host '  Steps that already worked are skipped on the next run.' -ForegroundColor Red
}
exit $failed
