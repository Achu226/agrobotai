#!/usr/bin/env bash
# Farm Wi-Fi: when the Pi cannot join the home/farm Wi-Fi at boot, it makes its own Wi-Fi "AGROBOTAI", so phones
# connect straight to it in a field with no router. The app's "Find server on Wi-Fi" then finds http://10.42.0.1:8000.
#   sudo ./farm_wifi.sh boot       what agrobotai-farm-wifi.service runs: wait 60 s for normal Wi-Fi, else hotspot
#   sudo ./farm_wifi.sh on | off   start / stop the hotspot now (off = rejoin the normal Wi-Fi)
#   sudo ./farm_wifi.sh password   show the hotspot password (made randomly on this Pi, stored root-only)
# The Pi has one Wi-Fi radio: while the hotspot is on it is NOT on the home Wi-Fi (reach it by joining "AGROBOTAI").
# shortcut: the hotspot stays on until "off" or a reboot; add a periodic home-Wi-Fi check if that is a problem.
set -euo pipefail
CON=AGROBOTAI-hotspot
SSID=AGROBOTAI
IFACE=${AGROBOT_WIFI_IFACE:-wlan0}
PASS_FILE=/etc/agrobotai/hotspot_password

[ "$(id -u)" = 0 ] || { echo "Run with sudo."; exit 1; }

password() {
  if [ ! -s "$PASS_FILE" ]; then
    install -d -m 700 "$(dirname "$PASS_FILE")"
    (umask 077; tr -dc 'a-km-z2-9' < /dev/urandom | head -c 12 > "$PASS_FILE")  # no 1/l/0/o: easy to type on a phone
  fi
  cat "$PASS_FILE"
}

wifi_connected() { nmcli -t -f DEVICE,STATE device | grep -qx "$IFACE:connected"; }

hotspot_on() {
  nmcli device wifi hotspot ifname "$IFACE" con-name "$CON" ssid "$SSID" password "$(password)" > /dev/null
  nmcli connection modify "$CON" connection.autoconnect no  # next boot tries the normal Wi-Fi first
  echo "$(date -Is) hotspot '$SSID' on; server at http://10.42.0.1:8000"
}

case "${1:-}" in
  boot)
    for _ in $(seq 60); do
      wifi_connected && { echo "$(date -Is) normal Wi-Fi connected; no hotspot"; exit 0; }
      sleep 1
    done
    hotspot_on ;;
  on) hotspot_on ;;
  off)
    nmcli connection down "$CON" > /dev/null 2>&1 || true
    nmcli device connect "$IFACE" > /dev/null && echo "back on the normal Wi-Fi" ;;
  password) echo "Wi-Fi name: $SSID   password: $(password)" ;;
  *) sed -n 2,8p "$0"; exit 1 ;;
esac
