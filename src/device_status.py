"""
Real health readings of the machine running the server, for the app's device card.

On a Raspberry Pi: CPU temperature, power problems (vcgencmd get_throttled), memory, storage, uptime.
A reading the machine cannot provide (for example CPU temperature on the Windows laptop) is None,
never an estimate.
"""
from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

from src import config
from src.config import ROOT_DIR

log = logging.getLogger("agrobot.device")
# Last request from a phone/laptop (not the Pi itself); the idle auto-off counts from here
_last_activity = time.monotonic()

# vcgencmd get_throttled bits (Raspberry Pi documentation)
_FLAGS = {0: "under_voltage_now", 2: "throttled_now", 3: "temp_limit_now",
          16: "under_voltage_since_boot", 18: "throttled_since_boot", 19: "temp_limit_since_boot"}


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip().rstrip("\x00")
    except OSError:
        return None


def parse_throttled(raw: str) -> dict:
    """'throttled=0x50005' -> {'raw': '0x50005', 'under_voltage_now': True, ...}"""
    value = int(raw.split("=")[-1], 16)
    return {"raw": hex(value), **{name: bool(value >> bit & 1) for bit, name in _FLAGS.items()}}


def _power() -> dict | None:
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=3)
        return parse_throttled(out.stdout.strip()) if out.returncode == 0 and "=" in out.stdout else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _memory_used_pct() -> float | None:
    info = _read("/proc/meminfo")
    if not info:
        return None
    kb = {line.split(":")[0]: int(line.split()[1]) for line in info.splitlines() if line.split()[1:2]}
    if not kb.get("MemTotal") or "MemAvailable" not in kb:
        return None
    return round(100 * (1 - kb["MemAvailable"] / kb["MemTotal"]), 1)


def is_raspberry_pi() -> bool:
    return "Raspberry Pi" in (_read("/proc/device-tree/model") or "")


def shutdown_soon(delay_s: float = 2.0) -> None:
    """Powers the Pi off once the HTTP reply has gone out (the Pi user has passwordless sudo)."""
    threading.Timer(delay_s, lambda: subprocess.run(["sudo", "-n", "shutdown", "-h", "now"], check=False)).start()


def mark_activity() -> None:
    global _last_activity
    _last_activity = time.monotonic()


def idle_watchdog(hours: float, check_every_s: float = 300, clock=time.monotonic, sleep=time.sleep, off=shutdown_soon) -> None:
    """Turns the Pi off after `hours` without any request. It cannot turn itself on again: plug it in."""
    while True:
        sleep(check_every_s)
        if clock() - _last_activity >= hours * 3600:
            log.warning("No requests for %.1f h: turning the Raspberry Pi off", hours)
            off(0)
            return


def status() -> dict:
    temp = _read("/sys/class/thermal/thermal_zone0/temp")
    uptime = _read("/proc/uptime")
    disk = shutil.disk_usage(ROOT_DIR)
    return {
        "device": _read("/proc/device-tree/model") or f"{platform.system()} {platform.machine()}",
        "hostname": platform.node(),
        "cpu_temp_c": round(int(temp) / 1000, 1) if temp and temp.isdigit() else None,
        "power": _power(),
        "memory_used_pct": _memory_used_pct(),
        "disk_free_gb": round(disk.free / 1e9, 1),
        "disk_total_gb": round(disk.total / 1e9, 1),
        "uptime_s": int(float(uptime.split()[0])) if uptime else None,
        "can_shutdown": is_raspberry_pi(),
        "auto_off_idle_hours": config.AUTO_OFF_IDLE_HOURS if is_raspberry_pi() and config.AUTO_OFF_IDLE_HOURS > 0 else None,
    }
