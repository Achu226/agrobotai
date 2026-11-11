# AGROBOTAI Raspberry Pi sensor agent

Sends **real** soil and air readings from a Raspberry Pi to the AGROBOTAI laptop server. They appear in the
phone app's **IoT** tab and are passed to the AI advisor. Nothing is simulated: a sensor that can't be read is
reported as missing, and the server refuses physically impossible values (for example moisture above 100%).

## 1. On the laptop

1. Run `start.bat`. It creates the sensor token on first start.
2. Show the token: `.venv\Scripts\python.exe scripts\sensor_token.py`
3. Set the laptop's Wi-Fi to **Private**: Settings → Network & internet → Wi-Fi → your network → *Private network*.
   Otherwise Windows Firewall blocks the Pi. (`start.bat` offers to do this for you.)

## 2. Wiring (Raspberry Pi 3/4/5, physical pin numbers)

| Sensor | Connect | Notes |
|---|---|---|
| **DHT22** (air temp + humidity) | VCC → pin 1 (3.3 V), DATA → pin 11 (GPIO17), GND → pin 9 | A bare sensor needs a 10 kΩ resistor between DATA and 3.3 V; modules already have one |
| **Capacitive soil moisture v1.2** | VCC → 3.3 V, GND → GND, AOUT → **ADS1115 A0** | The Pi has no analog input, so the **ADS1115** is required |
| **ADS1115** (ADC) | VDD → pin 17 (3.3 V), GND → pin 14, SCL → pin 5, SDA → pin 3, ADDR → GND | I2C address 0x48 |
| **DS18B20** waterproof probe (soil temp) | Red → pin 1 (3.3 V), Black → pin 6, Yellow → pin 7 (GPIO4) | 4.7 kΩ resistor between Yellow and 3.3 V |
| **RS485 7-in-1 NPK** (optional) | USB-RS485 adapter: A+ → sensor A (yellow), B− → sensor B (blue); sensor brown/black → 12 V supply | Register addresses differ by model; check your sensor's datasheet and edit `registers` in config.json |

Enable the interfaces: `sudo raspi-config` → *Interface Options* → **I2C** (for the ADS1115) and **1-Wire** (for the DS18B20), then reboot.

## 3. Install on the Pi

```bash
mkdir -p ~/agrobot && cd ~/agrobot
# copy agrobot_sensor_agent.py, config.example.json, requirements.txt, agrobot-sensor.service here
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp config.example.json config.json
nano config.json     # paste sensor_token, set enabled true/false for the sensors you wired
```

## 4. Calibrate the soil moisture sensor (once)

1. Hold the sensor in dry air and run `venv/bin/python agrobot_sensor_agent.py --test`. Note `soil_moisture_raw`, then put it in `calibration_dry_raw`.
2. Put the sensor in a glass of water (up to the line), run `--test` again, and put that `soil_moisture_raw` in `calibration_wet_raw`.

## 5. Test, then run

```bash
venv/bin/python agrobot_sensor_agent.py --test         # prints real readings and errors; sends nothing
venv/bin/python agrobot_sensor_agent.py --find-server  # finds the laptop on the Wi-Fi
venv/bin/python agrobot_sensor_agent.py --once         # sends one reading -> check the app's IoT tab
```

Start it automatically on boot:

```bash
sudo cp agrobot-sensor.service /etc/systemd/system/
sudo systemctl enable --now agrobot-sensor
journalctl -u agrobot-sensor -f     # live log
```

With `"server_url": "auto"`, the agent finds the laptop by itself, even after its IP address changes. If the laptop
is offline, readings are saved in `unsent_readings.jsonl` and sent when it comes back. A device that has sent nothing
for 5 minutes shows as **Disconnected** in the app.
