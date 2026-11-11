#!/usr/bin/env python3
"""
AGROBOTAI Raspberry Pi sensor agent.

Reads the sensors that are physically connected and sends the readings to the AGROBOTAI laptop
server (POST /api/v1/sensors/readings). It never makes up a value: a sensor that cannot be read
is reported as missing (None) and logged, and nothing is sent when no sensor could be read.

Supported sensors (enable the ones you have in config.json):
  dht22        air temperature (°C) + humidity (%)          GPIO data pin, adafruit-circuitpython-dht
  ds18b20      soil temperature probe (°C)                   1-Wire (GPIO4), no extra library
  soil_ads1115 capacitive soil moisture v1.2 via ADS1115 ADC  I2C, adafruit-circuitpython-ads1x15
  rs485_npk    7-in-1 soil sensor (moisture, temp, EC, pH, N, P, K) over RS485/Modbus, minimalmodbus

Usage:
  python3 agrobot_sensor_agent.py --test      # read sensors and print, send nothing
  python3 agrobot_sensor_agent.py --once      # read and send one reading
  python3 agrobot_sensor_agent.py             # run forever (every interval_seconds)
  python3 agrobot_sensor_agent.py --find-server
"""
from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
import logging
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
QUEUE_PATH = HERE / "unsent_readings.jsonl"
SERVICE_NAME = "AGROBOTAI inference server"
log = logging.getLogger("agrobot-agent")


# ---------------------------------------------------------------- sensors

def read_dht22(cfg: dict) -> dict:
    import adafruit_dht  # pip install adafruit-circuitpython-dht
    import board

    pin = getattr(board, f"D{int(cfg.get('gpio', 17))}")
    dht = adafruit_dht.DHT22(pin, use_pulseio=False)
    try:
        # DHT sensors often fail single reads; retry a few times, never substitute a value
        for _ in range(5):
            try:
                t, h = dht.temperature, dht.humidity
                if t is not None and h is not None:
                    return {"air_temp_c": round(float(t), 1), "humidity_pct": round(float(h), 1)}
            except RuntimeError:
                pass
            time.sleep(2.2)
        raise RuntimeError("DHT22 gave no valid reading after 5 tries (check wiring and the 10k pull-up)")
    finally:
        dht.exit()


def read_ds18b20(cfg: dict) -> dict:
    devices = glob.glob("/sys/bus/w1/devices/28-*/w1_slave")
    if cfg.get("device_id"):
        devices = [d for d in devices if cfg["device_id"] in d]
    if not devices:
        raise RuntimeError("No DS18B20 found. Enable 1-Wire (sudo raspi-config > Interface Options) and check the 4.7k pull-up.")
    lines = Path(devices[0]).read_text().splitlines()
    if not lines or not lines[0].strip().endswith("YES") or "t=" not in lines[-1]:
        raise RuntimeError("DS18B20 CRC check failed")
    temp = int(lines[-1].split("t=")[1]) / 1000.0
    if temp == 85.0:  # power-on reset value, not a measurement
        raise RuntimeError("DS18B20 returned its 85 °C reset value")
    return {"soil_temp_c": round(temp, 2)}


def read_soil_ads1115(cfg: dict) -> dict:
    import adafruit_ads1x15.ads1115 as ADS  # pip install adafruit-circuitpython-ads1x15
    import board
    import busio
    from adafruit_ads1x15.analog_in import AnalogIn

    ads = ADS.ADS1115(busio.I2C(board.SCL, board.SDA), address=int(str(cfg.get("i2c_address", "0x48")), 16))
    chan = AnalogIn(ads, getattr(ADS, f"P{int(cfg.get('channel', 0))}"))
    raw = sum(chan.value for _ in range(10)) / 10
    dry, wet = float(cfg["calibration_dry_raw"]), float(cfg["calibration_wet_raw"])
    if dry == wet:
        raise RuntimeError("Calibrate first: calibration_dry_raw and calibration_wet_raw must differ (see README)")
    pct = (dry - raw) / (dry - wet) * 100.0  # capacitive sensors read lower when wetter
    return {"soil_moisture_pct": round(min(100.0, max(0.0, pct)), 1), "soil_moisture_raw": round(raw)}


def read_rs485_npk(cfg: dict) -> dict:
    import minimalmodbus  # pip install minimalmodbus

    inst = minimalmodbus.Instrument(cfg.get("port", "/dev/ttyUSB0"), int(cfg.get("slave_address", 1)))
    inst.serial.baudrate = int(cfg.get("baudrate", 9600))
    inst.serial.timeout = 1.0
    regs = cfg.get("registers") or {}
    out = {}
    for key, spec in regs.items():  # {"soil_ph": {"address": 3, "scale": 0.1, "signed": false}, ...}
        value = inst.read_register(int(spec["address"]), 0, functioncode=3, signed=bool(spec.get("signed", False)))
        out[key] = round(value * float(spec.get("scale", 1)), 2)
    if not out:
        raise RuntimeError("rs485_npk has no registers configured")
    return out


SENSORS = {"dht22": read_dht22, "ds18b20": read_ds18b20, "soil_ads1115": read_soil_ads1115, "rs485_npk": read_rs485_npk}


def read_all(config: dict) -> tuple[dict, dict]:
    readings, errors = {}, {}
    for name, cfg in (config.get("sensors") or {}).items():
        if not cfg.get("enabled"):
            continue
        try:
            readings.update(SENSORS[name](cfg))
        except Exception as exc:  # noqa: BLE001 - report every failure, never fill in a value
            errors[name] = f"{type(exc).__name__}: {exc}"
            log.warning("sensor %s failed: %s", name, errors[name])
    return readings, errors


# ---------------------------------------------------------------- server

def _get_json(url: str, timeout: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as res:
        return json.loads(res.read().decode())


def is_agrobot(base_url: str) -> bool:
    try:
        return _get_json(f"{base_url}/health", 3).get("service") == SERVICE_NAME
    except Exception:  # noqa: BLE001
        return False


def find_server(port: int = 8000) -> str | None:
    """Scans this Pi's /24 subnet for the AGROBOTAI server (same idea as the phone app)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))  # no packet is sent
        own = s.getsockname()[0]
    prefix = own.rsplit(".", 1)[0]

    def probe(host: str) -> str | None:
        try:
            with socket.create_connection((host, port), timeout=0.7):
                pass
        except OSError:
            return None
        url = f"http://{host}:{port}"
        return url if is_agrobot(url) else None

    with concurrent.futures.ThreadPoolExecutor(64) as pool:
        for url in pool.map(probe, [f"{prefix}.{i}" for i in range(1, 255)]):
            if url:
                return url
    return None


def send(base_url: str, token: str, payload: dict) -> None:
    req = urllib.request.Request(f"{base_url}/api/v1/sensors/readings", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "X-Sensor-Token": token}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as res:
        if res.status != 201:
            raise RuntimeError(f"server answered {res.status}")


def flush_queue(base_url: str, token: str) -> None:
    if not QUEUE_PATH.exists():
        return
    pending = [json.loads(line) for line in QUEUE_PATH.read_text().splitlines() if line.strip()]
    remaining = []
    for i, payload in enumerate(pending):
        try:
            send(base_url, token, payload)
        except Exception:  # noqa: BLE001 - keep this and everything after it for the next try
            remaining = pending[i:]
            break
    if remaining:
        QUEUE_PATH.write_text("".join(json.dumps(p) + "\n" for p in remaining))
    else:
        QUEUE_PATH.unlink()
        log.info("sent %d queued readings", len(pending))


def queue(payload: dict, max_lines: int = 5000) -> None:
    lines = QUEUE_PATH.read_text().splitlines() if QUEUE_PATH.exists() else []
    lines = (lines + [json.dumps(payload)])[-max_lines:]
    QUEUE_PATH.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- main loop

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="read sensors and print; send nothing")
    ap.add_argument("--once", action="store_true", help="send one reading and exit")
    ap.add_argument("--find-server", action="store_true", help="look for the AGROBOTAI laptop on this Wi-Fi")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not CONFIG_PATH.exists():
        print(f"Missing {CONFIG_PATH.name}. Run:  cp config.example.json config.json  and edit it (see README.md).")
        return 2
    config = json.loads(CONFIG_PATH.read_text())
    port = int(config.get("server_port", 8000))
    if args.find_server:
        url = find_server(port)
        print(url or "No AGROBOTAI server found on this network (is start.bat running? is the laptop's Wi-Fi 'Private'?)")
        return 0 if url else 1

    server = None if config.get("server_url", "auto") == "auto" else config["server_url"].rstrip("/")
    token = config.get("sensor_token", "")
    if not args.test and not token:
        log.error("sensor_token is empty. On the laptop run:  python scripts\\sensor_token.py  and copy the token here.")
        return 2

    while True:
        readings, errors = read_all(config)
        if args.test:
            print(json.dumps({"readings": readings, "errors": errors}, indent=2))
            return 0 if readings else 1
        if readings:
            payload = {"device_id": config.get("device_id", socket.gethostname()),
                       "measured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                       "readings": readings}
            try:
                if server is None or not is_agrobot(server):
                    found = find_server(port) if config.get("server_url", "auto") == "auto" else None
                    server = found or server
                if server is None:
                    raise RuntimeError("AGROBOTAI server not found on this network")
                flush_queue(server, token)
                send(server, token, payload)
                log.info("sent %s to %s", readings, server)
            except urllib.error.HTTPError as exc:
                log.error("server refused the reading: %s %s", exc.code, exc.read().decode(errors="replace")[:200])
                if exc.code in (401, 503):
                    return 2  # wrong token / ingest disabled: retrying will not help
            except Exception as exc:  # noqa: BLE001 - offline: keep the real reading for later
                queue(payload)
                log.warning("server unreachable (%s); reading queued", exc)
        else:
            log.warning("no sensor could be read; nothing sent")
        if args.once:
            return 0 if readings else 1
        time.sleep(max(5, int(config.get("interval_seconds", 60))))


if __name__ == "__main__":
    sys.exit(main())
