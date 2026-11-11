#!/usr/bin/env bash
# Consistent snapshot of the Pi's data (accounts, scans, scan photos, .env) for the laptop's nightly
# backup (scripts/backup_pi.ps1). Prints the path of the archive it made.
set -euo pipefail
cd "$(dirname "$0")"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
# SQLite online backup: safe while the server is writing
venv/bin/python -c "import sqlite3, sys; s = sqlite3.connect('outputs/scans.db'); d = sqlite3.connect(sys.argv[1]); s.backup(d); d.close()" "$tmp/scans.db"
cp .env "$tmp/env"
out=/tmp/agrobotai_backup.tgz
if [ -d outputs/scan_images ]; then
  tar -czf "$out" -C "$tmp" scans.db env -C "$PWD/outputs" scan_images
else
  tar -czf "$out" -C "$tmp" scans.db env
fi
echo "$out"
