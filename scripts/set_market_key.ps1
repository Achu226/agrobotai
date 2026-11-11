<#
Stores your free data.gov.in API key (for mandi prices) on this laptop and on the Raspberry Pi.

  powershell -ExecutionPolicy Bypass -File scripts\set_market_key.ps1

1. Register free at https://data.gov.in (Sign Up), open "My Account" and copy your API key.
2. Run this script and paste the key when asked (it is not shown on screen).
#>
param([string]$PiHost = 'agrobotai-pi.local')
$Root = Split-Path $PSScriptRoot -Parent
$secure = Read-Host 'Paste your data.gov.in API key' -AsSecureString
$key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)).Trim()
if ($key -notmatch '^[A-Za-z0-9]{20,}$') { Write-Host 'That does not look like a data.gov.in API key (letters and digits only).' -ForegroundColor Red; exit 1 }

$envFile = Join-Path $Root '.env'
$lines = @(Get-Content $envFile -ErrorAction SilentlyContinue | Where-Object { $_ -notmatch '^DATA_GOV_API_KEY=' }) + "DATA_GOV_API_KEY=$key"
[IO.File]::WriteAllText($envFile, (($lines -join "`n") + "`n"))
Write-Host 'Saved on this laptop (.env). Restart start.bat to use it here.' -ForegroundColor Green

# The key goes to the Pi through SSH's input, never on a command line
$remote = 'cd ~/agrobotai_edge && read -r k && sed -i "/^DATA_GOV_API_KEY=/d" .env && echo "DATA_GOV_API_KEY=$k" >> .env && sudo systemctl restart agrobotai-edge && echo saved'
$out = $key | ssh -o BatchMode=yes -o ConnectTimeout=10 "agrobot@$PiHost" $remote 2>&1
if ("$out" -match 'saved') { Write-Host 'Saved on the Raspberry Pi and restarted it. Prices now show in the app (Weather tab).' -ForegroundColor Green }
else { Write-Host "Could not reach the Pi ($PiHost). Turn it on and run this script again." -ForegroundColor Yellow }
