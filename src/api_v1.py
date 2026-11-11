"""
Authenticated mobile API (/api/v1) plus /health and /models/status.

These are the only routes reachable from other devices on the LAN (see src/security.py).
"""
from __future__ import annotations

import asyncio
import hmac
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from src import auth, config, farm_advisor, inference_service, languages, model_registry, speech, store
from src.config import CROPS, SCAN_IMAGES_DIR
from src.security import read_upload

router = APIRouter()
# One GPU: run inferences one at a time so concurrent phones do not exhaust VRAM
_inference_lock = asyncio.Lock()
# The laptop LLM answers one advice/chat request at a time; it does not block image inference
_advisor_lock = asyncio.Lock()


# ---------------------------------------------------------------- schemas

class LoginIn(BaseModel):
    username: str = Field(..., max_length=40)
    password: str = Field(..., max_length=200)


class RegisterIn(LoginIn):
    full_name: str = Field("", max_length=80)
    farm_name: str = Field("", max_length=80)
    location: str = Field("", max_length=80)


class ReviewIn(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    comment: str = Field("", max_length=1000)


# Physically possible ranges; a reading outside them means a wiring/sensor fault, so it is refused
SENSOR_RANGES = {
    "soil_moisture_pct": (0, 100), "humidity_pct": (0, 100), "air_temp_c": (-40, 85), "soil_temp_c": (-40, 85),
    "soil_ph": (0, 14), "soil_ec": (0, 20000), "n": (0, 2000), "p": (0, 2000), "k": (0, 2000),
    "soil_moisture_raw": (0, 70000),
}


class SensorReadingIn(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    measured_at: str | None = None
    readings: dict[str, float | int | None] = Field(..., description="e.g. soil_moisture_pct, soil_temp_c, air_temp_c, humidity_pct, soil_ph, soil_ec, n, p, k")

    @field_validator("readings")
    @classmethod
    def _physically_possible(cls, readings):
        if len(readings) > 32:
            raise ValueError("too many readings in one message")
        for key, value in readings.items():
            lo, hi = SENSOR_RANGES.get(key, (None, None))
            if value is not None and lo is not None and not lo <= value <= hi:
                raise ValueError(f"{key}={value} is outside the possible range {lo}..{hi} (sensor or wiring fault?)")
        return readings


class DiaryIn(BaseModel):
    plot: str = Field(..., min_length=1, max_length=60)
    kind: str = Field(..., pattern="^(spray|fertilizer|irrigation|sowing|weeding|harvest|labour|sale|note)$")
    product: str = Field("", max_length=80)
    quantity: str = Field("", max_length=40)
    cost: float | None = Field(None, ge=0, le=10_000_000)  # for kind "sale": money received
    note: str = Field("", max_length=500)
    done_on: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    remind_on: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    repeat_days: int | None = Field(None, ge=1, le=365)  # repeat the reminder every N days (needs remind_on)


class AdviceIn(BaseModel):
    language: str = Field("ta", max_length=8)
    refresh: bool = False


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=4000)


class SpeakIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=3000)
    language: str = Field("ta", max_length=8)
    engine: str = Field("local", pattern="^(local|online|auto)$")


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    language: str = Field("ta", max_length=8)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    scan_id: int | None = None
    # With no scan_id, the advisor gets the farmer's most recent completed scan as context
    use_latest_scan: bool = True


def _live_sensors() -> list[dict]:
    return store.latest_sensor_readings()


def _error(exc: inference_service.InferenceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"detail": exc.message, "error": exc.to_dict()})


# ---------------------------------------------------------------- health & model status

@router.get("/health")
def health():
    """Unauthenticated liveness + readiness. No file paths or secrets."""
    return {
        "ok": True,
        "service": "AGROBOTAI inference server",
        "time": store.now_iso(),
        "runtime": model_registry.runtime_info(),
        "models": {name: model_registry.public_status(name) for name in model_registry.SPECS},
        "auth_required": True,
        "farmer_signup_enabled": config.ALLOW_FARMER_SIGNUP,
    }


@router.get("/models/status")
def models_status(user: dict = Depends(auth.current_user)):
    return {
        "runtime": model_registry.runtime_info(),
        "models": {name: model_registry.public_status(name, detailed=True) for name in model_registry.SPECS},
        "disease_uncertainty_threshold": config.DISEASE_UNCERTAIN_THRESHOLD,
        "supported_disease_crops": list(config.SUPPORTED_DISEASE_CROPS),
    }


# ---------------------------------------------------------------- auth

@router.post("/api/v1/auth/login")
def login(body: LoginIn, request: Request):
    user, token, expires = auth.login(body.username, body.password, request)
    return {"token": token, "expires_at": expires, "user": user}


@router.post("/api/v1/auth/register", status_code=201)
def register(body: RegisterIn, request: Request):
    if not config.ALLOW_FARMER_SIGNUP:
        raise HTTPException(status_code=403, detail="Self-registration is disabled. Ask the administrator for an account.")
    auth.validate_new_credentials(body.username, body.password)
    if store.get_user_auth(body.username):
        raise HTTPException(status_code=409, detail="That username is already taken.")
    # Self-registration can only ever create farmer accounts; admins are created on the laptop (manage_users.py)
    user = store.create_user(body.username, auth.hash_password(body.password), "farmer",
                             body.full_name, body.farm_name, body.location)
    token, expires = auth.issue_session(user["id"], request)
    return {"token": token, "expires_at": expires, "user": user}


@router.get("/api/v1/auth/me")
def me(user: dict = Depends(auth.current_user)):
    return {"user": user}


@router.post("/api/v1/auth/logout")
def logout(request: Request, user: dict = Depends(auth.current_user)):
    auth.revoke(request)
    return {"ok": True}


# ---------------------------------------------------------------- prediction

async def _image_from_upload(file: UploadFile):
    data = await read_upload(file)
    return inference_service.decode_image(data)


@router.post("/api/v1/predict/disease")
async def predict_disease(file: UploadFile = File(...), crop: str = Form(""), user: dict = Depends(auth.current_user)):
    try:
        image = await _image_from_upload(file)
        inference_service.validate_quality(image)
        async with _inference_lock:
            return await asyncio.to_thread(inference_service.predict_disease, image, crop or None)
    except inference_service.InferenceError as exc:
        return _error(exc)


@router.post("/api/v1/predict/pest")
async def predict_pest(file: UploadFile = File(...), user: dict = Depends(auth.current_user)):
    try:
        image = await _image_from_upload(file)
        inference_service.validate_quality(image)
        async with _inference_lock:
            return await asyncio.to_thread(inference_service.predict_pest, image)
    except inference_service.InferenceError as exc:
        return _error(exc)


def _record_from_result(result: dict) -> dict:
    disease, pest = result["disease"], result["pest"]
    ok_states = ("unavailable", "failed")
    return {
        "inference_status": "partial" if disease["state"] in ok_states or pest["state"] in ok_states else "succeeded",
        "summary_state": result["summary"]["state"],
        "crop_reported": result["crop"]["reported"],
        "disease_label": disease.get("display_name") if disease.get("label") else None,
        "disease_state": disease["state"],
        "disease_confidence": disease.get("calibrated_confidence"),
        "pest_label": pest.get("display_name") if pest["state"] == "pest_detected" else None,
        "pest_state": pest["state"],
        "pest_confidence": pest.get("calibrated_confidence"),
        "health_index": (result.get("health_index") or {}).get("value"),
        "severity_pct": result["severity"].get("affected_pct"),
        "model_versions": {"disease": disease["model"].get("version"), "pest": pest["model"].get("version")},
    }


@router.post("/api/v1/analyze")
async def analyze(
    file: UploadFile = File(...),
    crop: str = Form(""),
    captured_at: str = Form(""),
    client_request_id: str = Form("", max_length=64),
    include_advice: bool = Form(True),
    location: str = Form("", max_length=80),
    language: str = Form("ta", max_length=8),
    plot: str = Form("", max_length=60),
    user: dict = Depends(auth.current_user),
):
    """Runs every available model on one photo and saves a scan only after inference succeeded."""
    request_id = client_request_id.strip() or None
    if request_id:
        existing = store.find_scan_by_request(user["id"], request_id)
        if existing:  # retry of a request that already completed: return it, never duplicate
            return {"scan": existing, "duplicate": True}
    crop = crop.strip() or None
    if crop and crop not in CROPS:
        crop = None
    try:
        image = await _image_from_upload(file)
        async with _inference_lock:
            result = await asyncio.to_thread(inference_service.analyze, image, crop, include_advice, location or None,
                                             languages.normalize(language), _live_sensors())
    except inference_service.InferenceError as exc:
        if exc.status >= 500:
            # Record genuine failures for diagnostics; they never count as diagnoses
            store.insert_scan({"user_id": user["id"], "source": "mobile", "captured_at": captured_at or None,
                               "crop_selected": crop, "inference_status": "failed", "error": exc.message})
        return _error(exc)

    image_path = await asyncio.to_thread(inference_service.save_scan_image, image)
    record = _record_from_result(result) | {
        "user_id": user["id"], "source": "mobile", "client_request_id": request_id,
        "captured_at": captured_at or None, "crop_selected": crop, "image_path": image_path, "result_json": result,
        "plot": plot.strip() or None,
    }
    try:
        scan_id = store.insert_scan(record)
    except Exception:
        # Lost a race with an identical retry: return the stored one
        if request_id and (existing := store.find_scan_by_request(user["id"], request_id)):
            os.remove(image_path)
            return {"scan": existing, "duplicate": True}
        raise
    return {"scan": store.get_scan(scan_id), "duplicate": False}


# ---------------------------------------------------------------- scans, reviews, reports

def _visible_scan(scan_id: int, user: dict) -> dict:
    scan = store.get_scan(scan_id)
    if not scan or (user["role"] != "admin" and scan["user_id"] != user["id"]):
        raise HTTPException(status_code=404, detail="Scan not found.")
    return scan


@router.get("/api/v1/scans")
def list_scans(review_status: str | None = Query(None, pattern="^(pending|approved|rejected)$"),
               include_failed: bool = False, limit: int = Query(50, ge=1, le=500),
               user: dict = Depends(auth.current_user)):
    owner = None if user["role"] == "admin" else user["id"]
    return {"scans": store.list_scans(user_id=owner, review_status=review_status,
                                      include_failed=include_failed and user["role"] == "admin", limit=limit)}


@router.get("/api/v1/scans/{scan_id}")
def get_scan(scan_id: int, user: dict = Depends(auth.current_user)):
    return {"scan": _visible_scan(scan_id, user)}


@router.get("/api/v1/scans/{scan_id}/image")
def scan_image(scan_id: int, user: dict = Depends(auth.current_user)):
    _visible_scan(scan_id, user)
    path = store.get_scan_image_path(scan_id)
    # Only serve files that live inside the scan image folder
    if not path or not os.path.isfile(path) or os.path.commonpath([os.path.abspath(path), str(SCAN_IMAGES_DIR.resolve())]) != str(SCAN_IMAGES_DIR.resolve()):
        raise HTTPException(status_code=404, detail="No image stored for this scan.")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/api/v1/scans/{scan_id}/report.pdf")
def scan_report(scan_id: int, user: dict = Depends(auth.current_user)):
    from src.report import build_scan_pdf

    scan = _visible_scan(scan_id, user)
    if scan["inference_status"] == "failed":
        raise HTTPException(status_code=409, detail="Reports are only available for completed scans.")
    pdf = build_scan_pdf(scan, store.get_scan_image_path(scan_id))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="agrobotai_scan_{scan_id}.pdf"'})


@router.post("/api/v1/scans/{scan_id}/advice")
async def scan_advice(scan_id: int, body: AdviceIn, user: dict = Depends(auth.current_user)):
    """Advice card for one scan in the requested language; generated once per language, then cached."""
    scan = _visible_scan(scan_id, user)
    result = scan.get("result")
    if scan["inference_status"] == "failed" or not result:
        raise HTTPException(status_code=409, detail="Advice is only available for completed scans.")
    code = languages.normalize(body.language)
    if result.get("summary", {}).get("state") not in inference_service.ADVISABLE_STATES:
        return {"advice": result.get("advice") or {"state": "not_applicable"}, "cached": True}
    cached = (result.get("advice_by_language") or {}).get(code)
    if cached and cached.get("source") == "local_llm" and not body.refresh:
        return {"advice": cached, "cached": True}
    async with _advisor_lock:
        card = await asyncio.to_thread(farm_advisor.advise_scan, result, code, _live_sensors())
    latest = store.get_scan(scan_id)["result"]  # re-read: another language may have been saved meanwhile
    latest.setdefault("advice_by_language", {})[code] = card
    latest["advice"] = card
    store.update_scan_result(scan_id, latest)
    return {"advice": card, "cached": False}


# ---------------------------------------------------------------- languages & chat

@router.get("/api/v1/languages")
def list_languages():
    return {"default": languages.DEFAULT_LANGUAGE, "languages": languages.public_list()}


def _chat_context(body: ChatIn, user: dict) -> tuple[dict | None, dict | None]:
    """(scan result, short description) the advisor should talk about."""
    scan = None
    if body.scan_id is not None:
        scan = _visible_scan(body.scan_id, user)
    elif body.use_latest_scan:
        latest = [r for r in store.list_scans(user_id=user["id"], limit=5) if r["inference_status"] != "failed"]
        scan = store.get_scan(latest[0]["id"]) if latest else None
    if not scan or not scan.get("result"):
        return None, None
    label = scan.get("disease_label") if scan.get("disease_state") == "disease_detected" else None
    readable = {"uncertain": "uncertain result", "no_supported_condition_detected": "no disease found",
                "unsupported_crop": "crop not supported", "partial": "partial result"}
    state = (scan["result"].get("summary") or {}).get("state", "")
    label = label or scan.get("pest_label") or readable.get(state, state.replace("_", " "))
    crop = scan.get("crop_reported") or scan.get("crop_selected") or ""
    return scan["result"], {"scan_id": scan["id"], "crop": crop, "label": label}


_ADVISOR_OFFLINE = {
    "detail": "The AI advisor on the laptop is not running. Start Ollama (start.bat does this) and try again.",
    "code": "advisor_unavailable",
}


@router.post("/api/v1/chat")
async def chat(body: ChatIn, user: dict = Depends(auth.current_user)):
    scan_result, context = _chat_context(body, user)
    try:
        async with _advisor_lock:
            res = await asyncio.to_thread(farm_advisor.chat, body.message, body.language,
                                          [t.model_dump() for t in body.history], scan_result, _live_sensors())
        return res | {"context": context}
    except farm_advisor.AdvisorUnavailable as exc:
        return JSONResponse(status_code=503, content={
            "detail": _ADVISOR_OFFLINE["detail"], "error": {"code": _ADVISOR_OFFLINE["code"], "message": str(exc)}})


@router.post("/api/v1/chat/stream")
async def chat_stream(body: ChatIn, user: dict = Depends(auth.current_user)):
    """Same as /chat, but streams newline-delimited JSON events so words appear as they are written:
    {"type":"start",...} then {"type":"delta","text":...}... then {"type":"done",...}; on failure
    {"type":"error","code":...,"detail":...}."""
    import json as _json

    scan_result, context = _chat_context(body, user)
    history = [t.model_dump() for t in body.history]
    sensors = _live_sensors()

    async def events():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def produce():
            try:
                for ev in farm_advisor.chat_stream(body.message, body.language, history, scan_result, sensors):
                    if ev["type"] == "start":
                        ev = ev | {"context": context}
                    loop.call_soon_threadsafe(queue.put_nowait, ev)
            except farm_advisor.AdvisorUnavailable as exc:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "code": _ADVISOR_OFFLINE["code"],
                                                             "detail": _ADVISOR_OFFLINE["detail"], "message": str(exc)})
            except Exception as exc:  # noqa: BLE001 - reported to the phone, never swallowed
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "code": "advisor_failed", "detail": str(exc)})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        async with _advisor_lock:
            task = loop.run_in_executor(None, produce)
            while (ev := await queue.get()) is not None:
                yield (_json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")
            await task

    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- spray calculator

# Exact model labels -> rows of the reference table in src/dosage_calculator.py. Anything else
# (e.g. mosaic virus, septoria, target spot) has no verified table, so no dose is shown.
DOSAGE_TABLE_FOR_LABEL = {
    "Tomato_Early_blight": "Early Blight", "Potato___Early_blight": "Early Blight",
    "Tomato_Late_blight": "Late Blight", "Potato___Late_blight": "Late Blight",
    "Tomato_Bacterial_spot": "Bacterial Spot", "Pepper__bell___Bacterial_spot": "Bacterial Spot",
    "Tomato_Leaf_Mold": "Leaf Mold",
    "Tomato__Tomato_YellowLeaf__Curl_Virus": "Yellow Leaf Curl Virus",
    "Tomato_Spider_mites_Two_spotted_spider_mite": "mites",
    "aphids": "aphids", "armyworm": "armyworm", "bollworm": "bollworm", "mites": "mites",
    "beetle": "beetle", "stem_borer": "stem_borer",
}


@router.get("/api/v1/dosage")
def dosage(scan_id: int, acres: float = Query(1.0, gt=0.01, le=100), tank_liters: float = Query(15.0, ge=1, le=2000),
           user: dict = Depends(auth.current_user)):
    """Spray quantities for the confirmed finding of one scan, from the reference table only."""
    from src.dosage_calculator import DosageCalculator

    result = _visible_scan(scan_id, user).get("result") or {}
    disease, pest = result.get("disease") or {}, result.get("pest") or {}
    label = (disease.get("label") if disease.get("state") == "disease_detected"
             else pest.get("label") if pest.get("state") == "pest_detected" else None)
    if not label:
        raise HTTPException(status_code=409, detail="No confirmed disease or pest in this scan, so no spray is recommended.")
    table = DOSAGE_TABLE_FOR_LABEL.get(label)
    name = disease.get("display_name") if label == disease.get("label") else pest.get("display_name")
    if not table:
        raise HTTPException(status_code=404, detail=f"There is no verified spray table for {name}. "
                                                   "Ask your local agriculture officer (KVK) before spraying.")
    plan = DosageCalculator.calculate_dosage(target_name=table, field_size_acres=acres, tank_capacity_liters=tank_liters)
    return plan | {"target": name, "table": table,
                   "note": "Reference doses (TNAU/ICAR style table). Always follow the product label and your local "
                           "agriculture officer; wear gloves and a mask while spraying."}


# ---------------------------------------------------------------- voice (local Whisper + MMS-TTS)

_speech_lock = asyncio.Lock()


def _speech_error(exc: speech.SpeechError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"detail": exc.message, "error": {"code": exc.code}})


@router.get("/api/v1/voice/status")
def voice_status(user: dict = Depends(auth.current_user)):
    return speech.status()


@router.post("/api/v1/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...), language: str = Form("auto"),
                           user: dict = Depends(auth.current_user)):
    """Farmer's spoken question (16-bit PCM WAV) -> text, using Whisper on this laptop."""
    data = await file.read(6 * 1024 * 1024 + 1)
    if not data:
        return _speech_error(speech.SpeechError(400, "invalid_audio", "The recording is empty."))
    if len(data) > 6 * 1024 * 1024:
        return _speech_error(speech.SpeechError(413, "audio_too_long", "Recording is too large."))
    try:
        audio = speech.decode_wav(data)
        hint = None if language == "auto" else languages.normalize(language)
        async with _speech_lock:
            return await asyncio.to_thread(speech.transcribe, audio, hint)
    except speech.SpeechError as exc:
        return _speech_error(exc)


@router.post("/api/v1/voice/speak")
async def voice_speak(body: SpeakIn, user: dict = Depends(auth.current_user)):
    """Reads text aloud in the farmer's language. Local MMS voices by default; "online" uses Edge neural voices."""
    try:
        async with _speech_lock:
            audio, mime, engine = await asyncio.to_thread(speech.synthesize, body.text,
                                                          languages.normalize(body.language), body.engine)
    except speech.SpeechError as exc:
        return _speech_error(exc)
    return Response(audio, media_type=mime, headers={"X-Voice-Engine": engine, "Cache-Control": "no-store"})


@router.post("/api/v1/scans/{scan_id}/review")
def review(scan_id: int, body: ReviewIn, admin: dict = Depends(auth.require_admin)):
    updated = store.review_scan(scan_id, admin["id"], body.decision, body.comment)
    if not updated:
        raise HTTPException(status_code=404, detail="Scan not found or it is a failed attempt.")
    return {"scan": updated}


@router.delete("/api/v1/scans/{scan_id}")
def delete_scan(scan_id: int, user: dict = Depends(auth.current_user)):
    _visible_scan(scan_id, user)
    path = store.delete_scan(scan_id)
    if path and os.path.isfile(path):
        os.remove(path)
    return {"ok": True}


@router.get("/api/v1/admin/users")
def admin_users(admin: dict = Depends(auth.require_admin)):
    return {"users": store.list_users()}


def _sessions_report() -> dict:
    now = datetime.now(timezone.utc)
    sessions = [s | {"online": (now - datetime.fromisoformat(s["last_seen"])).total_seconds() <= 300}
                for s in store.list_sessions()]
    return {"sessions": sessions, "online_users": len({s["user_id"] for s in sessions if s["online"]})}


@router.get("/api/v1/admin/sessions")
def admin_sessions(admin: dict = Depends(auth.require_admin)):
    """Who is logged in: every unexpired login; `online` = active in the last 5 minutes."""
    return _sessions_report()


@router.get("/api/v1/admin/outbreaks")
def admin_outbreaks(days: int = Query(30, ge=1, le=365), admin: dict = Depends(auth.require_admin)):
    """Which diseases and pests were confirmed recently, and where (from real scans only)."""
    return store.outbreaks(days)


@router.get("/api/v1/device/report")
def device_report(x_status_token: str = Header("", alias="X-Status-Token")):
    """Pi health + logins + scan counts for the laptop website; needs the shared STATUS_TOKEN."""
    from src import device_status

    if not config.STATUS_TOKEN or not hmac.compare_digest(x_status_token, config.STATUS_TOKEN):
        raise HTTPException(status_code=401, detail="Status key required.")
    return {"device": device_status.status(), "stats": store.scan_stats(), "outbreaks": store.outbreaks(), **_sessions_report()}


@router.get("/api/v1/admin/pi")
def admin_pi(admin: dict = Depends(auth.require_admin)):
    """The Raspberry Pi's report, fetched by the laptop for its admin page. Real data or a clear error."""
    import httpx

    if not (config.PI_URL and config.PI_STATUS_TOKEN):
        return {"configured": False}
    try:
        res = httpx.get(f"{config.PI_URL}/api/v1/device/report", headers={"X-Status-Token": config.PI_STATUS_TOKEN}, timeout=8)
    except httpx.HTTPError as exc:
        return {"configured": True, "ok": False, "url": config.PI_URL, "error": f"Raspberry Pi not reachable ({exc.__class__.__name__})"}
    if res.status_code != 200:
        return {"configured": True, "ok": False, "url": config.PI_URL, "error": f"Raspberry Pi answered HTTP {res.status_code}"}
    return {"configured": True, "ok": True, "url": config.PI_URL, **res.json()}


@router.get("/api/v1/admin/stats")
def admin_stats(admin: dict = Depends(auth.require_admin)):
    return store.scan_stats()


# ---------------------------------------------------------------- weather & sensors

@router.get("/api/v1/weather")
def weather(location: str = Query(..., min_length=2, max_length=80), crop: str = "Tomato",
            detected_disease: str | None = None, user: dict = Depends(auth.current_user)):
    from src.weather_forecast import WeatherService, calculate_disease_risk

    data = WeatherService().get_weather_data(location=location)
    if not data.get("ok"):
        return {"ok": False, "code": data.get("code", "weather_unavailable"), "error": data.get("error", "Weather unavailable")}
    return {"ok": True, "provider": data.get("provider"), "fetched_at": data.get("fetched_at"), "weather": data,
            "risk_analysis": calculate_disease_risk(data, crop=crop, detected_disease=detected_disease)}


@router.get("/api/v1/device/status")
def device_status(user: dict = Depends(auth.current_user)):
    """Real health of the machine running this server (Raspberry Pi temperature, power, storage)."""
    from src import device_status as ds

    return ds.status()


@router.post("/api/v1/device/shutdown")
def device_shutdown(admin: dict = Depends(auth.require_admin)):
    """Admin-only safe power-off of the Raspberry Pi (never the laptop)."""
    from src import device_status as ds

    if not ds.is_raspberry_pi():
        raise HTTPException(status_code=409, detail="Only a Raspberry Pi server can be turned off from the app.")
    ds.log.warning("Shutdown requested by admin %s", admin["username"])
    ds.shutdown_soon()
    return {"ok": True, "message": "The Raspberry Pi is turning off. Wait 20 seconds before unplugging it; plug it in again to start it."}


@router.post("/api/v1/sensors/readings", status_code=201)
def sensor_ingest(body: SensorReadingIn, x_sensor_token: str = Header("")):
    if not config.SENSOR_INGEST_TOKEN:
        raise HTTPException(status_code=503, detail="Sensor ingest is not configured (set SENSOR_INGEST_TOKEN in .env).")
    if not hmac.compare_digest(x_sensor_token.encode(), config.SENSOR_INGEST_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Invalid sensor token.")
    return {"id": store.insert_sensor_reading(body.device_id, body.readings, body.measured_at)}


@router.get("/api/v1/sensors/status")
def sensor_status(user: dict = Depends(auth.current_user)):
    now = datetime.now(timezone.utc)
    devices = []
    for d in store.latest_sensor_readings():
        age = (now - datetime.fromisoformat(d["received_at"])).total_seconds()
        devices.append(d | {"connected": age <= config.SENSOR_STALE_SECONDS, "seconds_since_last_reading": int(age)})
    return {
        "configured": bool(config.SENSOR_INGEST_TOKEN),
        "stale_after_seconds": config.SENSOR_STALE_SECONDS,
        "devices": devices,
        "message": None if devices else "No sensor gateway has sent data yet. Values are shown only after a real reading arrives.",
    }


@router.get("/api/v1/plots")
def list_plots(user: dict = Depends(auth.current_user)):
    """Recovery tracking: the caller's own scans grouped by plot / plant name."""
    return {"plots": store.plots(user["id"])}


def field_alerts(devices: list[dict], now: datetime | None = None) -> list[dict]:
    """Alert codes from real sensor readings. Stale devices only ever produce `sensor_offline`."""
    now = now or datetime.now(timezone.utc)
    alerts = []
    for d in devices:
        dev = d["device_id"]
        age = (now - datetime.fromisoformat(d["received_at"])).total_seconds()
        if age > config.SENSOR_STALE_SECONDS:
            # A device silent for over a day is treated as removed, so it does not alert forever
            if age <= 86400:
                alerts.append({"code": "sensor_offline", "device": dev, "value": int(age // 60), "threshold": None})
            continue
        r = d["readings"]
        moisture, temp, humidity = r.get("soil_moisture_pct"), r.get("air_temp_c"), r.get("humidity_pct")
        if moisture is not None and moisture < config.ALERT_SOIL_DRY_PCT:
            alerts.append({"code": "soil_dry", "device": dev, "value": moisture, "threshold": config.ALERT_SOIL_DRY_PCT})
        if moisture is not None and moisture > config.ALERT_SOIL_WET_PCT:
            alerts.append({"code": "waterlogged", "device": dev, "value": moisture, "threshold": config.ALERT_SOIL_WET_PCT})
        if temp is not None and temp > config.ALERT_HEAT_C:
            alerts.append({"code": "heat", "device": dev, "value": temp, "threshold": config.ALERT_HEAT_C})
        if (humidity is not None and temp is not None and humidity >= config.ALERT_BLIGHT_HUMIDITY_PCT
                and config.ALERT_BLIGHT_TEMP_MIN_C <= temp <= config.ALERT_BLIGHT_TEMP_MAX_C):
            alerts.append({"code": "blight_weather", "device": dev, "value": humidity,
                           "threshold": config.ALERT_BLIGHT_HUMIDITY_PCT})
    return alerts


@router.get("/api/v1/diary")
def diary(plot: str | None = Query(None, max_length=60), user: dict = Depends(auth.current_user)):
    return {"entries": store.list_diary(user["id"], plot)}


@router.post("/api/v1/diary", status_code=201)
def diary_add(body: DiaryIn, user: dict = Depends(auth.current_user)):
    for day in (body.done_on, body.remind_on):
        if day:
            try:
                datetime.strptime(day, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Not a real date: {day}") from None
    if body.repeat_days and not body.remind_on:
        raise HTTPException(status_code=422, detail="A repeating reminder needs its first reminder date.")
    entry = body.model_dump() | {"plot": body.plot.strip(), "product": body.product.strip() or None,
                                 "quantity": body.quantity.strip() or None, "note": body.note.strip() or None}
    return {"entry": store.add_diary_entry(user["id"], entry)}


@router.delete("/api/v1/diary/{entry_id}")
def diary_delete(entry_id: int, user: dict = Depends(auth.current_user)):
    if not store.delete_diary_entry(user["id"], entry_id):
        raise HTTPException(status_code=404, detail="Diary entry not found.")
    return {"ok": True}


@router.get("/api/v1/library")
def library_list(language: str = Query("ta", max_length=8), user: dict = Depends(auth.current_user)):
    """Disease & pest library; entries not yet translated into `language` come back in English."""
    from src import library

    return {"entries": library.localized(language, translate_missing=False)}


@router.get("/api/v1/library/{key}")
async def library_entry(key: str, language: str = Query("ta", max_length=8), user: dict = Depends(auth.current_user)):
    """One entry, translated by the laptop AI on first use (then cached)."""
    from src import library

    if key not in {e["key"] for e in library.entries()}:
        raise HTTPException(status_code=404, detail="No library entry with that name.")
    async with _advisor_lock:
        entry = await asyncio.to_thread(library.localized, language, True, {key})
    return {"entry": entry[0]}


@router.get("/api/v1/market-prices")
def market_prices(commodity: str = Query(..., min_length=2, max_length=60), state: str = Query("Tamil Nadu", max_length=40),
                  user: dict = Depends(auth.current_user)):
    """Today's published mandi prices (Agmarknet via data.gov.in); needs DATA_GOV_API_KEY."""
    from src import market_prices as mp

    return mp.prices(commodity.strip(), state.strip())


def _csv_cell(value) -> str:
    """Text cells starting with = + - @ would run as formulas in Excel: prefix them with a quote."""
    text = "" if value is None else str(value)
    return "'" + text if isinstance(value, str) and text[:1] in ("=", "+", "-", "@") else text


@router.get("/api/v1/export.csv")
def export_csv(what: str = Query("diary", pattern="^(diary|scans)$"), user: dict = Depends(auth.current_user)):
    """The caller's own farm records as a CSV file that opens in Excel (for the bank, officer or own books)."""
    if what == "diary":
        header = ["Date", "Plot", "Activity", "Product", "Quantity", "Spent (Rs)", "Earned (Rs)", "Note"]
        rows = [[e["done_on"], e["plot"], e["kind"], e["product"], e["quantity"],
                 e["cost"] if e["kind"] != "sale" else None, e["cost"] if e["kind"] == "sale" else None, e["note"]]
                for e in reversed(store.list_diary(user["id"]))]
    else:
        header = ["Date", "Plot", "Crop", "Result", "Disease", "Pest", "Affected area %", "Health (0-100)"]
        rows = [[(s["captured_at"] or s["received_at"] or "")[:10], s["plot"], s["crop_reported"] or s["crop_selected"],
                 s["summary_state"], s["disease_label"] if s["disease_state"] == "disease_detected" else None,
                 s["pest_label"] if s["pest_state"] == "pest_detected" else None, s["severity_pct"], s["health_index"]]
                for s in reversed(store.list_scans(user_id=user["id"], limit=5000))]
    return _csv_response(f"agrobotai_{what}.csv", header, rows)


def _csv_response(filename: str, header: list[str], rows: list[list]) -> Response:
    import csv
    import io

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows([_csv_cell(c) for c in row] for row in rows)
    # BOM so Excel reads Tamil plot names and notes as UTF-8
    return Response("\ufeff" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/api/v1/admin/outbreaks.csv")
def admin_outbreaks_csv(days: int = Query(30, ge=1, le=365), admin: dict = Depends(auth.require_admin)):
    """Confirmed diseases and pests per village as an Excel file (for reports to the agriculture office)."""
    rows = [[p["location"], p["label"], p["kind"], p["count"], p["last_seen"][:10]] for p in store.outbreaks(days)["by_location"]]
    return _csv_response(f"agrobotai_outbreaks_{days}_days.csv", ["Village / place", "Condition", "Type", "Confirmed scans", "Last seen"], rows)


@router.get("/api/v1/today")
def today(user: dict = Depends(auth.current_user)):
    """One-glance summary for the home screen, built only from the caller's real data: spraying now, reminders due
    today, alerts, and the last 7 days."""
    day = datetime.now().date()
    week_start = (day - timedelta(days=6)).isoformat()
    diary = store.list_diary(user["id"])
    spray = spray_plan(location="", user=user)
    week = [e for e in diary if e["done_on"] >= week_start and e["cost"] is not None]
    return {
        "date": day.isoformat(),
        "spray": {k: spray.get(k) for k in ("ok", "code", "location", "ok_now", "now_problems", "best_window")},
        "reminders": [e for e in diary if e["remind_on"] == day.isoformat()],
        "nearby": outbreaks_nearby(days=14, user=user).get("alerts", []),
        "alerts": alerts(user=user)["alerts"],
        "week": {
            "scans": sum((s["received_at"] or "")[:10] >= week_start for s in store.list_scans(user_id=user["id"], limit=500)),
            "spent": sum(e["cost"] for e in week if e["kind"] != "sale"),
            "earned": sum(e["cost"] for e in week if e["kind"] == "sale"),
        },
    }


@router.get("/api/v1/outbreaks/nearby")
def outbreaks_nearby(days: int = Query(14, ge=1, le=60), user: dict = Depends(auth.current_user)):
    """Confirmed diseases and pests other farmers found in the caller's village/town (counts only, never names)."""
    place = (user.get("location") or "").strip()
    if len(place) < 2:
        return {"ok": False, "code": "no_location", "error": "Set your village or town in your profile to get local alerts."}
    names = config.DISEASE_DISPLAY_NAMES | config.PEST_DISPLAY_NAMES
    rows = [{"label": p["label"], "display_name": names.get(p["label"], p["label"]), "kind": p["kind"], "count": p["count"],
             "last_seen": p["last_seen"]}
            for p in store.outbreaks(days, exclude_user_id=user["id"])["by_location"] if p["location"].casefold() == place.casefold()]
    return {"ok": True, "location": place, "days": days, "alerts": sorted(rows, key=lambda r: -r["count"])}


@router.get("/api/v1/fertilizer")
def fertilizer(n: float = Query(..., ge=0, le=1000), p2o5: float = Query(..., ge=0, le=1000), k2o: float = Query(..., ge=0, le=1000),
               acres: float = Query(1.0, gt=0, le=1000), dose_per: str = Query("acre", pattern="^(acre|hectare)$"),
               user: dict = Depends(auth.current_user)):
    """Bags of Urea / DAP / MOP for an N-P-K recommendation (Soil Health Card)."""
    from src import fertilizer_calculator

    return fertilizer_calculator.plan(n, p2o5, k2o, acres, dose_per)


@router.get("/api/v1/spray-plan")
def spray_plan(location: str = Query("", max_length=80), user: dict = Depends(auth.current_user)):
    """Is it safe to spray in the next 24 h, from the real hourly forecast (rain, wind, heat)."""
    from src import spray_planner
    from src.weather_forecast import WeatherService

    place = location.strip() or (user.get("location") or "").strip()
    if len(place) < 2:
        return {"ok": False, "code": "no_location", "error": "Enter your village or town to plan spraying."}
    data = WeatherService().get_weather_data(location=place)
    if not data.get("ok") or not data.get("hourly"):
        return {"ok": False, "code": data.get("code", "weather_unavailable"), "error": data.get("error", "Hourly forecast unavailable")}
    return {"ok": True, "location": data.get("location") or place, "provider": data.get("provider"),
            "fetched_at": data.get("fetched_at")} | spray_planner.plan(data["hourly"])


@router.get("/api/v1/irrigation")
def irrigation(location: str = Query("", max_length=80), user: dict = Depends(auth.current_user)):
    """Watering advice from live soil moisture + the rain forecast for `location` (or the user's farm location)."""
    from src import irrigation as irrigation_rules
    from src.weather_forecast import WeatherService

    place = location.strip() or (user.get("location") or "").strip()
    weather = WeatherService().get_weather_data(location=place) if len(place) >= 2 else None
    return irrigation_rules.advice(store.latest_sensor_readings(), weather) | {"location": place or None}


def device_alerts(status: dict) -> list[dict]:
    """Health warnings of the machine running the server (a Raspberry Pi), in the same shape as field alerts."""
    out = []
    device = status.get("hostname") or "server"
    temp = status.get("cpu_temp_c")
    if temp is not None and temp >= config.ALERT_PI_TEMP_C:
        out.append({"code": "pi_hot", "device": device, "value": temp, "threshold": config.ALERT_PI_TEMP_C})
    if (status.get("power") or {}).get("under_voltage_now"):
        out.append({"code": "pi_low_power", "device": device, "value": None, "threshold": None})
    return out


@router.get("/api/v1/alerts")
def alerts(user: dict = Depends(auth.current_user)):
    from src import device_status as ds

    return {"alerts": field_alerts(store.latest_sensor_readings()) + device_alerts(ds.status())}


@router.get("/api/v1/sensors/history")
def sensor_history(device_id: str = Query(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$"),
                   hours: int = Query(24, ge=1, le=168), user: dict = Depends(auth.current_user)):
    since = (datetime.now(timezone.utc).astimezone() - timedelta(hours=hours)).isoformat(timespec="seconds")
    return {"device_id": device_id, "hours": hours, "readings": store.sensor_history(device_id, since)}
