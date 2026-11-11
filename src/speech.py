"""
Local speech for the farmer app — runs on this laptop, no cloud needed.

* Speech-to-text: OpenAI Whisper large-v3-turbo (Hugging Face transformers). Tamil, English,
  Hindi and 9 more Indian languages. Uses the GPU when enough VRAM is free (the disease models
  and the chat LLM share the 6 GB card), otherwise the CPU.
* Text-to-speech: Meta MMS-TTS (VITS) voices, one small model (~145 MB) per language; on the GPU
  when there is room (about 1 s per answer), else the CPU (3-5 s).
  Optional "online" engine: Microsoft Edge neural voices (more natural, needs internet).

Models are downloaded once into the Hugging Face cache (~1.6 GB Whisper + ~145 MB per voice).
Nothing here invents text: transcription failures are reported as errors.
"""
from __future__ import annotations

import hashlib
import io
import re
import threading
import time
import wave
from collections import OrderedDict

import numpy as np

WHISPER_MODEL = "openai/whisper-large-v3-turbo"
SAMPLE_RATE = 16000
MAX_AUDIO_SECONDS = 60

# app language code -> (Whisper language name or None if Whisper does not support it, MMS-TTS repo, Edge voice)
LANGS: dict[str, tuple[str | None, str, str]] = {
    "ta": ("tamil", "facebook/mms-tts-tam", "ta-IN-PallaviNeural"),
    "en": ("english", "facebook/mms-tts-eng", "en-IN-NeerjaNeural"),
    "hi": ("hindi", "facebook/mms-tts-hin", "hi-IN-SwaraNeural"),
    "te": ("telugu", "facebook/mms-tts-tel", "te-IN-ShrutiNeural"),
    "kn": ("kannada", "facebook/mms-tts-kan", "kn-IN-SapnaNeural"),
    "ml": ("malayalam", "facebook/mms-tts-mal", "ml-IN-SobhanaNeural"),
    "mr": ("marathi", "facebook/mms-tts-mar", "mr-IN-AarohiNeural"),
    "bn": ("bengali", "facebook/mms-tts-ben", "bn-IN-TanishaaNeural"),
    "gu": ("gujarati", "facebook/mms-tts-guj", "gu-IN-DhwaniNeural"),
    "pa": ("punjabi", "facebook/mms-tts-pan", "pa-IN-OjasNeural"),
    "or": (None, "facebook/mms-tts-ory", "or-IN-SubhasiniNeural"),
    "ur": ("urdu", "facebook/mms-tts-urd-script_arabic", "ur-IN-GulNeural"),
}
_WHISPER_TO_CODE = {v[0]: k for k, v in LANGS.items() if v[0]}


class SpeechError(RuntimeError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# ---------------------------------------------------------------- audio helpers

def decode_wav(data: bytes) -> np.ndarray:
    """16 kHz mono float32 from a PCM WAV file (what the phone app records)."""
    try:
        with wave.open(io.BytesIO(data)) as w:
            channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(frames)
    except (wave.Error, EOFError) as exc:
        raise SpeechError(400, "invalid_audio", f"Audio must be a PCM WAV recording: {exc}")
    if width != 2:
        raise SpeechError(400, "invalid_audio", "Audio must be 16-bit PCM WAV.")
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != SAMPLE_RATE and len(audio):
        n = int(len(audio) * SAMPLE_RATE / rate)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)
    seconds = len(audio) / SAMPLE_RATE
    if seconds < 0.3:
        raise SpeechError(422, "audio_too_short", "Recording is too short. Hold the mic button and speak.")
    if seconds > MAX_AUDIO_SECONDS:
        raise SpeechError(413, "audio_too_long", f"Recording is longer than {MAX_AUDIO_SECONDS} seconds.")
    if float(np.abs(audio).max()) < 0.01:
        raise SpeechError(422, "silent_audio", "No speech heard — the recording is silent. Check the microphone.")
    return audio


def encode_wav(audio: np.ndarray, rate: int) -> bytes:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def speakable(text: str) -> str:
    """Removes markdown bullets/symbols that voices read out literally."""
    text = re.sub(r"[*#_`>|~]+", " ", text or "")
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str, max_len: int = 220) -> list[str]:
    parts = re.split(r"(?<=[.!?।॥\n])\s+", text)
    out: list[str] = []
    for p in (x.strip() for x in parts):
        while len(p) > max_len:
            cut = p.rfind(" ", 0, max_len)
            cut = cut if cut > 40 else max_len
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            out.append(p)
    return out


# ---------------------------------------------------------------- speech-to-text

_whisper = {"pipe": None, "device": None, "error": None, "loading": False}
_whisper_lock = threading.Lock()


def _pick_device(min_free_gb: float) -> str:
    try:
        import torch

        if torch.cuda.is_available():
            free, _ = torch.cuda.mem_get_info()
            if free / 1e9 >= min_free_gb:
                return "cuda"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


def load_whisper() -> dict:
    with _whisper_lock:
        if _whisper["pipe"] is not None or _whisper["error"]:
            return _whisper
        _whisper["loading"] = True
        try:
            import torch
            from transformers import pipeline

            device = _pick_device(2.2)
            _whisper["pipe"] = pipeline(
                "automatic-speech-recognition", model=WHISPER_MODEL, device=device,
                dtype=torch.float16 if device == "cuda" else torch.float32,
            )
            _whisper["device"] = device
        except Exception as exc:  # noqa: BLE001 - reported by /voice/status and on use
            _whisper["error"] = f"Speech recognition model could not be loaded: {exc}"
        finally:
            _whisper["loading"] = False
        return _whisper


def transcribe(audio: np.ndarray, language: str | None = None) -> dict:
    state = load_whisper()
    if state["pipe"] is None:
        raise SpeechError(503, "stt_unavailable", state["error"] or "Speech recognition is not available.")
    whisper_lang = LANGS.get(language or "", (None,))[0]
    kwargs = {"task": "transcribe"}
    if whisper_lang:
        kwargs["language"] = whisper_lang
    started = time.perf_counter()
    with _whisper_lock:
        out = state["pipe"]({"raw": audio, "sampling_rate": SAMPLE_RATE}, generate_kwargs=kwargs, return_language=True)
    text = (out.get("text") or "").strip()
    chunks = out.get("chunks") or []
    detected = (chunks[0].get("language") if chunks else None) or whisper_lang
    if not text:
        raise SpeechError(422, "no_speech", "No words were recognised. Speak closer to the phone and try again.")
    return {
        "text": text,
        "language": _WHISPER_TO_CODE.get(detected or "", language),
        "engine": f"whisper-large-v3-turbo ({state['device']})",
        "audio_seconds": round(len(audio) / SAMPLE_RATE, 1),
        "elapsed_s": round(time.perf_counter() - started, 2),
    }


# ---------------------------------------------------------------- text-to-speech

_voices: OrderedDict[str, tuple] = OrderedDict()  # repo -> (model, tokenizer); a few kept in memory
_voice_lock = threading.Lock()
_audio_cache: OrderedDict[str, tuple[bytes, str, str]] = OrderedDict()
MAX_VOICES_LOADED = 4
MAX_CACHED_CLIPS = 64


def _voice(repo: str):
    if repo in _voices:
        _voices.move_to_end(repo)
        return _voices[repo]
    from transformers import AutoTokenizer, VitsModel

    device = _pick_device(0.8)
    model = VitsModel.from_pretrained(repo).eval().to(device)
    tokenizer = AutoTokenizer.from_pretrained(repo)
    _voices[repo] = (model, tokenizer)
    while len(_voices) > MAX_VOICES_LOADED:
        _voices.popitem(last=False)
    return _voices[repo]


def _romanize(text: str) -> str:
    import uroman

    return uroman.Uroman().romanize_string(text)


def _speak_local(text: str, code: str) -> tuple[bytes, str]:
    import torch

    repo = LANGS[code][1]
    with _voice_lock:
        model, tokenizer = _voice(repo)
        pieces = []
        silence = np.zeros(int(model.config.sampling_rate * 0.25), dtype=np.float32)
        for sentence in split_sentences(text):
            if getattr(tokenizer, "is_uroman", False):
                sentence = _romanize(sentence)
            inputs = tokenizer(sentence, return_tensors="pt").to(model.device)
            if inputs["input_ids"].shape[-1] == 0:
                continue
            with torch.inference_mode():
                wav = model(**inputs).waveform[0].float().cpu().numpy()
            pieces += [wav, silence]
        if not pieces:
            raise SpeechError(422, "nothing_to_say", "There is no speakable text in this language.")
        desc = f"mms-tts ({repo.split('/')[-1]}, {model.device.type})"
        return encode_wav(np.concatenate(pieces), model.config.sampling_rate), desc


def _speak_online(text: str, code: str) -> tuple[bytes, str]:
    import asyncio

    import edge_tts

    async def run() -> bytes:
        out = bytearray()
        async for chunk in edge_tts.Communicate(text, LANGS[code][2]).stream():
            if chunk["type"] == "audio":
                out.extend(chunk["data"])
        return bytes(out)

    data = asyncio.run(asyncio.wait_for(run(), timeout=15))
    if len(data) < 500:
        raise SpeechError(502, "tts_online_failed", "Online voice returned no audio.")
    return data, f"edge-neural ({LANGS[code][2]})"


def synthesize(text: str, language: str, engine: str = "local") -> tuple[bytes, str, str]:
    """Returns (audio bytes, mime type, engine description). engine: local | online | auto."""
    code = language if language in LANGS else "en"
    clean = speakable(text)[:3000]
    if not clean:
        raise SpeechError(422, "nothing_to_say", "No text to read aloud.")
    key = hashlib.sha256(f"{code}|{engine}|{clean}".encode()).hexdigest()
    if key in _audio_cache:
        _audio_cache.move_to_end(key)
        return _audio_cache[key]

    attempts = {"local": ["local"], "online": ["online"], "auto": ["online", "local"]}.get(engine, ["local"])
    errors = []
    for which in attempts:
        try:
            if which == "online":
                audio, desc = _speak_online(clean, code)
                result = (audio, "audio/mpeg", desc)
            else:
                audio, desc = _speak_local(clean, code)
                result = (audio, "audio/wav", desc)
            _audio_cache[key] = result
            while len(_audio_cache) > MAX_CACHED_CLIPS:
                _audio_cache.popitem(last=False)
            return result
        except SpeechError:
            raise
        except Exception as exc:  # noqa: BLE001 - try the next engine, report all if none works
            errors.append(f"{which}: {exc}")
    raise SpeechError(503, "tts_unavailable", "Voice output is not available: " + "; ".join(errors))


def preload_voices(codes=("ta", "en")):
    """Load the most used voices at startup so the first "Listen" is not slowed by model loading (~20 s)."""
    for code in codes:
        try:
            with _voice_lock:
                _voice(LANGS[code][1])
        except Exception as exc:  # noqa: BLE001 - voices then load on first use
            print(f"[speech] could not preload {code} voice: {exc}")


def status() -> dict:
    import importlib.util

    has_transformers = importlib.util.find_spec("transformers") is not None
    return {
        "speech_to_text": {
            "engine": "whisper-large-v3-turbo",
            "ready": _whisper["pipe"] is not None,
            "loading": _whisper["loading"],
            "device": _whisper["device"],
            "error": _whisper["error"] or (None if has_transformers else "transformers is not installed"),
            "languages": [c for c, v in LANGS.items() if v[0]],
        },
        "text_to_speech": {
            "local": {"engine": "mms-tts", "available": has_transformers, "languages": list(LANGS)},
            "online": {"engine": "edge-neural", "available": importlib.util.find_spec("edge_tts") is not None,
                       "note": "needs internet"},
        },
    }
