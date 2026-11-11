"""
Startup checks run by start.bat before the server starts. Reports what is actually true;
it never marks a model "ready" (only the running server can, after loading it).

Exit codes: 0 = ok to start, 1 = fatal problem, 2 = port already in use, 3 = no admin account yet.
"""
from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

OK, WARN, FAIL = "[OK]  ", "[WARN]", "[FAIL]"


def lan_ipv4s() -> list[str]:
    ips = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent; picks the default-route interface
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    private = [ip for ip in ips if ip.startswith(("192.168.", "10.")) or
               (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31)]
    return sorted(private)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def main() -> int:
    fatal = False
    print(f"{OK} Python {sys.version.split()[0]} ({sys.executable})")

    for mod in ("fastapi", "uvicorn", "multipart", "numpy", "cv2", "PIL", "reportlab", "dotenv"):
        try:
            importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001
            print(f"{FAIL} Python package '{mod}' missing: {exc}")
            fatal = True

    try:
        import torch

        cuda = torch.cuda.is_available()
        if cuda:
            print(f"{OK} PyTorch {torch.__version__} with CUDA on {torch.cuda.get_device_name(0)}")
        else:
            print(f"{WARN} PyTorch {torch.__version__} has no CUDA - inference will run on the CPU (slower).")
            if subprocess.run("where nvidia-smi", shell=True, capture_output=True).returncode == 0:
                print("       An NVIDIA GPU is present. Install the CUDA build with:")
                print("       .venv\\Scripts\\python.exe -m pip install --upgrade torch torchvision "
                      "--index-url https://download.pytorch.org/whl/cu130")
    except Exception as exc:  # noqa: BLE001
        print(f"{FAIL} PyTorch is not importable: {exc}")
        fatal = True

    if not (ROOT / ".env").exists():
        print(f"{WARN} .env not found - using defaults. Copy .env.example to .env to configure the server.")
    else:
        print(f"{OK} .env found")

    from src import config

    for name in ("disease_model.pt", "pest_model.pt"):
        path = config.MODELS_DIR / name
        if not path.exists():
            print(f"{WARN} models/{name} is MISSING - that analysis will be reported as unavailable.")
            continue
        try:
            import torch

            ckpt = torch.load(str(path), map_location="cpu")
            meta = ckpt if isinstance(ckpt, dict) and "model_state_dict" in ckpt else {}
            arch = meta.get("model_name", "legacy state_dict")
            val = meta.get("val_accuracy")
            print(f"{OK} models/{name}: {arch}, {len(meta.get('classes', [])) or '?'} classes"
                  + (f", val acc {val:.2f}% at training time" if val else "")
                  + " (file readable; the server confirms it loads)")
        except Exception as exc:  # noqa: BLE001
            print(f"{FAIL} models/{name} cannot be read: {exc}")
    cal = config.MODELS_DIR / "calibration.json"
    print(f"{OK} confidence calibration found" if cal.exists() else
          f"{WARN} models/calibration.json missing - run scripts\\calibrate_models.py (confidences stay uncalibrated)")

    if not os.getenv("WEATHER_API_KEY"):
        print(f"{OK} Weather: Open-Meteo (free, no key, needs internet). Set WEATHER_API_KEY to use WeatherAPI.com.")
    if not config.SENSOR_INGEST_TOKEN:
        # The Raspberry Pi agent needs a token; create it now so the IoT tab works after this start
        from scripts.sensor_token import ensure_token

        token, _ = ensure_token()
        os.environ["SENSOR_INGEST_TOKEN"] = token
        print(f"{OK} Created the Raspberry Pi sensor token in .env (show it with: python scripts\\sensor_token.py)")
    else:
        print(f"{OK} Raspberry Pi sensor token set (show it with: python scripts\\sensor_token.py)")

    # Farmer advice/chat model (fluent Tamil and other Indian languages)
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as res:
            installed = {m["name"] for m in json.loads(res.read().decode()).get("models", [])}
        if config.ADVISOR_MODEL in installed:
            print(f"{OK} Advisor model {config.ADVISOR_MODEL} installed (advice and chat in 12 languages)")
        else:
            print(f"{WARN} Advisor model {config.ADVISOR_MODEL} is not installed - Tamil/Indian-language advice will be poor.")
            print(f"       Install it once with:  ollama pull {config.ADVISOR_MODEL}")
    except Exception:  # noqa: BLE001 - Ollama not running yet; start.bat starts it next
        print(f"{WARN} Ollama is not running yet - it is started next; advice needs model {config.ADVISOR_MODEL}.")

    port = config.SERVER_PORT
    if not port_free(port):
        print(f"{FAIL} Port {port} is already in use. Is AGROBOTAI already running? "
              f"Check http://localhost:{port}/health or close the other server window.")
        return 2

    ips = lan_ipv4s()
    if ips:
        for ip in ips:
            print(f"{OK} Phone server URL: http://{ip}:{port}")
    else:
        print(f"{WARN} No private LAN IPv4 address found. Connect the laptop to Wi-Fi (run 'ipconfig' to check).")

    # Firewall + Public/Private network check; start.bat offers the fix (scripts/phone_access.py --fix)
    from scripts.phone_access import problems

    blocked = problems(port)
    for msg in blocked:
        print(f"{WARN} {msg}")
    if not blocked:
        print(f"{OK} Firewall allows phones on this Wi-Fi to reach port {port}")

    from src import store

    store.migrate()
    if store.count_admins() == 0:
        print(f"{WARN} No administrator account exists yet.")
        return 1 if fatal else 3
    print(f"{OK} {store.count_admins()} administrator account(s)")
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
