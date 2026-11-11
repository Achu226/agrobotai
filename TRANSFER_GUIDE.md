# AGROBOTAI - New Laptop Transfer Guide

## What to Copy to the New Laptop

Copy the **entire `AGROBOTAI` folder** to the new laptop (any drive works, e.g. `E:\AGROBOTAI` — all paths are relative).

### Critical files/folders (MUST copy):
| File/Folder | What | Size |
|---|---|---|
| `models/pest_model.pt` | Pest detection AI model (EfficientNetV2-S) | ~78 MB |
| `models/disease_model.pt` | Disease detection AI model (EfficientNetV2-S) | ~78 MB |
| `models/pest_classes.json` | Pest class labels | tiny |
| `models/disease_classes.json` | Disease class labels | tiny |
| `frontend/dist/` | Pre-built React web app | ~2 MB |
| `Modelfile.agri-qwen` | Ollama model config | tiny |
| `.env` | Configuration file | tiny |
| `src/` | All Python backend code | ~500 KB |
| `server.py` | FastAPI server | |
| `app.py` | Main entry point | |
| `requirements.txt` | Python dependencies list | |
| `SETUP_AND_RUN.bat` | **The one-click installer** | |

### What you can SKIP copying (saves time):
| Folder | Why skip | Size |
|---|---|---|
| `.venv/` | Will be recreated automatically by the script | ~2+ GB |
| `data/pest/` | Training data (not needed for running) | Large |
| `data/disease/` | Training data (not needed for running) | Large |
| `_installer_temp/` | Temporary files (auto-cleaned) | |
| `__pycache__/` | Python cache (auto-recreated) | |

## On the New Laptop

1. Copy the `AGROBOTAI` folder anywhere you want (e.g. `E:\AGROBOTAI`)
2. **Double-click `SETUP_AND_RUN.bat`**
3. Wait — it will automatically:
   - ✅ Install Python 3.12 (if not installed)
   - ✅ Install Node.js (if not installed)  
   - ✅ Install Ollama (if not installed)
   - ✅ Create Python virtual environment
   - ✅ Install all Python packages (PyTorch, FastAPI, OpenCV, etc.)
   - ✅ Download qwen2.5:7b base model (~4.4 GB)
   - ✅ Create agri-qwen:7b agricultural AI model
   - ✅ Launch the web application
4. Browser opens automatically → **http://localhost:8000**

## First Run Timing
| Step | Time (approx.) |
|---|---|
| Python install | 1-2 min |
| Node.js install | 1-2 min |
| Ollama install | 1-2 min |
| Python packages | 5-10 min |
| LLM model download | 5-15 min (4.4 GB) |
| **Total first run** | **~15-30 min** |

## After First Setup
Subsequent runs: just double-click `SETUP_AND_RUN.bat` — it detects everything is installed and **starts in under 10 seconds**.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Python not found" after install | Close and reopen `SETUP_AND_RUN.bat` |
| PyTorch install fails | Check internet connection, re-run the script |
| Ollama won't start | Restart the laptop, then run the script again |
| "Model files missing" warning | Make sure you copied `models/` folder |
| Frontend blank page | Make sure `frontend/dist/` folder was copied |
| Port 8000 in use | Close other apps using that port, or edit `app.py` to change the port |
