"""
Multilingual Voice & NLP Audio Service
Supports:
1. Microsoft Edge Neural TTS (edge-tts): Zero-Cost, Studio-Quality Neural Voice in Tamil, Hindi, Telugu, etc.
2. ElevenLabs Multilingual v2 (High-Fidelity AI Voice)
3. gTTS / Indic Stream Fallback Engine
4. Speech-to-Text (STT) Transcription Pipeline
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import urllib.parse
from typing import Optional, Dict, Any, List
import requests

from src.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_TIMEOUT_SECONDS,
)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM").strip()  # Rachel / Multilingual
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip()

# Edge-TTS Neural Voice Map for Indian Languages and English
EDGE_TTS_VOICE_MAP = {
    "ta": "ta-IN-PallaviNeural",     # Tamil (India) - Female
    "ta_male": "ta-IN-ValluvarNeural", # Tamil (India) - Male
    "hi": "hi-IN-SwaraNeural",       # Hindi (India) - Female
    "hi_male": "hi-IN-MadhurNeural", # Hindi (India) - Male
    "te": "te-IN-ShrutiNeural",      # Telugu (India) - Female
    "te_male": "te-IN-MohanNeural",  # Telugu (India) - Male
    "kn": "kn-IN-SapnaNeural",       # Kannada (India) - Female
    "kn_male": "kn-IN-GaganNeural",  # Kannada (India) - Male
    "ml": "ml-IN-SobhanaNeural",     # Malayalam (India) - Female
    "ml_male": "ml-IN-MidhunNeural", # Malayalam (India) - Male
    "mr": "mr-IN-AarohiNeural",      # Marathi (India) - Female
    "mr_male": "mr-IN-ManoharNeural",# Marathi (India) - Male
    "bn": "bn-IN-TanishaaNeural",    # Bengali (India) - Female
    "bn_male": "bn-IN-BashkarNeural",# Bengali (India) - Male
    "gu": "gu-IN-DhwaniNeural",      # Gujarati (India) - Female
    "gu_male": "gu-IN-NiranjanNeural",# Gujarati (India) - Male
    "pa": "pa-IN-GurpreetNeural",    # Punjabi (India) - Female
    "pa_male": "pa-IN-OjasNeural",   # Punjabi (India) - Male
    "en": "en-IN-NeerjaNeural",      # English (India) - Female
    "en_male": "en-IN-PrabhatNeural",# English (India) - Male
}

# Supported language codes mapping for gTTS / Google TTS
TTS_LANG_MAP = {
    "ta": "ta",      # Tamil
    "hi": "hi",      # Hindi
    "te": "te",      # Telugu
    "kn": "kn",      # Kannada
    "ml": "ml",      # Malayalam
    "mr": "mr",      # Marathi
    "bn": "bn",      # Bengali
    "pa": "pa",      # Punjabi
    "gu": "gu",      # Gujarati
    "en": "en",      # English
}

# ElevenLabs curated voice presets for Indic agricultural advisory
ELEVENLABS_VOICE_PRESETS = {
    "female_advisor": "21m00Tcm4TlvDq8ikWAM",  # Rachel - Warm, empathetic
    "male_agronomist": "pNInz6obpgDQGcFmaJgB", # Adam - Authoritative, clear
    "elder_advisor": "ErXwobaYiN019PkySvjV",   # Antoni - Calm, steady
}


def detect_script_language(text: str, fallback_lang: str = "ta") -> str:
    """
    Detect the language directly from the Unicode script of the text.
    Ensures Tamil text is ALWAYS spoken by a Tamil voice, regardless of dropdown setting.
    """
    if not text:
        return fallback_lang

    counts = {
        "ta": len(re.findall(r'[஀-௿]', text)),  # Tamil
        "hi": len(re.findall(r'[ऀ-ॿ]', text)),  # Devanagari (Hindi/Marathi)
        "te": len(re.findall(r'[ఀ-౿]', text)),  # Telugu
        "kn": len(re.findall(r'[ಀ-೿]', text)),  # Kannada
        "ml": len(re.findall(r'[ഀ-ൿ]', text)),  # Malayalam
        "bn": len(re.findall(r'[ঀ-৿]', text)),  # Bengali
        "gu": len(re.findall(r'[઀-૿]', text)),  # Gujarati
        "pa": len(re.findall(r'[਀-੿]', text)),  # Gurmukhi (Punjabi)
    }

    max_lang = max(counts, key=counts.get)
    if counts[max_lang] >= 2:
        return max_lang

    # Check for English / Latin script
    latin_count = len(re.findall(r'[a-zA-Z]', text))
    if latin_count > 5 and counts[max_lang] == 0:
        return "en"

    return fallback_lang


def clean_text_for_speech(text: str) -> str:
    """Clean markdown markers, URLs, emojis, and special chars for smooth phonetic speech."""
    if not text:
        return ""
    # Remove markdown formatting like **bold**, *italic*, # headers, bullets
    cleaned = re.sub(r'[*#_`~[\]()>]', ' ', text)
    # Remove URLs
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    # Remove numbered list markers like "1. ", "2. " into clean pauses
    cleaned = re.sub(r'^\s*\d+\.\s*', '', cleaned, flags=re.MULTILINE)
    # Remove emojis
    cleaned = re.sub(r'[\U00010000-\U0010ffff]', '', cleaned)
    # Remove excessive whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def split_text_into_chunks(text: str, max_chunk_len: int = 220) -> List[str]:
    """Split long text into sentence-level chunks for smooth audio synthesis without cutoffs."""
    sentences = re.split(r'([.!?\n।]+)', text)
    chunks = []
    current_chunk = ""

    for part in sentences:
        if not part:
            continue
        if len(current_chunk) + len(part) < max_chunk_len:
            current_chunk += part
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = part

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


class MultilingualVoiceService:
    """Handles text-to-speech and speech-to-text with Edge Neural TTS, ElevenLabs, and robust fallbacks."""

    def __init__(self, elevenlabs_api_key: Optional[str] = None):
        self.elevenlabs_key = (elevenlabs_api_key or ELEVENLABS_API_KEY).strip()

    def generate_speech(
        self,
        text: str,
        language: str = "ta",
        voice_id: Optional[str] = None,
        custom_elevenlabs_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate high-quality speech audio (MP3 bytes) for the given text.

        Hierarchy:
        1. ElevenLabs Multilingual v2 (if valid API key provided)
        2. Microsoft Edge Neural TTS (zero-cost, studio-quality, high fidelity for Indic languages)
        3. gTTS (Google Text-to-Speech Python Library)
        4. Indic Neural Audio HTTP Fallback
        """
        clean_text = clean_text_for_speech(text)
        if not clean_text:
            return {"ok": False, "error": "Empty text provided for speech synthesis"}

        # Auto-detect script language from text Unicode characters (e.g. Tamil Unicode -> 'ta')
        detected_lang = detect_script_language(clean_text, fallback_lang=language)
        effective_lang = detected_lang or language or "ta"

        api_key = (custom_elevenlabs_key or self.elevenlabs_key).strip()
        selected_voice = (voice_id or ELEVENLABS_VOICE_ID).strip()

        # 1. Try ElevenLabs if valid API key is provided
        if api_key and api_key != "ollama":
            try:
                audio_bytes = self._generate_elevenlabs_speech(
                    text=clean_text,
                    api_key=api_key,
                    voice_id=selected_voice
                )
                if audio_bytes:
                    return {
                        "ok": True,
                        "audio_bytes": audio_bytes,
                        "content_type": "audio/mpeg",
                        "engine": "elevenlabs",
                        "language": effective_lang
                    }
            except Exception as e:
                print(f"[VoiceService] ElevenLabs note: {e}. Falling back to Edge Neural TTS.")

        # 2. Microsoft Edge Neural TTS (Primary Zero-Cost Engine with Studio Quality)
        try:
            audio_bytes = self._generate_edge_tts_speech(text=clean_text, language=effective_lang)
            if audio_bytes and len(audio_bytes) > 200:
                return {
                    "ok": True,
                    "audio_bytes": audio_bytes,
                    "content_type": "audio/mpeg",
                    "engine": "edge_neural_tts",
                    "language": effective_lang
                }
        except Exception as e:
            print(f"[VoiceService] Edge-TTS error: {e}. Trying gTTS fallback.")

        # 3. gTTS Library Fallback
        try:
            audio_bytes = self._generate_gtts_speech(text=clean_text, language=effective_lang)
            if audio_bytes and len(audio_bytes) > 200:
                return {
                    "ok": True,
                    "audio_bytes": audio_bytes,
                    "content_type": "audio/mpeg",
                    "engine": "gtts",
                    "language": effective_lang
                }
        except Exception as e:
            print(f"[VoiceService] gTTS error: {e}. Trying Google stream fallback.")

        # 4. Google Translate HTTP Stream Fallback
        try:
            audio_bytes = self._generate_indic_speech(text=clean_text, language=effective_lang)
            if audio_bytes and len(audio_bytes) > 100:
                return {
                    "ok": True,
                    "audio_bytes": audio_bytes,
                    "content_type": "audio/mpeg",
                    "engine": "indic_stream",
                    "language": effective_lang
                }
        except Exception as e:
            print(f"[VoiceService] Indic stream error: {e}")

        return {"ok": False, "error": "Unable to synthesize audio stream across all voice engines"}

    def _generate_edge_tts_speech(self, text: str, language: str) -> Optional[bytes]:
        """Synthesize neural audio via Microsoft Edge TTS async engine."""
        import edge_tts

        voice = EDGE_TTS_VOICE_MAP.get(language, EDGE_TTS_VOICE_MAP.get("ta", "ta-IN-PallaviNeural"))

        async def _run():
            communicate = edge_tts.Communicate(text, voice)
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            return b"".join(audio_chunks)

        # Run async coroutine safely in synchronous context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In nested event loop (e.g. FastAPI worker thread)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(_run())).result(timeout=15)
            else:
                return loop.run_until_complete(_run())
        except Exception:
            return asyncio.run(_run())

    def _generate_gtts_speech(self, text: str, language: str) -> Optional[bytes]:
        """Synthesize audio via gTTS library."""
        from gtts import gTTS
        target_lang = TTS_LANG_MAP.get(language, "ta")
        tts = gTTS(text=text, lang=target_lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        data = fp.read()
        return data if len(data) > 0 else None

    def _generate_elevenlabs_speech(self, text: str, api_key: str, voice_id: str) -> Optional[bytes]:
        """Call ElevenLabs Multilingual v2 REST API."""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        payload = {
            "text": text,
            "model_id": ELEVENLABS_MODEL_ID,
            "voice_settings": {
                "stability": 0.50,
                "similarity_boost": 0.80,
                "style": 0.15,
                "use_speaker_boost": True
            }
        }
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        if response.status_code == 200 and len(response.content) > 100:
            return response.content
        else:
            raise RuntimeError(f"ElevenLabs API returned {response.status_code}: {response.text}")

    def _generate_indic_speech(self, text: str, language: str) -> Optional[bytes]:
        """Generate audio stream via Google Translate HTTP TTS."""
        target_lang = TTS_LANG_MAP.get(language, "ta")
        chunks = split_text_into_chunks(text, max_chunk_len=180)

        combined_audio = io.BytesIO()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://translate.google.com/"
        }

        for chunk in chunks:
            if not chunk.strip():
                continue
            encoded = urllib.parse.quote(chunk)
            url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded}&tl={target_lang}&client=tw-ob"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200 and len(res.content) > 0:
                combined_audio.write(res.content)

        data = combined_audio.getvalue()
        if len(data) > 0:
            return data
        return None

    def transcribe_audio(
        self,
        audio_file_bytes: bytes,
        language: str = "ta",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe spoken audio from microphone into text.
        Uses OpenAI / Groq Whisper API when API key is provided.
        """
        effective_key = (api_key or OPENAI_API_KEY).strip()
        if not effective_key or effective_key == "ollama":
            return {
                "ok": False,
                "error": "STT requires an OpenAI / Groq API key or client-side Web Speech API."
            }

        try:
            from openai import OpenAI
            base_url = (os.getenv("OPENAI_BASE_URL", "") or OPENAI_BASE_URL).strip()

            client_kwargs = {"api_key": effective_key, "timeout": OPENAI_TIMEOUT_SECONDS}
            if effective_key.startswith("gsk_"):
                client_kwargs["base_url"] = "https://api.groq.com/openai/v1"
            elif base_url and "localhost" not in base_url:
                client_kwargs["base_url"] = base_url

            client = OpenAI(**client_kwargs)

            # Create in-memory file for transcription
            audio_io = io.BytesIO(audio_file_bytes)
            audio_io.name = "recording.wav"

            model_name = "whisper-1" if not effective_key.startswith("gsk_") else "whisper-large-v3"

            transcript = client.audio.transcriptions.create(
                model=model_name,
                file=audio_io,
                language=language if language in ("en", "ta", "hi", "te", "kn", "ml") else None
            )

            return {
                "ok": True,
                "text": transcript.text.strip(),
                "language": language
            }
        except Exception as e:
            return {
                "ok": False,
                "error": f"Audio transcription failed: {str(e)}"
            }
