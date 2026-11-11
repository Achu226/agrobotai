# HANDOFF NOTE — AI Crop Health System (as of Sun Aug 30 2026)

> Paste this note (or read this file) to resume work tomorrow.
> A background training process is STILL RUNNING. Keep the PC awake/on.

## Project location
- Folder: `D:\HORTICBOTAI`
- Python venv: `D:\HORTICBOTAI\.venv` (Python 3.12, CPU-only torch, 12 cores, no GPU)
- App: FastAPI backend (`server.py`) + React frontend (`frontend/`) — run via `start.bat`
- `.env` API key is a Groq key (works)

## What was done TODAY (earlier)
1. **Fixed `start.bat`** — auto-creates `.venv`, installs missing packages, then boots
   uvicorn at http://127.0.0.1:8000
2. **Fixed the "always says Healthy / Pest Free" bug**:
   - Root cause: in `src/pest_detector.py` and `src/disease_detector.py`, any prediction
     under `LOW_CONFIDENCE_THRESHOLD` was forcibly overwritten to "Healthy".
   - Fix: now reports the TRUE top class with an `(uncertain)` suffix + a
     "confirm in field" warning when low-confidence. Added a `low_confidence` flag.
   - Lowered `LOW_CONFIDENCE_THRESHOLD` to `0.30` in `.env` and `.env.example`.
   - Frontend (`frontend/src/App.jsx`) rebuilt to show a yellow
     "Low confidence — verify in field" badge.
   - `src/ai_advisor.py` now uses the config threshold instead of hardcoded 0.45.

## ACTIVE task (background training) — most recent status
- Rewrote `train_models.py` for high accuracy: balanced dataset, class-weighted sampler,
  augmentation, 2-phase training (head-only -> full-backbone fine-tune), cosine LR,
  best-checkpoint saving, plus HELD-OUT test accuracy reporting.
- Batch runner: `run_training.py`
- **Pest training currently running in background** (log `D:\HORTICBOTAI\train2.txt`).
  Latest seen (may be further now):
    - head phase: best val 94.75%
    - fine-tune 10 epochs: reached **100.0% validation** at epoch 7–8 (on epoch ~8–9 now)
    - after 10 ft epochs it reports HELD-OUT test accuracy on `data/pest/test` (450 imgs)
- **Disease model training NOT started yet** — it runs automatically after pest finishes
  (max 500/class, head 3 + ft 8 epochs; on CPU this takes a while).

## Files changed today
| File | Change |
|---|---|
| `start.bat` | auto venv + install deps |
| `src/pest_detector.py` | show true label + low-confidence flag |
| `src/disease_detector.py` | show true label + low-confidence flag |
| `src/ai_advisor.py` | use config threshold |
| `.env`, `.env.example` | threshold 0.30, model paths -> `.pt` |
| `frontend/src/App.jsx` | low-confidence warning badge (rebuilt to `frontend/dist`) |
| `train_models.py` | major rewrite for accuracy |
| `run_training.py` | tiny runner script |
| `models/pest_model.pt`, `models/disease_model.pt` | overwritten with retrained weights (earlier 07:47 / 07:56) |

## TO CONTINUE TOMORROW
1. Check background training:
   ```
   Get-Content "D:\HORTICBOTAI\train2.txt" -Tail 30
   Get-Process | Where-Object { $_.ProcessName -like '*python*' }
   ```
   - If pest finished, the script auto-starts disease training. Wait for it.
   - If the process died/crashed, re-run:
     ```
     cd D:\HORTICBOTAI
     .venv\Scripts\python.exe -u run_training.py > train2.txt 2>&1
     ```

2. When BOTH models done, read the final "HELD-OUT TEST accuracy" lines in `train2.txt`
   (that is the real, trustworthy accuracy number).

3. Verify confidently on real held-out images:
   ```
   .venv\Scripts\python.exe -c "from src.pest_detector import load_pest_model, detect_pest; from src.image_utils import load_rgb_array; import glob; [print(detect_pest(load_rgb_array(p), load_pest_model())['display_name'], detect_pest(load_rgb_array(p), load_pest_model())['confidence']) for p in sorted(glob.glob('data/pest/test/stem_borer/*.jpg'))[:5]]"
   ```
   (same pattern for disease via `load_disease_model` / `detect_disease`)

4. Run the test suite (expect 13 passed):
   ```
   cd D:\HORTICBOTAI
   .venv\Scripts\python.exe -m pytest -q
   ```

5. Rebuild frontend only if JSX changed:
   ```
   cd D:\HORTICBOTAI\frontend
   npm run build
   ```

6. Start the app and test an upload:
   ```
   cd D:\HORTICBOTAI
   .venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
   ```
   open http://127.0.0.1:8000

## Honest limitation
- **100% accuracy on any real-world image is NOT realistic.** Validation hit 100% but
  that is a random split of the same images (some leakage risk). The true HELD-OUT test
  accuracy is the number to trust; expect ~95–99% on clean in-distribution images.
  Blurry/odd photos will show low-confidence — now shown as the correct class + "uncertain"
  instead of a fake "healthy".

## If you want even higher accuracy later
- Raise `ft_epochs`, use more disease data per class (currently 500/class), or use a bigger
  backbone (EfficientNet-B1/B2). All trade CPU time on this 12-core, no-GPU machine.
