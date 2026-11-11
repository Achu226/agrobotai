#!/usr/bin/env bash
# Start the AGROBOTAI Edge-AI server on the Raspberry Pi.
#   ./start.sh               start in the background (log: logs/server.log)
#   ./start.sh --foreground  run in the foreground (used by the systemd service)
set -u
cd "$(dirname "$0")"
PIDFILE=run/server.pid
mkdir -p logs run

[ -x venv/bin/python ] || { echo "[FAIL] venv missing - run: bash install_pi.sh"; exit 1; }
# Load AGROBOT_HOST / AGROBOT_PORT / AGROBOT_BACKEND from .env (plain KEY=value lines)
set -a; [ -f .env ] && . ./.env; set +a
HOST=${AGROBOT_HOST:-0.0.0.0}
PORT=${AGROBOT_PORT:-8000}

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "[OK] AGROBOTAI is already running (PID $(cat "$PIDFILE")) on port $PORT"; exit 0
fi
if ss -ltn "sport = :$PORT" 2>/dev/null | grep -q LISTEN; then
  echo "[FAIL] Port $PORT is used by another program (is the systemd service running? sudo systemctl status agrobotai-edge)"; exit 1
fi
venv/bin/python -c "import onnxruntime, fastapi, uvicorn, cv2" 2>>logs/server.log || { echo "[FAIL] Python packages missing - run: bash install_pi.sh"; exit 1; }
for f in models/onnx/disease_model.onnx models/onnx/pest_model.onnx; do
  [ -f "$f" ] || echo "[WARN] $f is missing - that analysis will report 'model unavailable' until it is copied from the laptop"
done

CMD=(venv/bin/python -m uvicorn server:app --host "$HOST" --port "$PORT" --timeout-keep-alive 15 --limit-concurrency 16)
if [ "${1:-}" = "--foreground" ]; then
  exec "${CMD[@]}"
fi

echo "$(date '+%F %T') starting AGROBOTAI on $HOST:$PORT" >> logs/server.log
nohup "${CMD[@]}" >> logs/server.log 2>&1 &
echo $! > "$PIDFILE"
echo -n "Starting AGROBOTAI (loading models)"
for _ in $(seq 1 90); do
  if ! kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo; echo "[FAIL] server stopped - last log lines:"; tail -n 20 logs/server.log; rm -f "$PIDFILE"; exit 1
  fi
  if curl -fs "http://127.0.0.1:$PORT/health" -o run/health.json 2>/dev/null \
     && venv/bin/python -c "import json,sys; m=json.load(open('run/health.json'))['models']; sys.exit(0 if all(v['state']!='loading' for v in m.values()) else 1)" 2>/dev/null; then
    echo
    venv/bin/python -c "
import json; h = json.load(open('run/health.json'))
for k, v in h['models'].items(): print(f\"  {'[OK]' if v['ready'] else '[FAIL]'} {k} model: {v.get('version') or v.get('error')}\")
print('  device:', h.get('runtime', {}).get('inference_device'))"
    echo "[OK] AGROBOTAI running (PID $(cat "$PIDFILE")). Phone app server URL: http://$(hostname -I | awk '{print $1}'):$PORT"
    exit 0
  fi
  echo -n "."; sleep 1
done
echo; echo "[WARN] server started but /health did not answer within 90 s - see logs/server.log"
