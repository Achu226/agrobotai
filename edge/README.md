# AGROBOTAI Edge-AI on Raspberry Pi 4

The laptop (RTX 4050) trains the models. The Pi runs the **same AGROBOTAI server** that the laptop runs, but uses
**ONNX Runtime on the CPU** instead of PyTorch/CUDA. The phone app works with it unchanged: sign-in, scans, history,
PDF reports, IoT sensors, diary, library and weather.

- The ONNX files are exported from the real trained checkpoints by `scripts/export_onnx.py`.
- The export is rejected unless every test photo gets the same top class as PyTorch.
- The model version strings are identical, so a Pi scan and a laptop scan of one photo can be compared.

| Model | File on the Pi | Classes | Input |
|---|---|---|---|
| Disease (EfficientNetV2-S) | `models/onnx/disease_model.onnx` (81 MB) | 16: tomato, potato, bell pepper, plus `Other_plant` | 224×224 RGB, ImageNet mean/std, NCHW |
| Pest (EfficientNetV2-S) | `models/onnx/pest_model.onnx` (81 MB) | 10: 9 insects plus `no_pest` | same |

**Not available on the Pi:**
- **Voice** (Whisper and the voice output) is too heavy for a Pi 4.
- **Grad-CAM heatmaps** need PyTorch.
- **AI farmer advice** needs Ollama. Advice is shown as "unavailable", never invented. The diagnosis, confidence, severity and dosage table still work.

## 1. Write the microSD card (laptop, once)

> Writing the card **erases everything on it**. Check the drive letter and size (about 29–32 GB) before you write.

1. Put the microSD card into a card reader. A USB-C power cable cannot read the card.
2. Install **Raspberry Pi Imager**: `winget install RaspberryPiFoundation.RaspberryPiImager`
3. In Imager, choose:
   - **Device:** Raspberry Pi 4
   - **OS:** Raspberry Pi OS (64-bit) or Raspberry Pi OS Lite (64-bit)
   - **Storage:** the 32 GB card
4. Click **Edit settings** and set:

   | Tab | Setting | Value |
   |---|---|---|
   | General | Hostname | `agrobotai-pi` |
   | General | Username | `agrobot`, with a password you choose |
   | General | Wireless LAN | your Wi-Fi name and password, country **IN** |
   | General | Locale | Asia/Kolkata |
   | Services | Enable SSH | password authentication |

5. Write the card. Put it in the Pi and power it on.
6. Wait 2–3 minutes on the first boot: the Pi resizes the card and joins Wi-Fi.

## 2. Install from the laptop (one command)

```powershell
cd E:\AGROBOTAI
powershell -ExecutionPolicy Bypass -File scripts\deploy_to_pi.ps1 -SetupKey
```

The script does the following:
- **Finds the Pi:** first by the name `agrobotai-pi.local`, then by scanning the Wi-Fi for a Raspberry Pi hardware address with SSH open.
- **Asks for the Pi password once.** You type it into ssh yourself; it is never stored. It then installs an SSH key so later runs need no password.
- **Copies about 143 MB:** code, the ONNX models and the web build.
- **Runs `install_pi.sh`:** OS update, Python venv, packages, `.env`, sensor token and the administrator account.
- **Starts the server and tests it** with a real leaf photo.

To push new code or models later, without re-installing anything:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy_to_pi.ps1 -UpdateOnly
```

After retraining on the laptop, the deploy script re-exports the ONNX models automatically if the `.pt` files are newer. A re-deploy never replaces `.env`, accounts or scans on the Pi.

## 3. Start / stop on the Pi

```bash
ssh agrobot@agrobotai-pi.local
cd ~/agrobotai_edge
./start.sh          # checks packages + models, refuses a second copy, waits until the models are loaded
./stop.sh
tail -f logs/server.log
```

**Start on boot (optional).** Do this only after `./start.sh` works:

```bash
sed "s#__DIR__#$HOME/agrobotai_edge#g; s#__USER__#$USER#g" agrobotai-edge.service | sudo tee /etc/systemd/system/agrobotai-edge.service
sudo systemctl daemon-reload && sudo systemctl enable --now agrobotai-edge
```

## 4. Phone app

On the same Wi-Fi, the app scans for an AGROBOTAI server on port 8000 and finds the Pi by itself.

To enter the address yourself: **Login → Change → `http://<pi-ip>:8000`**. `start.sh` prints the address, or run `hostname -I` on the Pi.

Do not use `localhost` on the phone. If the laptop's `start.bat` is also running, the app may find the laptop first, so type the Pi's address in that case.

## 5. Security

- From the Wi-Fi, only `/health`, `/api/v1/*` and `/models/*` are reachable. Everything except `/health` needs a signed-in account.
- The web dashboard and admin page answer only on the Pi itself. Use them from the laptop through an SSH tunnel: `ssh -L 8000:127.0.0.1:8000 agrobot@agrobotai-pi.local`, then open http://localhost:8000/#admin.
- Uploads are limited to `MAX_UPLOAD_MB` (10 MB) and validated as real images.
- `.env` holds the sensor token and has permissions 600.
- Don't forward port 8000 on your router: the Pi must not be reachable from the internet.
- **Firewall (optional).** This changes system settings, so decide yourself:

  ```bash
  sudo apt install ufw
  sudo ufw allow from 192.168.1.0/24 to any port 22,8000 proto tcp
  sudo ufw enable
  ```

## 6. Sensors

The sensor agent is in `sensors/`. `install_pi.sh` points it at this Pi (`http://127.0.0.1:8000`) with the right token. Wiring, calibration and testing are in `sensors/README.md`. Run `--test` first; it prints real readings and sends nothing.

Safety rules:
- GPIO pins are **3.3 V only**. Never connect 5 V or 12 V signals to them.
- The RS485 soil sensor connects through the USB-RS485 adapter, with its own 12 V supply.
- No pump or relay is switched by this software. Add one only with a relay module, a separate pump supply and real moisture readings.

## 7. AI advice, health card, backups

- **AI advice and chat** come from the laptop's Ollama (`gemma3:4b`), set with `OPENAI_BASE_URL=http://YOUR-LAPTOP-NAME.local:11434/v1` in the Pi's `.env`.
  - When the laptop is off, the app shows the labelled offline rule book within about 3 s.
  - The Pi's own `gemma3:1b` fallback is **turned off**, because in testing on 2026-11-04 it gave wrong Tamil advice and took over 4 minutes for scan advice.
  - It is still installed. To try it again, set `ADVISOR_FALLBACK_URL=http://127.0.0.1:11434` and `ADVISOR_FALLBACK_MODEL=gemma3:1b`, then run `sudo systemctl enable --now ollama`.

  - On the laptop, Ollama listens on the network (`OLLAMA_HOST=0.0.0.0:11434`). The firewall rule **"AGROBOTAI Ollama (Raspberry Pi only)"** allows only the Pi's address (192.168.1.17).
  - If the Pi gets a new address, update that rule, or reserve the address in the router.
- **Server device card.** The app's IoT tab shows the Pi's real CPU temperature, power warnings, memory, storage and uptime (`GET /api/v1/device/status`).
- **Nightly backup.** The laptop's scheduled task **"AGROBOTAI Pi backup"** runs `scripts\backup_pi.ps1` at 21:00, or later if the laptop was off.
  - It copies accounts, scans, photos and `.env` to `backups\pi\` and keeps the last 14.
  - To restore, unpack the archive into `~/agrobotai_edge/outputs/` on the Pi. `scans.db` goes there and `env` becomes `.env`.

### Turning the Pi off, auto-off and the website

- **Safe turn-off.** An admin can use **IoT → Server device → Turn off Pi** in the app (`POST /api/v1/device/shutdown`). This works only on a Pi, never on the laptop. To start it again, plug it in.
- **Auto-off.** Set `AUTO_OFF_IDLE_HOURS=3` in the Pi's `.env` (0 = never).
  - The Pi turns off after 3 h with no request from any phone or laptop. An open phone app counts as use.
  - The Pi cannot switch itself back on; someone must plug it in.
  - If it is off at 21:00, that night's laptop backup is skipped. The backup log says so.
- **Website.** The laptop admin page (`http://localhost:8000/#admin`) shows the Pi's live health and logins.
  - The laptop's `.env` holds `PI_URL` and `PI_STATUS_TOKEN`. The Pi's `.env` holds `STATUS_TOKEN`, a random key with the same value.
  - Without the key, the Pi's `/api/v1/device/report` answers 401.
- **Scan speed.** `INFERENCE_TTA=false` makes scans use 1 view instead of 5, which is faster. Switch it only after measuring accuracy.

### More crops, spray planner, prices, outbreaks (2026-11-10)

- **48-class disease model** (if it passes the comparison): rice, banana and 11 more PlantVillage crops on top of tomato/potato/pepper.
  - Data: `scripts/download_leaf_datasets.py` then `scripts/build_extended_dataset.py`. Licences are listed in `data/disease_ext/sources.json`.
  - Training and comparison: `scripts/train_extended_model.py`, then `scripts/compare_disease_models.py`.
  - The server takes its class list from `models/disease_classes.json`, which travels with the model file.
- **Spray planner.** `GET /api/v1/spray-plan` and a Weather-tab card. It uses the real hourly forecast: no rain for 6 h, wind 3–15 km/h, below 32 °C, daylight.
- **Market prices.** `GET /api/v1/market-prices` and a Weather-tab card, from Agmarknet on data.gov.in. The prices need your free key; run `scripts\set_market_key.ps1`.
- **Fertilizer bag calculator.** `GET /api/v1/fertilizer` and a Weather-tab card. It turns the Soil Health Card N-P-K (kg per acre or per hectare) into bags of Urea (45 kg), DAP (50 kg) and MOP (50 kg). All P comes from DAP; urea makes up the rest of the N.
- **Profit book.** The farm diary has two new types, `labour` and `sale`. For a sale, the amount is the money received. The diary shows spent, earned and profit for each plot.
- **Disease alerts near you.** `GET /api/v1/outbreaks/nearby` and a Weather-tab card: confirmed diseases and pests from other farmers in the same village (the `location` of the account) in the last 14 days. Counts only.
- **Harvest-safe date.** The spray calculator shows the first harvest-safe date and an "I sprayed this today" button, which saves the spray in the diary with a reminder on that date.
- **Repeating reminders.** A diary reminder can repeat every 1 to 365 days (`repeat_days`); the server moves a passed date to the next one.
- **Today summary.** `GET /api/v1/today` and a card at the top of the app's home screen: spray verdict now, reminders due today, nearby and sensor alerts, and the last 7 days (scans, spent, earned). Only the caller's real data.
- **Pi health warnings.** `GET /api/v1/alerts` now also returns `pi_hot` (CPU at or above `ALERT_PI_TEMP_C`, default 75) and `pi_low_power` (under-voltage now). The app notifies each once.
- **Exports.** `GET /api/v1/export.csv?what=diary|scans` (own records) and `GET /api/v1/admin/outbreaks.csv` (admin), as CSV files for Excel.
- **Home-garden mode** is a setting inside the app (the pot icon in the top bar); the server is not involved.
- **Farmer website page.** Open `http://<server>:8000/#farm` and sign in with the app account. It has weather, the spray planner, market prices, the fertilizer calculator and the profit book.
- **Outbreak dashboard.** The laptop admin page lists confirmed diseases and pests of the last 30 days by village, for laptop + Pi.

## 8. Check it from the laptop

```powershell
.venv\Scripts\python.exe edge\test_edge_api.py http://<pi-ip>:8000 "data\disease\test\Tomato_Late_blight\<photo>.jpg"
```

This checks health, model status, invalid-image rejection, disease and pest prediction, a saved scan and the PDF report.

Diagnostics on the Pi:

```bash
cat /proc/device-tree/model; free -h; df -h /; hostname -I; python3 --version; vcgencmd get_throttled; vcgencmd measure_temp
```

`get_throttled` should print `throttled=0x0`. Anything else means the power supply is too weak (use the official 5 V 3 A supply) or the Pi is overheating.

### Farm Wi-Fi, USB backup, expert questions, crop calendar (2026-11-13)

- **Farm Wi-Fi (no router needed).** `farm_wifi.sh` + `agrobotai-farm-wifi.service`: at boot the Pi waits 60 s for its normal Wi-Fi; if there is none it starts its own Wi-Fi **AGROBOTAI**.
  - Phones join AGROBOTAI and tap *Find server on Wi-Fi*; the server is `http://10.42.0.1:8000`.
  - See the password (random, made on the Pi): `sudo ./farm_wifi.sh password`. Stop it: `sudo ./farm_wifi.sh off`.
  - One Wi-Fi radio: while the hotspot is on, the Pi is not on the home Wi-Fi and the laptop backup cannot reach it. It stays on until `off` or a reboot.
  - Enable: `sed "s#__DIR__#$HOME/agrobotai_edge#g" agrobotai-farm-wifi.service | sudo tee /etc/systemd/system/agrobotai-farm-wifi.service && sudo systemctl daemon-reload && sudo systemctl enable agrobotai-farm-wifi`
- **USB backup.** `usb_backup.sh` + `agrobotai-usb-backup.timer`: every day at 21:00 (or at the next boot) the Pi copies the same archive as the laptop backup to `agrobotai_backups/` on a plugged-in USB stick, keeping 7. No stick = skipped (`logs/usb_backup.log`). The archive holds password hashes and `.env`: keep the stick safe.
- **Ask an expert.** `POST /api/v1/scans/{id}/ask`. The admin page lists *Questions from farmers*; the answer is the review comment, shown on the scan and on the Today card.
- **Crop calendar.** `GET/POST /api/v1/calendar` (10 crops): sowing date → dated tasks saved as diary reminders. Timings are general and approximate.
- **3-photo scan.** `/api/v1/analyze` accepts `file2`, `file3`: up to 3 leaves of one plant, averaged for the disease decision.
- **Plant name.** The crop is named only when the model's probabilities for that crop add up to at least 90 %; otherwise "Crop not identified".
