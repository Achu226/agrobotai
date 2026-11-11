"""
Ollama Local Offline AI Service Manager for HORTICBOTAI
Handles automatic detection, background lifecycle management, and pre-warming
of the offline agri-qwen:7b / qwen2.5:7b model on GPU.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_OLLAMA_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1").replace("/v1", "")
# The advisor model (gemma3:4b writes good Tamil/Hindi). Warming the old 7B model wasted VRAM
# that gemma then had to compete for on the 6 GB GPU.
DEFAULT_MODEL = (os.getenv("ADVISOR_MODEL") or "gemma3:4b").strip()


def find_ollama_binary() -> str | None:
    """Finds the absolute path to the ollama executable on Windows/Linux."""
    which_path = shutil.which("ollama")
    if which_path:
        return which_path

    # Common Windows installation locations
    candidate_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\Ollama\ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
        r"C:\Users\Admin\AppData\Local\Programs\Ollama\ollama.exe",
        os.path.expandvars(r"%ProgramFiles%\Ollama\ollama.exe"),
    ]

    for p in candidate_paths:
        if os.path.isfile(p):
            return p

    return None


def is_ollama_running(base_url: str = "http://localhost:11434", timeout: float = 1.5) -> bool:
    """Checks if Ollama HTTP service is actively responding."""
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HORTICBOTAI-HealthCheck"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_available_models(base_url: str = "http://localhost:11434") -> list[str]:
    """Returns list of downloaded model tags in local Ollama instance."""
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HORTICBOTAI-HealthCheck"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception:
        pass
    return []


def start_ollama_service() -> bool:
    """
    Starts Ollama server in background if it is not already running.
    Returns True if service is verified online.
    """
    if is_ollama_running():
        return True

    ollama_bin = find_ollama_binary()
    if not ollama_bin:
        print("[Ollama Manager] Ollama executable not found in system PATH or standard folders.")
        return False

    print(f"[Ollama Manager] Launching Ollama background service via {ollama_bin}...")
    try:
        creation_flags = 0
        if sys.platform == "win32":
            # DETACHED_PROCESS (0x00000008) | CREATE_NO_WINDOW (0x08000000)
            creation_flags = 0x00000008 | 0x08000000

        subprocess.Popen(
            [ollama_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            close_fds=True,
        )

        # Wait up to 8 seconds for server to become responsive
        for attempt in range(1, 17):
            time.sleep(0.5)
            if is_ollama_running():
                print(f"[Ollama Manager] Ollama service successfully started and ready (took {attempt * 0.5:.1f}s).")
                return True

        print("[Ollama Manager] Ollama process started, but API health check timed out.")
        return False
    except Exception as exc:
        print(f"[Ollama Manager] Failed to launch Ollama service: {exc}")
        return False


def _prewarm_worker(model_name: str, base_url: str = "http://localhost:11434"):
    """Background worker that warms up the model in GPU memory."""
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model_name,
        "prompt": "Hello",
        "stream": False,
        "keep_alive": "24h",  # Keep model resident in GPU VRAM
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "HORTICBOTAI-Prewarm"},
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            if resp.status == 200:
                print(f"[Ollama Manager] 🧠 Model '{model_name}' loaded into GPU VRAM (keep_alive: 24h).")
    except Exception as exc:
        # Pre-warming is non-blocking; failure just means lazy load on first request
        pass


def prewarm_model_in_background(model_name: str = DEFAULT_MODEL):
    """Spawns a daemon thread to load model weights into GPU VRAM."""
    thread = threading.Thread(target=_prewarm_worker, args=(model_name,), daemon=True)
    thread.start()


def ensure_ollama_ready(model_name: str = DEFAULT_MODEL) -> bool:
    """
    Main entry point: ensures Ollama service is running and triggers background pre-warming.
    """
    active = start_ollama_service()
    if active:
        models = get_available_models()
        target = model_name
        # Fallback to qwen2.5:7b or first available model if target isn't explicitly installed
        if target not in models and "qwen2.5:7b" in models:
            target = "qwen2.5:7b"
        elif target not in models and models:
            target = models[0]

        print(f"[Ollama Manager] Active Offline AI Model: {target} (Models installed: {models})")
        prewarm_model_in_background(target)
        return True
    return False
