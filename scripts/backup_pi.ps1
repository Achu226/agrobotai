<#
Nightly backup of the Raspberry Pi's AGROBOTAI data to this laptop (run by the scheduled task
"AGROBOTAI Pi backup"; safe to run by hand too):

  powershell -ExecutionPolicy Bypass -File scripts\backup_pi.ps1

Copies accounts, scans, scan photos and .env to backups\pi\agrobotai_pi_<date>.tgz and keeps the last 14.
Uses the laptop's SSH key (no password). If the Pi is off, it logs that and exits with code 1.
#>
param([string]$PiHost = 'agrobotai-pi.local', [string]$User = 'agrobot', [int]$Keep = 14)

$Root = Split-Path $PSScriptRoot -Parent
$Dir = Join-Path $Root 'backups\pi'
New-Item -ItemType Directory -Force $Dir | Out-Null
$LogFile = Join-Path $Dir 'backup.log'
function Log($msg) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Tee-Object -FilePath $LogFile -Append }

$ssh = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'StrictHostKeyChecking=accept-new')
$remote = (& ssh @ssh "$User@$PiHost" '~/agrobotai_edge/backup_snapshot.sh' 2>&1 | Select-Object -Last 1)
if ($LASTEXITCODE -ne 0) { Log "FAILED: Pi not reachable or snapshot failed ($remote)"; exit 1 }

$file = Join-Path $Dir ("agrobotai_pi_{0}.tgz" -f (Get-Date -Format 'yyyyMMdd_HHmm'))
& scp @ssh "${User}@${PiHost}:$remote" $file 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $file)) { Log 'FAILED: copy from the Pi failed'; exit 1 }

# Check the archive opens and holds the database before counting it as a backup
$list = & "$env:SystemRoot\System32\tar.exe" -tzf $file 2>$null
if ($list -notcontains 'scans.db') { Remove-Item $file; Log 'FAILED: archive is incomplete (no scans.db)'; exit 1 }

Get-ChildItem $Dir -Filter 'agrobotai_pi_*.tgz' | Sort-Object Name -Descending | Select-Object -Skip $Keep | Remove-Item
Log ("OK: {0} ({1:N1} MB, {2} files)" -f (Split-Path $file -Leaf), ((Get-Item $file).Length / 1MB), $list.Count)
exit 0
