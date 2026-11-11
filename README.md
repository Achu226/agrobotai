# AGROBOTAI — leaf doctor for farmers and home gardeners

Photograph a leaf with the phone app and get the disease, the pest, how much of the leaf is affected,
what to do (in Tamil, English and 10 more Indian languages) and when it is safe to spray.
Runs offline on a laptop or a Raspberry Pi on the farm's Wi-Fi — no cloud, no account outside your network.

[![Latest release](https://img.shields.io/github/v/release/Achu226/agrobotai)](https://github.com/Achu226/agrobotai/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Achu226/agrobotai/total)](https://github.com/Achu226/agrobotai/releases)
[![Licence: MIT](https://img.shields.io/badge/code-MIT-green)](LICENSE)
![Flutter](https://img.shields.io/badge/app-Flutter-02569B)
![FastAPI](https://img.shields.io/badge/server-FastAPI-009688)
![Raspberry Pi](https://img.shields.io/badge/edge-Raspberry%20Pi%204-C51A4A)

**⬇️ Download:** the Android app and the trained disease model are on the
[Releases page](https://github.com/Achu226/agrobotai/releases/latest).

**Using AGROBOTAI in your project, college work or farm?**
[Tell us here](https://github.com/Achu226/agrobotai/issues/new?template=using-agrobotai.yml) — it takes a minute and
helps the project. ⭐ Star the repo if it helped you.

## What it does

| | |
|---|---|
| 🍃 **Disease check** | 48 classes, 16 crops: tomato, potato, bell pepper, rice, banana, maize, grape, apple, orange, peach, cherry, strawberry, squash, soybean, blueberry, raspberry. Leaves of other plants are reported as "not a supported crop", never guessed. |
| 🐛 **Pest check** | 9 pests (aphids, armyworm, beetle, bollworm, grasshopper, mites, mosquito, sawfly, stem borer) + "no pest". |
| 🤔 **Honest when unsure** | Calibrated confidence; below the gate the app says "not sure, take another photo" instead of a wrong answer. |
| 💬 **Advice & chat** | Integrated pest management advice per disease; voice questions; offline LLM (Ollama, gemma3:4b) for Tamil chat. |
| 🧴 **Spray planner** | From the real hourly forecast (Open-Meteo): no rain for 6 h, wind 3–15 km/h, below 32 °C. |
| 🧮 **Dosage & fertilizer** | Spray tank mixes; Soil Health Card N-P-K → bags of Urea/DAP/MOP. |
| 💰 **Farm diary & profit book** | Sprays, fertilizer, labour and sales per plot, with one-time or repeating reminders ("water every 3 days") and profit per plot. |
| 📣 **Disease alerts near you** | What other farmers' scans confirmed in your village in the last 14 days (counts only, never names). |
| 📤 **Records export** | Diary and scans as a CSV file for Excel (bank, agriculture officer, own books); the website also lists your scans with PDF reports. |
| 🗓️ **Today card** | Home screen: spraying now, reminders due today, alerts, and the last 7 days at a glance; a Sunday-morning weekly nudge. |
| 🪴 **Home-garden mode** | For pots and terraces: spray doses per litre, farm-only tools hidden. |
| 📷 **Before / after photos** | First and latest photo of each plot side by side, with the affected-area trend. |
| 🎙️ **Voice note** | Speak a diary note instead of typing (Whisper on the server). |
| 🌡️ **Pi health warnings** | Phone notification when the Raspberry Pi overheats or its power supply is weak. |
| 🔁 **Rescan reminder** | After a disease result: "remind me to scan again in 7 days", so the recovery tracker gets a second point. |
| ☎️ **Kisan Call Centre** | Every uncertain or disease result shows India's free farmer helpline (1800-180-1551) with a copy button. |
| 📚 **Offline guide** | The disease & pest guide is saved on the phone and shown without a connection. |
| 📊 **Where the money goes** | Spending per activity (labour, spray, seed…) in the profit card. |
| 🧺 **Harvest-safe date** | "I sprayed this today" records the spray and reminds you on the first day it is safe to harvest. |
| 📈 **Recovery tracker** | Affected-area trend per plot across scans. |
| 🛒 **Market prices** | Agmarknet mandi prices (needs a free data.gov.in key). |
| 📡 **IoT** | Raspberry Pi / ESP32 soil-moisture and weather sensors with alerts. |
| 🗺️ **Outbreak dashboard** | Admin website: confirmed diseases/pests per village. |
| 📶 **Works offline** | Scans taken without a connection are queued and uploaded later. |

## Results (held-out test photos, never used in training)

| Test | Accuracy |
|---|---|
| Lab photos, tomato/potato/pepper | 99.71% |
| New crops (rice, banana, 11 PlantVillage crops) | 98.28% |
| Outdoor field photos (PlantDoc), raw model | 55.88% |
| Outdoor field photos, full app | 60% correct · 25% "not sure" · 13% wrong |
| Pest model | 99.78%; 0 false alarms on 534 pest-free leaves |

Outdoor photos are the weak spot: treat a field result as a first opinion.

## Parts

| Folder | What |
|---|---|
| `server.py`, `src/` | FastAPI server, models, advice, SQLite store (`/api/v1`) |
| `agrobot_flutter_app/` | Android app (Flutter) |
| `frontend/` | Website (React + Vite): diagnosis, `#farm` farmer page, `#admin` dashboard |
| `edge/` | Raspberry Pi 4 server (ONNX Runtime), install and deploy scripts |
| `iot/` | Sensor agent for the Pi |
| `scripts/` | Dataset download/build, training, calibration, evaluation, deploy |
| `tests/` | Server tests (`pytest`); app tests in `agrobot_flutter_app/test` |

## Run it (Windows laptop)

```bat
SETUP_ALL.bat          :: Python venv, packages, website build, firewall rule
start.bat              :: server on http://<laptop-ip>:8000
```

Model weights are too big for git. From the [latest release](https://github.com/Achu226/agrobotai/releases/latest) put
`disease_model.pt`, `disease_classes.json` and `calibration.json` into `models/`, and `disease_model.onnx` + `disease_model.json`
into `models/onnx/` (for the Raspberry Pi).
The **pest model is not published**: the source licence of its training photos is not confirmed. Without it the app says
"pest model unavailable" and everything else works; train your own with `run_training.py` and your own insect photos.
Copy `.env.example` to `.env` and edit it; never commit `.env`.

Phone app: `cd agrobot_flutter_app && flutter build apk --release`, then in the app *Login → Change server*.
Raspberry Pi: see [`edge/README.md`](edge/README.md).

Retrain: `scripts/download_leaf_datasets.py` → `scripts/build_extended_dataset.py` → `scripts/train_extended_model.py`
→ `scripts/compare_disease_models.py` → `scripts/calibrate_models.py` → `scripts/export_onnx.py`.

## Datasets and credits

The models are trained on these public datasets (not included in this repository):

| Dataset | Licence |
|---|---|
| PlantVillage (Hughes & Salathé; `mohanty/PlantVillage`) | CC BY-SA 3.0 |
| PlantDoc (Singh et al., 2020) | CC BY 4.0 |
| Rice leaf diseases (Sethy et al., Mendeley 10.17632/fwcj7stb8r.2) | CC BY 4.0 |
| Rice (Bangladesh), BananaLSD (Mendeley 10.17632/9tb7k297ff.1), chilli, betel, turmeric — via Project-AgML | CC BY 4.0 |
| Beans (AI Lab Makerere) | MIT |

Because the disease model is trained on PlantVillage (CC BY-SA), the released model weights are shared under
**CC BY-SA 4.0** with the credits above.

## Cite

If you use AGROBOTAI in research or a college project, please cite it: GitHub shows a **"Cite this repository"**
button (from [`CITATION.cff`](CITATION.cff)).

## Licence

Source code: [MIT](LICENSE). Model weights: CC BY-SA 4.0 (see above). Datasets: their own licences.

AGROBOTAI gives a first opinion, not a guarantee. Check pesticide labels and local agriculture officers before spraying.
