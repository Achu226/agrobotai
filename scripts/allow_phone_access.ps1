# Lets phones on the home Wi-Fi reach the AGROBOTAI server. Run elevated by scripts\phone_access.py --fix
# (only after the user agrees in start.bat).
#  1. Marks connected Public networks as Private (Windows blocks inbound connections on Public networks).
#  2. Adds an inbound TCP allow rule for the server port, limited to Private networks.
param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'

Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq 'Public' } | ForEach-Object {
    Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private
}

$name = "AGROBOTAI Server $Port"
if (-not (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private | Out-Null
}
