# 🌾 HORTICBOTAI / AGROBOTAI — Session Status & Handover Documentation
**Date:** October 3, 2026  
**System Status:** Fully Operational & Verified  
**Backend:** FastAPI (`server.py`, port 8000)  
**Frontend:** React 18 + Vite 8 (`frontend/dist`)  
**AI Pipeline:** PyTorch GPU (CUDA, RTX 4050 Laptop) + OpenCV Multi-Spectral Proxies (NDRE/CRI) + Local Offline LLM (`agri-qwen:7b` via Ollama) + Microsoft Edge Neural TTS Engine (`edge-tts`)

---

## 📌 1. Major Accomplishments & Capabilities

### 1.1 Studio-Quality Tamil & Indic Neural Voice Synthesis (`edge-tts`)
- **Neural Voice Engine**: Integrated Microsoft Edge Neural TTS with zero API cost, generating studio-quality 24kHz audio in ~280ms:
  - **Tamil (`ta`)**: `ta-IN-PallaviNeural` (Female, primary) & `ta-IN-ValluvarNeural` (Male).
  - **Hindi (`hi`)**: `hi-IN-SwaraNeural` (Female) & `hi-IN-MadhurNeural` (Male).
  - **Telugu (`te`)**: `te-IN-ShrutiNeural` (Female) & `te-IN-MohanNeural` (Male).
  - **Kannada (`kn`)**: `kn-IN-SapnaNeural` (Female) & `kn-IN-GaganNeural` (Male).
  - **Malayalam (`ml`)**: `ml-IN-SobhanaNeural` (Female) & `ml-IN-MidhunNeural` (Male).
  - **Marathi (`mr`)**: `mr-IN-AarohiNeural` (Female) & `mr-IN-ManoharNeural` (Male).
  - **Bengali (`bn`)**: `bn-IN-TanishaaNeural` (Female) & `bn-IN-BashkarNeural` (Male).
  - **Gujarati (`gu`)**: `gu-IN-DhwaniNeural` (Female) & `gu-IN-NiranjanNeural` (Male).
  - **Punjabi (`pa`)**: `pa-IN-GurpreetNeural` (Female) & `pa-IN-GaganNeural` (Male).
  - **English (`en`)**: `en-IN-NeerjaNeural` (Female) & `en-IN-PrabhatNeural` (Male).
- **Automatic Unicode Script Detection**:
  - Implemented `detect_script_language(text)` in `src/voice_service.py` and `detectTextLanguage(text)` in `frontend/src/App.jsx`.
  - Automatically inspects Unicode code point ranges (e.g., Tamil `\u0B80-\u0BFF`, Devanagari `\u0900-\u097F`, Telugu `\u0C00-\u0C7F`).
  - If the UI dropdown is set to English but the response text contains Tamil Unicode, it automatically routes to the Tamil neural voice rather than failing or speaking English.
- **5-Tier Audio Fallback Cascade**:
  1. *Tier 1*: ElevenLabs Multilingual v2 (if custom API key is configured).
  2. *Tier 2*: Microsoft Edge Neural TTS (`edge-tts` — zero API cost, studio neural clarity).
  3. *Tier 3*: Google Text-to-Speech library (`gTTS`).
  4. *Tier 4*: Google Translate HTTP Audio Stream.
  5. *Tier 5*: Client-Side Browser `window.speechSynthesis` (`SpeechSynthesisUtterance`).

---

### 1.2 Full Tamil Agricultural NLP Engine
- **Ollama Agronomy LLM**: Connected to the local `agri-qwen:7b` GPU model with structured system prompting for precision Integrated Pest Management (IPM), chemical dosages (Mancozeb, Chlorothalonil, Imidacloprid, etc.), and organic remedies (வேப்பெண்ணெய் / Neem oil, சூடோமோனாஸ் / Pseudomonas fluorescens).
- **Tamil Agronomic Knowledge Fallback**: If Ollama is cold or offline, the system falls back to an extensive Tamil agricultural knowledge base covering diseases, pests, nutrient deficiencies, and weather risk advice in Tamil.
- **Multilingual Query Handling**: Responds fluently in Tamil (தமிழ்), Hindi (हिन्दी), Telugu (తెలుగు), Kannada (ಕನ್ನಡ), Malayalam (മലയാളം), Marathi (मराठी), Bengali (বাংলা), Gujarati (ગુજરાતી), Punjabi (ਪੰਜਾਬੀ), and English.

---

### 1.3 Interactive Chat & Audio Lifecycle Management in React UI
- **Audio Lifecycle Handling**: Dedicated `Audio` object handling with Blob URL generation, cleanup on unmount/re-click (`URL.revokeObjectURL`), and event listeners (`onplay`, `onended`, `onerror`).
- **Reactive UI States**:
  - 🔄 **Loading**: Shows animated spinner while neural speech is synthesized.
  - 🔊 **Voice**: Clickable speaker button on every message bubble.
  - 🔇 **Stop**: Allows pausing/stopping speech mid-playback.
- **Frontend Production Build**: Rebuilt all assets in `frontend/dist/` with Vite in 423ms.

---

### 1.4 Insect Pest Open-Set Decision Framework
- **Problem Solved**: Eliminated false-positive insect classifications on clean foliage.
- **Decision Pipeline**:
  1. **Minimum Top-1 Confidence Gate**: `PEST_CONFIDENCE_THRESHOLD = 0.72` (72%).
  2. **Probability Margin Gating ($\Delta p$)**: Enforced $\Delta p = p_{\text{top1}} - p_{\text{top2}} \ge 0.25$ to reject flat, high-entropy Softmax outputs.
  3. **Morphological Visual Evidence Verification**: Real-time OpenCV analysis (`_compute_pest_visual_evidence()` in `src/pest_detector.py`):
     - Segmented foliage tissue using HSV and CIELAB color spaces.
     - Calculated $\Delta E$ chromatic anomaly from median foliage color combined with Sobel gradient magnitudes (> 32.0).
     - Applied morphological opening and contour circularity / compactness analysis ($4\pi \cdot \text{Area} / \text{Perimeter}^2 \in [0.08, 0.95]$) to confirm physical insect bodies.
  4. **Three-Tier Output Status**:
     - *Tier 1 — Infestation Confirmed*: Conf $\ge 72\%$, $\Delta p \ge 25\%$, Evidence $\ge 0.35$.
     - *Tier 2 — Possible Pest (Verification Required)*: Score: 94/100, `pest_detected = False`.
     - *Tier 3 — Clean Foliage / No Visible Pest*: Score: 100/100, `pest_detected = False`, `is_healthy_class = True`.

---

## 🚀 2. How to Start the Project (1-Click Automated Startup)

### Option A: 1-Click Batch File (Recommended)
Simply double-click:
```
D:\AGROBOTAI\start.bat
```
`start.bat` automatically:
1. Checks for Ollama and launches the background service if not active.
2. Checks and activates the `.venv` Python virtual environment.
3. Pre-warms the `agri-qwen:7b` model into GPU VRAM.
4. Starts the FastAPI server and serves the compiled React UI.
5. Automatically opens **http://localhost:8000** in your default web browser.

### Option B: Command Line (PowerShell)
From `D:\AGROBOTAI`:
```powershell
python app.py
```
- Web Application: **http://localhost:8000**
- Interactive Swagger API: **http://localhost:8000/docs**
- Zero-cost offline AI model: **agri-qwen:7b** (Pre-warmed on GPU)

---

## 📂 3. Directory & File Reference

| File Path | Description |
| :--- | :--- |
| `app.py` | Main entry point that launches Uvicorn and opens the web browser. |
| `server.py` | FastAPI backend handling `/api/analyze`, `/api/crops`, `/api/chat`, `/api/tts`, `/api/stt`, reports, and weather risk. |
| `src/voice_service.py` | Multi-engine TTS/STT service with `edge-tts`, ElevenLabs v2, gTTS, and Unicode script detection. |
| `src/multilingual_chatbot.py` | Multilingual AI Agronomist chatbot powered by Ollama (`agri-qwen:7b`) with regional fallback KB. |
| `src/pipeline.py` | Master plant health diagnosis orchestrator. |
| `src/pest_detector.py` | Insect pest inference with OpenCV morphological visual evidence & 3-tier scoring. |
| `src/disease_detector.py` | PyTorch CNN foliar disease classifier. |
| `src/ndre_cri_analyzer.py` | Multi-spectral chlorophyll (ExG / NDRE) and carotenoid (CRI1/CRI2) proxies. |
| `src/disease_severity.py` | HSV foliar lesion area segmentation and severity grading. |
| `src/dosage_calculator.py` | TNAU/ICAR chemical and organic dosage recommendations. |
| `src/config.py` | Central configuration, model paths, thresholds, and weights. |
| `frontend/src/App.jsx` | React UI with diagnostic cards, camera capture, speaker synthesis, and telemetry. |
| `frontend/dist/` | Compiled production frontend assets. |
