<#
Deploy AGROBOTAI Edge-AI from this laptop to the Raspberry Pi (run in PowerShell from the project folder).

  powershell -ExecutionPolicy Bypass -File scripts\deploy_to_pi.ps1 -Find                 # only look for the Pi
  powershell -ExecutionPolicy Bypass -File scripts\deploy_to_pi.ps1                       # find, copy, install, start, test
  powershell -ExecutionPolicy Bypass -File scripts\deploy_to_pi.ps1 -PiHost 192.168.1.20  # use a known address
  powershell -ExecutionPolicy Bypass -File scripts\deploy_to_pi.ps1 -UpdateOnly           # copy new code/models + restart
  powershell -ExecutionPolicy Bypass -File scripts\deploy_to_pi.ps1 -PackageOnly          # just build the package

SSH asks for the Pi password yourself in this window (it is never stored). With -SetupKey it is asked once and
an SSH key is installed so later runs need no password. Data on the Pi (.env, accounts, scans) is never replaced.
#>
param([string]$PiHost = '', [string]$User = 'agrobot', [switch]$Find, [switch]$SetupKey, [switch]$UpdateOnly,
      [switch]$PackageOnly, [switch]$NoUpgrade)

$ErrorActionPreference = 'Continue'
$PSDefaultParameterValues['*:ErrorAction'] = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$PiOui = 'b8-27-eb', 'dc-a6-32', 'e4-5f-01', 'd8-3a-dd', '2c-cf-67', '28-cd-c1'   # Raspberry Pi Foundation / Ltd

function Say($t, $c = 'Gray') { Write-Host "  $t" -ForegroundColor $c }

function Test-Ssh($ip) {
    $c = New-Object Net.Sockets.TcpClient
    try { return $c.ConnectAsync($ip, 22).Wait(1500) -and $c.Connected } catch { return $false } finally { $c.Close() }
}

function Find-Pi {
    foreach ($name in 'agrobotai-pi.local', 'agrobotai-pi', 'raspberrypi.local') {
        try {
            $ip = [Net.Dns]::GetHostAddresses($name) | Where-Object AddressFamily -eq 'InterNetwork' | Select-Object -First 1
            if ($ip -and (Test-Ssh "$ip")) { Say "found $name at $ip (SSH open)" Green; return "$ip" }
        } catch { }
    }
    Say 'hostname not found; scanning the Wi-Fi network for a Raspberry Pi ...'
    $nets = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.PrefixLength -eq 24 -and $_.IPAddress -match '^(192\.168|10\.|172\.(1[6-9]|2\d|3[01]))' }
    foreach ($n in $nets) {
        $pre = $n.IPAddress -replace '\d+$', ''
        $pings = 1..254 | ForEach-Object { (New-Object Net.NetworkInformation.Ping).SendPingAsync("$pre$_", 500) }
        try { [Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]$pings) } catch { }
        $pis = Get-NetNeighbor -AddressFamily IPv4 -InterfaceIndex $n.InterfaceIndex | Where-Object {
            $mac = $_.LinkLayerAddress.ToLower(); $PiOui | Where-Object { $mac.StartsWith($_) } }
        foreach ($p in $pis) {
            $open = Test-Ssh $p.IPAddress
            Say ("Raspberry Pi at {0} (MAC {1}) - SSH {2}" -f $p.IPAddress, $p.LinkLayerAddress, $(if ($open) { 'open' } else { 'CLOSED' })) $(if ($open) { 'Green' } else { 'Yellow' })
            if ($open) { return $p.IPAddress }
        }
    }
    return $null
}

function Build-Package {
    $onnxOk = (Test-Path 'models\onnx\disease_model.onnx') -and (Test-Path 'models\onnx\pest_model.onnx') -and
        ((Get-Item 'models\onnx\disease_model.onnx').LastWriteTime -gt (Get-Item 'models\disease_model.pt').LastWriteTime) -and
        ((Get-Item 'models\onnx\pest_model.onnx').LastWriteTime -gt (Get-Item 'models\pest_model.pt').LastWriteTime)
    if (-not $onnxOk) {
        Say 'Exporting the trained models to ONNX (checked against PyTorch) ...'
        & $Py scripts\export_onnx.py
        if ($LASTEXITCODE -ne 0) { throw 'ONNX export failed' }
    }
    $stage = Join-Path $env:TEMP 'agrobotai_edge_pkg'
    if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
    New-Item -ItemType Directory -Force "$stage\models\onnx", "$stage\scripts", "$stage\sensors", "$stage\frontend" | Out-Null
    Copy-Item server.py, manage_users.py, .env.example $stage
    robocopy src "$stage\src" /E /XD __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null
    robocopy frontend\dist "$stage\frontend\dist" /E /NFL /NDL /NJH /NJS /NP | Out-Null
    Copy-Item models\onnx\*.onnx, models\onnx\*.json "$stage\models\onnx"
    Copy-Item models\calibration.json, models\disease_classes.json, models\pest_classes.json "$stage\models"
    Copy-Item scripts\sensor_token.py "$stage\scripts"
    Copy-Item iot\raspberry_pi\* "$stage\sensors"
    Copy-Item edge\* $stage
    # Shell scripts must have Unix line endings
    Get-ChildItem $stage -Filter *.sh | ForEach-Object { [IO.File]::WriteAllText($_.FullName, ([IO.File]::ReadAllText($_.FullName) -replace "`r`n", "`n")) }
    $tgz = Join-Path $env:TEMP 'agrobotai_edge.tar.gz'
    & "$env:SystemRoot\System32\tar.exe" -czf $tgz -C $stage .
    if ($LASTEXITCODE -ne 0) { throw 'could not create the package' }
    Say ("package ready: {0} ({1:N0} MB)" -f $tgz, ((Get-Item $tgz).Length / 1MB)) Green
    return $tgz
}

Write-Host "`n=== AGROBOTAI -> Raspberry Pi deploy ===" -ForegroundColor Cyan
if ($PackageOnly) { Build-Package | Out-Null; exit 0 }

if (-not $PiHost) { $PiHost = Find-Pi }
if (-not $PiHost) {
    Say 'No Raspberry Pi with SSH was found on this network.' Red
    Say '1. Power the Pi (USB-C power only powers it; it is not a data/SSH connection).' Yellow
    Say '2. Wait 2 minutes after the first boot (it resizes the SD card and joins Wi-Fi).' Yellow
    Say '3. The SD card must be written with Raspberry Pi Imager with hostname agrobotai-pi, user agrobot,' Yellow
    Say '   SSH enabled and your Wi-Fi name/password + country IN (see edge\README.md).' Yellow
    Say '4. Or plug the Pi into the router with an Ethernet cable, then run this again.' Yellow
    exit 2
}
if ($Find) { exit 0 }
$target = "$User@$PiHost"
$sshOpts = @('-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=10')

if ($SetupKey) {
    $key = Join-Path $env:USERPROFILE '.ssh\id_ed25519'
    if (-not (Test-Path $key)) {
        New-Item -ItemType Directory -Force (Split-Path $key) | Out-Null
        cmd /c "ssh-keygen -q -t ed25519 -N `"`" -f `"$key`""
    }
    Say "Installing this laptop's SSH key on the Pi - type the Pi password for '$User' once:" Yellow
    Get-Content "$key.pub" | & ssh @sshOpts $target 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && sort -u -o ~/.ssh/authorized_keys ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
    if ($LASTEXITCODE -ne 0) { Say 'SSH key was not installed (wrong password or user?)' Red; exit 3 }
    Say 'SSH key installed - no password needed from now on.' Green
}

$tgz = Build-Package
Say "Copying to $target ..."
& scp @sshOpts $tgz "${target}:~/agrobotai_edge.tar.gz"
if ($LASTEXITCODE -ne 0) { Say 'copy failed (check the user name / password)' Red; exit 3 }

$install = if ($UpdateOnly) { 'true' } elseif ($NoUpgrade) { 'bash install_pi.sh --no-upgrade' } else { 'bash install_pi.sh' }
# Unpacking adds/replaces program files only; .env, venv, outputs/ (accounts, scans) and logs/ are not in the package
# With the boot service enabled, systemd owns the server; otherwise use start.sh / stop.sh
$restart = 'if systemctl is-enabled --quiet agrobotai-edge 2>/dev/null; then sudo systemctl restart agrobotai-edge && sleep 10 && systemctl is-active agrobotai-edge; else ./stop.sh && ./start.sh; fi'
$remote = "mkdir -p ~/agrobotai_edge && tar -xzf ~/agrobotai_edge.tar.gz -C ~/agrobotai_edge && rm ~/agrobotai_edge.tar.gz && cd ~/agrobotai_edge && chmod +x *.sh && $install && ($restart)"
& ssh -t @sshOpts $target $remote
if ($LASTEXITCODE -ne 0) { Say 'install/start on the Pi reported a problem (see above)' Red; exit 4 }

$photo = Get-ChildItem 'data\disease\test' -Recurse -Include *.jpg, *.JPG -ErrorAction SilentlyContinue | Select-Object -First 1
if ($photo) {
    Say "Testing the Pi from this laptop with a real leaf photo ..."
    & $Py edge\test_edge_api.py "http://${PiHost}:8000" $photo.FullName
}
Write-Host "`n  Phone app server URL: http://${PiHost}:8000   (app: Login > Change server)" -ForegroundColor Green
