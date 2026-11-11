"""
Checks whether phones on the Wi-Fi can actually reach the server port, and can fix it.

Windows Firewall blocks inbound connections on networks marked "Public", and the AGROBOTAI
firewall rule only allows the port on "Private" networks. A home Wi-Fi left as Public is the
most common reason the phone app says "server did not answer".

    python scripts/phone_access.py --check   # exit 0 = phones can connect, 4 = blocked (reasons printed)
    python scripts/phone_access.py --fix     # asks Windows for admin rights (UAC) and fixes it

The fix sets the connected network(s) to Private and adds the TCP rule for the server port
(Private profile only). It is run only when the user agrees in start.bat.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX_SCRIPT = Path(__file__).resolve().parent / "allow_phone_access.ps1"
sys.path.insert(0, str(ROOT))
from src.config import SERVER_PORT as PORT  # noqa: E402  (reads AGROBOT_PORT from .env)
OK, WARN = "[OK]  ", "[WARN]"

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")


def _powershell(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)


def rule_name(port: int = PORT) -> str:
    return f"AGROBOTAI Server {port}"


def firewall_rule_exists(port: int = PORT) -> bool:
    res = subprocess.run(f'netsh advfirewall firewall show rule name="{rule_name(port)}"',
                         shell=True, capture_output=True, text=True)
    return res.returncode == 0


def public_networks() -> list[str]:
    """Names of connected networks Windows treats as Public (inbound connections blocked)."""
    res = _powershell(
        "Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, "
        "@{n='Category';e={\"$($_.NetworkCategory)\"}} | ConvertTo-Json -Compress")
    if res.returncode != 0 or not res.stdout.strip():
        return []
    data = json.loads(res.stdout)
    profiles = data if isinstance(data, list) else [data]
    return [f"{p.get('Name')} ({p.get('InterfaceAlias')})" for p in profiles if p.get("Category") == "Public"]


def problems(port: int = PORT) -> list[str]:
    found = []
    if not firewall_rule_exists(port):
        found.append(f"No Windows Firewall rule allows phones to reach port {port}.")
    for net in public_networks():
        found.append(f"Wi-Fi network {net} is set to 'Public' - Windows blocks phones on Public networks.")
    return found


def check() -> int:
    found = problems()
    if not found:
        print(f"{OK} Phones on this Wi-Fi can reach port {PORT} (firewall rule present, network is Private)")
        return 0
    for p in found:
        print(f"{WARN} {p}")
    print("       The phone app will NOT be able to connect until this is fixed.")
    return 4


def fix() -> int:
    print("Asking Windows for administrator permission (click 'Yes' in the prompt) ...")
    arg_list = f"'-NoProfile','-ExecutionPolicy','Bypass','-File','\"{FIX_SCRIPT}\"','-Port','{PORT}'"
    res = _powershell(f"Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList {arg_list}")
    if res.returncode != 0:
        print(f"{WARN} The fix was cancelled or failed: {res.stderr.strip() or 'administrator permission refused'}")
        return 4
    return check()


if __name__ == "__main__":
    if "--fix" in sys.argv:
        sys.exit(fix())
    sys.exit(check())
