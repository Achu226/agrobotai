from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

import io
import os
import threading
import traceback
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import CROPS, RGB_SPECTRAL_LIMITATION
from src.image_utils import load_rgb_array
from src.pipeline import analyze_image
from src.multilingual_chatbot import MultilingualFarmingAssistant, SUPPORTED_LANGUAGES
from src.report import build_docx_report, build_pdf_report, build_text_report
from src.dosage_calculator import DosageCalculator
from src.weather_forecast import WeatherService, calculate_disease_risk
from src.ollama_manager import ensure_ollama_ready, is_ollama_running
from src.voice_service import MultilingualVoiceService
from src import api_v1, model_registry, security, store

@asynccontextmanager
async def lifespan(_app):
    # Asynchronously initialize and pre-warm Ollama offline LLM
    threading.Thread(target=ensure_ollama_ready, daemon=True).start()
    store.migrate()
    # Load both models once (status, versions and load errors are kept in model_registry)
    threading.Thread(target=model_registry.load_all, daemon=True).start()
    # Speech recognition loads after the vision models (it picks GPU or CPU by free VRAM)
    threading.Thread(target=_load_speech_later, daemon=True).start()
    from src import config, device_status

    if config.AUTO_OFF_IDLE_HOURS > 0 and device_status.is_raspberry_pi():
        threading.Thread(target=device_status.idle_watchdog, args=(config.AUTO_OFF_IDLE_HOURS,), daemon=True).start()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AI Crop Health Diagnostic & Advisory API",
    description="Multi-spectral NDRE/CRI analysis and Deep Learning Pest & Disease Diagnosis API",
    version="3.0.0",
)

# Browsers may only call the API from the dashboard served on this laptop (or the Vite dev server).
# The Flutter app is not a browser, so CORS does not apply to it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://{h}:{p}" for h in ("localhost", "127.0.0.1") for p in (8000, 5173)],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.middleware("http")(security.lan_guard_and_log)
app.include_router(api_v1.router)


def _load_speech_later():
    import time as _time

    from src import speech

    for _ in range(60):  # wait for the vision models so they get the GPU first
        if all(n in model_registry._state for n in model_registry.SPECS):
            break
        _time.sleep(1)
    speech.load_whisper()
    speech.preload_voices()


def get_models():
    """(pest, disease) wrappers for the laptop dashboard endpoints; None when a model is unavailable."""
    return model_registry.wrapper("pest"), model_registry.wrapper("disease")


def _save_web_scan(result: dict) -> int:
    overall = result.get("overall") or {}
    disease, pest = result.get("disease") or {}, result.get("pest") or {}
    stripped = store_safe(result)
    return store.insert_scan({
        "source": "web",
        "captured_at": result.get("timestamp"),
        "crop_selected": result.get("selected_crop"),
        "crop_reported": result.get("crop"),
        "inference_status": "succeeded" if disease.get("ok") and pest.get("ok") else "partial",
        "disease_label": disease.get("display_name") if disease.get("ok") else None,
        "disease_confidence": disease.get("confidence"),
        "pest_label": pest.get("display_name") if pest.get("pest_detected") else None,
        "pest_confidence": pest.get("confidence"),
        "health_index": overall.get("overall_score"),
        "severity_pct": (result.get("severity") or {}).get("affected_percentage"),
        "model_versions": {n: model_registry.get(n).get("version") for n in model_registry.SPECS},
        "result_json": stripped,
    })


def store_safe(value):
    """Drop embedded base64 images so stored rows stay small."""
    if isinstance(value, dict):
        return {k: store_safe(v) for k, v in value.items() if not str(k).endswith("base64")}
    if isinstance(value, list):
        return [store_safe(v) for v in value]
    return value


def _gradcam_target(result: dict) -> str:
    """Explain the finding that drove the diagnosis: an active disease, else a confirmed pest."""
    disease = result.get("disease") or {}
    pest = result.get("pest") or {}
    if disease.get("ok") and not disease.get("is_healthy_class"):
        return "disease"
    if pest.get("ok") and pest.get("pest_detected"):
        return "pest"
    return "disease"


def _explain_result(result: dict, image_rgb, pest_model, disease_model) -> dict:
    target = _gradcam_target(result)
    model = disease_model if target == "disease" else pest_model
    if model is None or not hasattr(model, "model"):
        return {"ok": False, "target": target, "error": f"{target} model not loaded"}
    try:
        from src.gradcam_viz import gradcam_for_wrapper  # needs PyTorch; not on the Raspberry Pi

        cam = gradcam_for_wrapper(model, image_rgb)
        cam.pop("overlay", None)
        module = result.get(target) or {}
        cam.update({
            "target": target,
            "label": module.get("raw_class") or module.get("display_name"),
        })
        return cam
    except Exception as exc:
        traceback.print_exc()
        return {"ok": False, "target": target, "error": str(exc)}


@app.get("/api/crops")
def get_crops():
    crop_icons = {
        "Auto-Detect Plant Species": "🔍",
        "Tomato": "🍅",
        "Potato": "🥔",
        "Bell Pepper": "🫑",
        "Green Chilli": "🌶️",
        "Brinjal": "🍆",
        "Corn (Maize)": "🌽",
        "Rice (Paddy)": "🌾",
        "Wheat": "🌾",
        "Cotton": "☁️",
        "Sugarcane": "🎋",
        "Soybean": "🫘",
    }
    return {
        "crops": ["Auto-Detect Plant Species"] + list(CROPS),
        "icons": crop_icons,
        "limitation": RGB_SPECTRAL_LIMITATION,
    }


@app.post("/api/analyze")
async def analyze_crop_image(
    file: UploadFile = File(...),
    crop: str = Form("Auto-Detect Plant Species"),
    cri_variant: str = Form("CRI1"),
    api_key: str = Form(""),
):
    try:
        content = await file.read()
        file_bytes = io.BytesIO(content)
        image_rgb = load_rgb_array(file_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {exc}")

    pest_model, disease_model = get_models()
    if pest_model is None and disease_model is None:
        raise HTTPException(status_code=503, detail="No model is loaded. "
                            + " ".join(filter(None, (model_registry.get(n)["error"] for n in model_registry.SPECS))))

    try:
        result = analyze_image(
            image_rgb,
            crop=crop,
            pest_model=pest_model,
            disease_model=disease_model,
            include_advice=True,
            api_key=api_key if api_key.strip() else None,
            cri_variant=cri_variant,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    if result.get("is_valid_plant"):
        result["gradcam"] = _explain_result(result, image_rgb, pest_model, disease_model)
        try:
            result["scan_id"] = _save_web_scan(result)
        except Exception as exc:
            print(f"[Warning] Failed to save scan history: {exc}")
    return result


@app.get("/api/health")
def health_check():
    runtime = model_registry.runtime_info()
    return {
        "ok": True,
        "models": {n: model_registry.public_status(n) for n in model_registry.SPECS},
        "device": runtime["inference_device"],
        "gpu": runtime["gpu"],
        "ollama": is_ollama_running(),
    }


@app.get("/api/history")
def scan_history(limit: int = 30):
    rows = store.list_scans(limit=max(1, min(limit, 200)))
    return {"scans": [{
        "id": r["id"], "timestamp": r["captured_at"] or r["received_at"], "source": r["source"],
        "crop": r["crop_reported"] or r["crop_selected"] or "Unknown", "disease_label": r["disease_label"],
        "pest_label": r["pest_label"], "severity_pct": r["severity_pct"], "overall_score": r["health_index"],
        "review_status": r["review_status"],
    } for r in rows]}


@app.delete("/api/history/{scan_id}")
def delete_scan_endpoint(scan_id: int):
    path = store.delete_scan(scan_id)
    if path is False:
        raise HTTPException(status_code=404, detail="Scan not found")
    if path and os.path.isfile(path):
        os.remove(path)
    return {"ok": True}


@app.post("/api/heatmap")
async def get_heatmap(file: UploadFile = File(...), target: str = Form("disease")):
    """Grad-CAM overlay (JPEG) showing which leaf regions drove the model's prediction."""
    try:
        image_rgb = load_rgb_array(io.BytesIO(await file.read()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {exc}")

    pest_model, disease_model = get_models()
    model = disease_model if target == "disease" else pest_model
    if model is None:
        raise HTTPException(status_code=503, detail=f"{target} model is not loaded")
    try:
        import cv2

        from src.gradcam_viz import gradcam_for_wrapper  # needs PyTorch; not on the Raspberry Pi

        cam = gradcam_for_wrapper(model, image_rgb)
        _, encoded = cv2.imencode(".jpg", cv2.cvtColor(cam["overlay"], cv2.COLOR_RGB2BGR))
        return Response(content=encoded.tobytes(), media_type="image/jpeg")
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Grad-CAM failed: {exc}")


@app.post("/api/report/text")
def generate_text_report_endpoint(result: dict):
    report_text = build_text_report(result)
    crop = result.get("crop", "crop")
    return Response(
        content=report_text.encode("utf-8"),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={crop}_health_report.txt"},
    )


@app.post("/api/report/pdf")
def generate_pdf_report_endpoint(result: dict):
    try:
        pdf_bytes = build_pdf_report(result)
        crop = result.get("crop", "crop")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={crop}_health_report.pdf"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation error: {exc}")


@app.post("/api/report/docx")
def generate_docx_report_endpoint(result: dict):
    try:
        docx_bytes = build_docx_report(result)
        crop = result.get("crop", "crop")
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={crop}_NDRE_CRI_Report.docx"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Word DOCX generation error: {exc}")


@app.get("/api/languages")
def get_supported_languages():
    # Convert dictionary to array format with code, name, native, flag
    languages_array = [
        {"code": "ta", "name": "Tamil", "native": "தமிழ்", "flag": "🇮🇳"},
        {"code": "hi", "name": "Hindi", "native": "हिन्दी", "flag": "🇮🇳"},
        {"code": "en", "name": "English", "native": "English", "flag": "🇬🇧"},
        {"code": "te", "name": "Telugu", "native": "తెలుగు", "flag": "🇮🇳"},
        {"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ", "flag": "🇮🇳"},
        {"code": "ml", "name": "Malayalam", "native": "മലയാളം", "flag": "🇮🇳"},
        {"code": "mr", "name": "Marathi", "native": "मराठी", "flag": "🇮🇳"},
        {"code": "bn", "name": "Bengali", "native": "বাংলা", "flag": "🇮🇳"},
        {"code": "pa", "name": "Punjabi", "native": "ਪੰਜਾਬੀ", "flag": "🇮🇳"},
        {"code": "gu", "name": "Gujarati", "native": "ગુજરાતી", "flag": "🇮🇳"},
    ]
    return {
        "languages": languages_array,
        "default": "ta",
    }


@app.post("/api/chat")
async def chat_with_farming_assistant(payload: dict):
    question = payload.get("question", "").strip()
    language = payload.get("language", "ta")
    context = payload.get("context", None)
    api_key = payload.get("api_key", None)

    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    assistant = MultilingualFarmingAssistant(api_key=api_key, language=language)
    response = assistant.ask_question(question, context=context)
    return response


@app.post("/api/dosage/calculate")
def calculate_dosage_endpoint(payload: dict):
    target = payload.get("target", "Early Blight")
    field_size = float(payload.get("field_size_acres", 1.0))
    tank_liters = float(payload.get("tank_capacity_liters", 15.0))
    preferred_mode = payload.get("preferred_mode", "both")
    try:
        dosage_result = DosageCalculator.calculate_dosage(
            target_name=target,
            field_size_acres=field_size,
            tank_capacity_liters=tank_liters,
            preferred_mode=preferred_mode
        )
        return dosage_result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dosage calculation failed: {exc}")


@app.post("/api/weather/risk")
def get_weather_risk_endpoint(payload: dict):
    location = payload.get("location", "Salem, Tamil Nadu")
    lat = payload.get("lat")
    lon = payload.get("lon")
    crop = payload.get("crop", "Tomato")
    detected_disease = payload.get("detected_disease", None)

    try:
        # Weather credentials come only from the server's .env, never from the client
        service = WeatherService()
        weather_data = service.get_weather_data(location=location, lat=lat, lon=lon)
        if not weather_data.get("ok"):
            return {"ok": False, "error": weather_data.get("error", "Weather unavailable"), "weather": None, "risk_analysis": None}
        risk_analysis = calculate_disease_risk(weather_data, crop=crop, detected_disease=detected_disease)
        return {
            "ok": True,
            "weather": weather_data,
            "risk_analysis": risk_analysis
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Weather risk forecasting failed: {exc}")


@app.post("/api/tts")
async def text_to_speech_endpoint(payload: dict):
    """
    Synthesize high-fidelity speech for Tamil and Indic languages.
    Supports ElevenLabs Multilingual v2 with zero-cost Indic Neural streaming fallback.
    """
    text = payload.get("text", "").strip()
    language = payload.get("language", "ta").strip()
    voice_id = payload.get("voice_id", None)
    api_key = payload.get("api_key", None)

    if not text:
        raise HTTPException(status_code=400, detail="Text is required for TTS synthesis")

    voice_svc = MultilingualVoiceService()
    res = voice_svc.generate_speech(
        text=text,
        language=language,
        voice_id=voice_id,
        custom_elevenlabs_key=api_key
    )

    if not res.get("ok") or not res.get("audio_bytes"):
        raise HTTPException(status_code=500, detail=res.get("error", "TTS synthesis failed"))

    headers = {
        "Content-Disposition": 'inline; filename="speech.mp3"',
        "X-Voice-Engine": res.get("engine", "neural_stream"),
        "X-Voice-Language": res.get("language", language)
    }
    return Response(content=res["audio_bytes"], media_type="audio/mpeg", headers=headers)


@app.post("/api/stt")
async def speech_to_text_endpoint(
    file: UploadFile = File(...),
    language: str = Form("ta"),
    api_key: str = Form("")
):
    """
    Transcribe spoken voice audio into text via Whisper API.
    """
    try:
        content = await file.read()
        voice_svc = MultilingualVoiceService()
        res = voice_svc.transcribe_audio(
            audio_file_bytes=content,
            language=language,
            api_key=api_key
        )
        if not res.get("ok"):
            raise HTTPException(status_code=400, detail=res.get("error", "Transcription failed"))
        return res
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Speech-to-text processing failed: {exc}")


@app.post("/api/voice")
async def get_voice(text: str = Form(...), lang: str = Form("en")):
    """Form-encoded TTS alias of /api/tts (kept for older clients)."""
    res = MultilingualVoiceService().generate_speech(text=text.strip(), language=lang.strip())
    if not res.get("ok") or not res.get("audio_bytes"):
        raise HTTPException(status_code=500, detail=res.get("error", "TTS synthesis failed"))
    return Response(content=res["audio_bytes"], media_type="audio/mpeg")


# Serve the built React frontend. This mount catches every path, so it must be
# registered after all /api routes or it will shadow them.
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    @app.middleware("http")
    async def add_cache_control_header(request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

if __name__ == "__main__":
    # Development only: hot reload re-loads the models on every change. start.bat runs without reload.
    uvicorn.run("server:app", host="127.0.0.1", port=int(os.getenv("AGROBOT_PORT", "8000")), reload=True)
