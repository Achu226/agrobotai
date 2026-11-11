import numpy as np
import pytest
from fastapi.testclient import TestClient

import server
from src import speech
from tests.conftest import LAN_PHONE
from tests.test_api_v1 import _register


@pytest.fixture()
def phone():
    return TestClient(server.app, client=LAN_PHONE)


def _tone(seconds=1.0, rate=16000, amplitude=0.3):
    t = np.arange(int(seconds * rate)) / rate
    return speech.encode_wav((amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.float32), rate)


def test_wav_roundtrip_and_resampling():
    audio = speech.decode_wav(_tone(1.0, rate=44100))
    assert abs(len(audio) - 16000) <= 1  # resampled to 16 kHz
    assert 0.25 < np.abs(audio).max() <= 0.31


@pytest.mark.parametrize("wav, code", [
    (_tone(0.1), "audio_too_short"),
    (_tone(1.0, amplitude=0.001), "silent_audio"),
    (b"RIFF not really a wav", "invalid_audio"),
], ids=["too-short", "silent", "not-wav"])
def test_bad_recordings_are_rejected(wav, code):
    with pytest.raises(speech.SpeechError) as err:
        speech.decode_wav(wav)
    assert err.value.code == code


def test_speakable_text_drops_markdown():
    assert speech.speakable("* **Remove** leaves\n# Step 2: spray") == "Remove leaves Step 2: spray"
    assert all(len(s) <= 220 for s in speech.split_sentences("word " * 200))


def test_transcribe_endpoint(phone, monkeypatch):
    seen = {}

    def fake(audio, language):
        seen["seconds"], seen["language"] = len(audio) / 16000, language
        return {"text": "இலைகளில் புள்ளிகள் உள்ளன", "language": "ta", "engine": "whisper (test)", "elapsed_s": 0.1}

    monkeypatch.setattr(speech, "transcribe", fake)
    headers, _ = _register(phone)
    res = phone.post("/api/v1/voice/transcribe", headers=headers,
                     files={"file": ("q.wav", _tone(2.0), "audio/wav")}, data={"language": "ta"})
    assert res.status_code == 200, res.text
    assert res.json()["text"] == "இலைகளில் புள்ளிகள் உள்ளன"
    assert seen == {"seconds": 2.0, "language": "ta"}


def test_transcribe_requires_sign_in_and_real_audio(phone):
    assert phone.post("/api/v1/voice/transcribe", files={"file": ("q.wav", _tone(), "audio/wav")}).status_code == 401
    headers, _ = _register(phone)
    res = phone.post("/api/v1/voice/transcribe", headers=headers, files={"file": ("q.wav", _tone(1.0, amplitude=0.0005), "audio/wav")})
    assert res.status_code == 422 and res.json()["error"]["code"] == "silent_audio"


def test_speak_endpoint_returns_audio(phone, monkeypatch):
    monkeypatch.setattr(speech, "synthesize", lambda text, lang, engine: (b"RIFF....WAVEdata", "audio/wav", f"mms-tts ({lang})"))
    headers, _ = _register(phone)
    res = phone.post("/api/v1/voice/speak", headers=headers, json={"text": "வணக்கம்", "language": "ta"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/wav"
    assert res.headers["x-voice-engine"] == "mms-tts (ta)"


def test_speak_reports_unavailable_voice(phone, monkeypatch):
    def down(text, lang, engine):
        raise speech.SpeechError(503, "tts_unavailable", "Voice output is not available: local: no model")

    monkeypatch.setattr(speech, "synthesize", down)
    headers, _ = _register(phone)
    res = phone.post("/api/v1/voice/speak", headers=headers, json={"text": "hello", "language": "en"})
    assert res.status_code == 503 and "not available" in res.json()["detail"]


def test_auto_engine_falls_back_to_local(monkeypatch):
    def offline(text, code):
        raise OSError("no internet")

    monkeypatch.setattr(speech, "_speak_online", offline)
    monkeypatch.setattr(speech, "_speak_local", lambda text, code: (b"wav-bytes", "mms-tts (test)"))
    speech._audio_cache.clear()
    audio, mime, engine = speech.synthesize("Remove infected leaves.", "en", "auto")
    assert (audio, mime, engine) == (b"wav-bytes", "audio/wav", "mms-tts (test)")
