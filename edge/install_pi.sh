#!/usr/bin/env bash
# AGROBOTAI Edge-AI installer for Raspberry Pi 4 (64-bit Raspberry Pi OS). Safe to run again.
#   bash install_pi.sh               install / update everything
#   bash install_pi.sh --no-upgrade  skip "apt full-upgrade" of Raspberry Pi OS
# Installs: OS updates, Python venv + packages (ONNX Runtime, no PyTorch/CUDA), camera + I2C tools,
# .env, sensor token, admin account. Does NOT enable a boot service, change the firewall or reboot.
set -u
cd "$(dirname "$0")"
DIR="$PWD"
UPGRADE=1
[ "${1:-}" = "--no-upgrade" ] && UPGRADE=0
ok()   { echo -e "  \e[32m[OK]\e[0m $*"; }
warn() { echo -e "  \e[33m[WARN]\e[0m $*"; }
fail() { echo -e "  \e[31m[FAIL]\e[0m $*"; exit 1; }

echo "=== AGROBOTAI Edge-AI install in $DIR ==="

# 1. Hardware / OS check
MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo unknown)
ARCH=$(uname -m)
ok "Device: $MODEL ($ARCH), $(. /etc/os-release && echo "$PRETTY_NAME")"
[ "$ARCH" = "aarch64" ] || fail "64-bit Raspberry Pi OS is required (found $ARCH). ONNX Runtime has no 32-bit ARM wheels."
FREE_MB=$(df -Pm "$DIR" | awk 'NR==2 {print $4}')
[ "$FREE_MB" -ge 1500 ] || fail "Only ${FREE_MB} MB free on the SD card; at least 1500 MB is needed."
ok "Free space: ${FREE_MB} MB"

# 2. System packages
echo "--- System packages (sudo password may be asked) ---"
sudo apt-get update -q || fail "apt-get update failed (check the internet connection)"
if [ "$UPGRADE" = 1 ]; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get -y -q full-upgrade || warn "OS upgrade had problems; continuing"
fi
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3 python3-venv python3-pip python3-dev git \
  build-essential openssh-server i2c-tools libjpeg-dev zlib1g-dev curl || fail "could not install system packages"
# Camera utilities: package name differs between Raspberry Pi OS releases
sudo apt-get install -y -q rpicam-apps-lite 2>/dev/null || sudo apt-get install -y -q libcamera-apps-lite 2>/dev/null \
  || warn "camera utilities not installed (only needed for the Pi Camera Module)"
ok "system packages installed ($(python3 --version))"
[ -f /var/run/reboot-required ] && warn "Raspberry Pi OS asks for a reboot after the upgrade. Reboot when convenient: sudo reboot"

# 3. Python environment (ONNX Runtime CPU; PyTorch/CUDA are not used on the Pi)
echo "--- Python packages (first run takes 5-15 minutes) ---"
[ -x venv/bin/python ] || python3 -m venv venv || fail "could not create venv"
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements-pi.txt || fail "pip install -r requirements-pi.txt failed"
ok "$(venv/bin/python -c 'import onnxruntime, numpy, cv2, fastapi; print(f"onnxruntime {onnxruntime.__version__}, numpy {numpy.__version__}, opencv {cv2.__version__}, fastapi {fastapi.__version__}")')"

# 4. Configuration (.env is kept on re-install)
mkdir -p logs outputs run
if [ ! -f .env ]; then
  cp .env.example .env
  ok "created .env"
fi
grep -q '^AGROBOT_BACKEND=' .env || echo 'AGROBOT_BACKEND=onnx' >> .env
grep -q '^AGROBOT_HOST=' .env || echo 'AGROBOT_HOST=0.0.0.0' >> .env
chmod 600 .env
venv/bin/python scripts/sensor_token.py > /dev/null && ok "sensor token ready (show it: venv/bin/python scripts/sensor_token.py)"
if [ -f sensors/config.example.json ] && [ ! -f sensors/config.json ]; then
  TOKEN=$(grep '^SENSOR_INGEST_TOKEN=' .env | cut -d= -f2-)
  venv/bin/python - "$TOKEN" <<'EOF'
import json, sys
cfg = json.load(open("sensors/config.example.json"))
cfg["server_url"] = "http://127.0.0.1:8000"   # the server runs on this Pi
cfg["sensor_token"] = sys.argv[1]
json.dump(cfg, open("sensors/config.json", "w"), indent=2)
EOF
  chmod 600 sensors/config.json
  ok "sensors/config.json points the sensor agent at this Pi (enable your wired sensors in it)"
fi

# 5. Models
venv/bin/python - <<'EOF' || fail "models did not load - copy models/onnx from the laptop (deploy_to_pi.ps1 does this)"
import sys
sys.path.insert(0, ".")
from src import model_registry
state = model_registry.load_all()
for name, info in state.items():
    print(f"  {'[OK]' if info['ready'] else '[FAIL]'} {name}: {info.get('version') or info['error']} ({info.get('load_seconds', '-')} s)")
sys.exit(0 if all(i["ready"] for i in state.values()) else 1)
EOF

# 6. Administrator account (needed for the admin page and reviewing scans)
if [ -t 0 ]; then
  venv/bin/python manage_users.py ensure-admin || warn "no admin account yet: venv/bin/python manage_users.py create-admin"
else
  warn "no terminal: create the admin later with  venv/bin/python manage_users.py ensure-admin"
fi

chmod +x start.sh stop.sh
echo
ok "Install finished. Start the server:  ./start.sh     Stop it:  ./stop.sh"
echo "     Phone/laptop URL: http://$(hostname -I | awk '{print $1}'):$(grep '^AGROBOT_PORT=' .env | cut -d= -f2 || echo 8000)"
