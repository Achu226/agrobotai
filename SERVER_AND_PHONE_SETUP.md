# AGROBOTAI — Laptop AI Server + Android Phone Setup

```
Android phone (camera)  --Wi-Fi-->  Windows laptop: start.bat -> FastAPI (port 8000) -> PyTorch models on the RTX 4050
                        <--result--  (scan saved in outputs/scans.db, photo in outputs/scan_images/)
```

The phone takes the photo; the laptop runs the trained models. If the server, a model or the network
is unavailable, the app shows that error. It never shows a sample or made-up result.

---

## 1. One-time laptop setup

1. **Python environment** — already present in `.venv` (Python 3.14, PyTorch 2.14 + CUDA 13.0).
   On a fresh machine run `SETUP_AND_RUN.bat` once; it installs Python packages and the CUDA build of PyTorch.
   Exact versions: `requirements-lock.txt`.
2. **Check the GPU is used**
   ```
   .venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   ```
   Expected: `2.14.0+cu130 True NVIDIA GeForce RTX 4050 Laptop GPU`.
3. **Model files** (already in place):

   | File | Model | Classes | Test accuracy |
   |---|---|---|---|
   | `models/disease_model.pt` | EfficientNetV2-S | 15 PlantVillage classes (tomato, potato, bell pepper) | 99.41 % (2,046 images) |
   | `models/pest_model.pt` | EfficientNetV2-S | 9 insects: aphids, armyworm, beetle, bollworm, grasshopper, mites, mosquito, sawfly, stem borer | 99.69 % (321 images) |
   | `models/calibration.json` | temperature scaling + image-quality limits | — | fitted on the validation split |

   Class order is stored inside each checkpoint and checked against `src/config.py` at load; a mismatch
   refuses to load. Re-measure with `.venv\Scripts\python.exe verify_models.py --eval`, re-fit calibration
   with `.venv\Scripts\python.exe scripts\calibrate_models.py`.
4. **Allow the port through Windows Firewall** (admin terminal, private networks only):
   ```
   netsh advfirewall firewall add rule name="AGROBOTAI Server 8000" dir=in action=allow protocol=TCP localport=8000 profile=private
   ```
   Make sure the Wi-Fi network is set to **Private** (Settings → Network & internet → Wi-Fi → your network).
   Do not add a rule for the Public profile and do not forward the port on your router.
5. **Optional `.env` settings** (copy `.env.example` to `.env` if missing):
   - `WEATHER_API_KEY` — free key from weatherapi.com. Without it the app shows *Weather unavailable*.
   - `SENSOR_INGEST_TOKEN` — shared secret for the Raspberry Pi / ESP32 gateway (see §6).
   - `ALLOW_FARMER_SIGNUP=false` — if only the admin should create farmer accounts.

## 2. Start / stop the server

- **Start:** double-click `E:\AGROBOTAI\start.bat`. It checks Python, packages, model files, CUDA, the
  port, the firewall rule and accounts, then starts the server on all interfaces (no auto-reload).
  On the first run it asks you to create the **administrator account** (username + hidden password).
- It prints the address for the phone, e.g. `[OK] Phone server URL: http://10.44.218.177:8000`
  (find it any time with `ipconfig` → "IPv4 Address" of the Wi-Fi adapter).
- **Stop:** press `Ctrl+C` in that window or close it.
- **Check it:** open `http://localhost:8000/health` on the laptop. `"ready": true` for a model means it
  really loaded and ran a test inference.
- Logs: `logs\server.log` (every request) and the start.bat window (errors).
- Development only: `start_dev.bat` (hot reload, laptop-only).

More accounts: `.venv\Scripts\python.exe manage_users.py create-admin | create-farmer | list | reset-password <user>`.

## 3. Security model

- Binding to `0.0.0.0` lets other devices on the network reach port 8000. Protection:
  - The firewall rule is limited to **private** networks.
  - Every mobile endpoint (`/api/v1/...`, `/models/status`) needs a **signed-in session**: salted
    PBKDF2 passwords, random bearer tokens, stored only as hashes, expiring after 30 days.
  - The laptop web dashboard, the old `/api/...` endpoints and `/docs` answer **only on the laptop
    itself**; requests from other devices get HTTP 403.
  - Uploads are limited to 10 MB (`MAX_UPLOAD_MB`), checked as real images, re-encoded before saving,
    and stored under server-generated names.
  - Admin accounts can only be created on the laptop. Phones can only self-register as farmers.
- No passwords or tokens are compiled into the APK.
- Debug APKs allow plain HTTP for the LAN. Release builds do not; use HTTPS for any production deployment.

## 4. Build and install the app

```
cd E:\AGROBOTAI\agrobot_flutter_app
flutter pub get
flutter build apk --debug
```

Install `build\app\outputs\flutter-apk\app-debug.apk` on the phone. Either copy it over and open it
(allow "install unknown apps"), or with USB debugging on:

```
adb install -r build\app\outputs\flutter-apk\app-debug.apk
```

Optional: bake in the laptop address with
`flutter build apk --debug --dart-define=AGROBOT_SERVER_URL=http://10.44.218.177:8000`.

## 5. Connect the phone and test (do these on the real phone)

1. Phone and laptop on the **same Wi-Fi**. Start `start.bat`.
2. Open AGROBOTAI → **Change** under the server address → enter the *Phone server URL* → **Save & test /health**.
   You should see "Server reachable", and the disease and pest models as *Ready* on *CUDA*.
   - Never use `localhost` or `127.0.0.1` on the phone; they point at the phone itself.
   - Android emulator: `http://10.0.2.2:8000`.
3. Sign in (or create a farmer account).
4. Tap **Scan leaf** → allow the camera → the live rear-camera preview appears → **Capture** →
   **Retake** or **Analyze**.
5. Check: the result shows model versions and the inference time, and the scan appears under **My scans**
   (also after restarting the app). **PDF report** opens a report built from the stored record.
6. Failure checks:
   - Stop start.bat and tap Analyze → *Server unreachable*, and no result is saved.
   - Rename `models\disease_model.pt` and restart → *disease model unavailable* in diagnostics.
7. Admin: sign in with the admin account on another phone (or the same one after signing out) → **Review** →
   open the scan → Approve / Reject. The farmer's scan then shows who reviewed it and when.

Useful Android logs while testing: `adb logcat -s flutter CameraX AndroidRuntime`.

### Common problems

| Symptom | Fix |
|---|---|
| "Cannot reach the AGROBOTAI server" | Is start.bat running? Same Wi-Fi? Firewall rule added and the network set to Private? Is the URL the laptop's IPv4 address? Some guest/campus Wi-Fi blocks devices from talking to each other — use a phone hotspot instead. |
| "Port 8000 is already in use" | Another start.bat window is open; close it (or change `AGROBOT_PORT`). |
| Model "unavailable" | Read the error in the app's diagnostics or at `/health`; check that the `models\*.pt` files exist. |
| "Photo is blurry / too dark" | The image-quality gate rejected it before inference; retake in daylight. |
| Camera permission blocked | Phone Settings → Apps → AGROBOTAI → Permissions → Camera → Allow. |

## 6. Sensors (Raspberry Pi 4B / ESP32 / RS485 NPK / DHT22 / soil moisture)

Set `SENSOR_INGEST_TOKEN` in `.env`, restart, then have the gateway POST readings:

```
POST http://<laptop-ip>:8000/api/v1/sensors/readings
X-Sensor-Token: <the token from .env>
{"device_id": "rpi-field-1", "readings": {"soil_moisture_pct": 41.5, "soil_temp_c": 27.0, "air_temp_c": 29.1,
 "humidity_pct": 71, "soil_ph": 6.6, "soil_ec": 420, "n": 38, "p": 14, "k": 120}}
```

The app shows only readings that actually arrived. A device with no data for 5 minutes is marked
**Disconnected**. Soil data alone is never used to diagnose a leaf disease.

## 7. What the results mean (and their limits)

- **Disease model:** only tomato, potato and bell pepper (15 classes). Other crops get "crop not supported".
  "No supported disease detected" is *not* proof the plant is healthy.
- **Confidence:** temperature-calibrated on the validation split. On test data, the share of correct
  predictions at a given confidence closely matches that confidence (expected calibration error, ECE, < 0.5 %).
  This holds only for photos like the training data (PlantVillage lab photos). Field photos can be less reliable.
- **Uncertain:** shown when the calibrated confidence is below 90 % (`DISEASE_UNCERTAIN_THRESHOLD`),
  when the selected crop disagrees with the model, or when the photo looks like an insect rather than a
  leaf. The app then says: "Unable to make a reliable diagnosis. Please capture a clearer image or
  consult an agricultural expert."
- **Pest model:** classifies the whole photo into 9 insects. It cannot locate or count insects (no
  bounding boxes). On ordinary leaf close-ups its guesses are ignored unless at least 97 % confident,
  because on clean leaves it is confidently wrong. With this rule: 96.6 % of pest photos are caught,
  and 2.0 % of clean leaves are falsely flagged (measured on held-out data).
- **Health index:** a documented heuristic (weighted module scores), not a validated measurement.
  "NDRE/CRI" values are RGB proxies, not true multispectral indices.
- **Analysis mode:** capture-and-analyse only. Continuous live-frame analysis is not implemented.

## 8. Tests

```
cd E:\AGROBOTAI
.venv\Scripts\python.exe -m pytest -q
cd agrobot_flutter_app
flutter analyze
flutter test
```

## 9. Voice and chat (added 2026-10-25)

- **Ask AI tab:** answers stream word by word from `gemma3:4b` (first words in about 3 s; the model stays
  loaded on the GPU for 24 h). The advisor automatically uses your latest scan; tap ✕ on the chip for a
  general question.
- **Mic:** tap the mic, speak in Tamil, English or any supported language, and tap again to stop. Whisper
  large-v3-turbo on the laptop turns speech into text (about 1–3 s) and detects the language.
- **Speaker:** the 🔊 icon on an answer, or **Listen** on an advice card, reads it aloud sentence by sentence.
  - *Offline voice* (default): Meta MMS voices on the laptop GPU, about 0.7 s per sentence, no internet needed.
  - *Natural voice*: Microsoft neural voices, about 3–4 s per sentence, needs internet.
  - Choose in the voice settings menu (icon next to the language). *Read answers aloud automatically* is
    also there.
- Models live in the Hugging Face cache (`%USERPROFILE%\.cache\huggingface`): Whisper about 1.6 GB, each
  voice about 145 MB. The MMS voices are licensed CC-BY-NC 4.0 (non-commercial use).
- **Spray calculator:** shown on a scan with a confirmed disease or pest. Doses come only from the reference
  table; findings without a verified table (for example mosaic virus) show "ask your agriculture officer"
  instead of a number.
