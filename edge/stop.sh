#!/usr/bin/env bash
# Stop the AGROBOTAI Edge-AI server started with ./start.sh
cd "$(dirname "$0")"
PIDFILE=run/server.pid
if systemctl is-active --quiet agrobotai-edge 2>/dev/null; then
  echo "AGROBOTAI runs as a boot service - stop it with: sudo systemctl stop agrobotai-edge"; exit 0
fi
if [ ! -f "$PIDFILE" ] || ! kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "AGROBOTAI is not running."; rm -f "$PIDFILE"; exit 0
fi
PID=$(cat "$PIDFILE")
kill -TERM "$PID"
for _ in $(seq 1 15); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
kill -0 "$PID" 2>/dev/null && kill -KILL "$PID"
rm -f "$PIDFILE"
echo "$(date '+%F %T') stopped AGROBOTAI (PID $PID)" >> logs/server.log
echo "[OK] AGROBOTAI stopped."
