#!/usr/bin/env bash
# Daily copy of the Pi's data (accounts, scans, photos, .env) to a USB stick; keeps the newest 7 copies.
# Run by agrobotai-usb-backup.timer as root. No stick plugged in = skipped with a log line.
# The archive holds password hashes and the .env secrets: keep the stick somewhere safe.
set -euo pipefail
cd "$(dirname "$0")"
part=$(ls /dev/disk/by-id/usb-*-part1 2>/dev/null | head -n 1 || true)
[ -n "$part" ] || { echo "$(date -Is) no USB stick - backup skipped"; exit 0; }
mnt=$(findmnt -no TARGET "$part" || true)
if [ -z "$mnt" ]; then
  mnt=/mnt/agrobotai_usb
  mkdir -p "$mnt"
  mount "$part" "$mnt"
  trap 'sync; umount "$mnt"' EXIT
fi
dest="$mnt/agrobotai_backups"
mkdir -p "$dest"
src=$(./backup_snapshot.sh)
cp "$src" "$dest/agrobotai_$(date +%F_%H%M).tgz"
rm -f "$src"
ls -1t "$dest"/agrobotai_*.tgz | tail -n +8 | xargs -r rm --
echo "$(date -Is) backup saved to $dest ($(ls "$dest" | wc -l) copies)"
