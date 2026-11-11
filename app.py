"""
HORTICBOTAI - AI Crop Health Diagnostic & Precision Advisory Platform
Main application entry point. Launches the FastAPI server serving the React UI.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
import uvicorn

from server import app

def _init_ollama_background():
    try:
        from src.ollama_manager import ensure_ollama_ready
        ensure_ollama_ready()
    except Exception as exc:
        print(f"[Ollama Manager] Background start note: {exc}")


def _lan_ip() -> str:
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main():
    # --lan (or AGROBOT_HOST=0.0.0.0) exposes the API to phones on the same Wi-Fi,
    # which the Flutter mobile app needs.
    host = "0.0.0.0" if "--lan" in sys.argv else os.getenv("AGROBOT_HOST", "127.0.0.1")
    port = int(os.getenv("AGROBOT_PORT", "8000"))

    print("=" * 65)
    print(" HORTICBOTAI - AI Crop Health Diagnostic & Advisory System")
    print("=" * 65)
    print("\n Starting FastAPI backend + React Single-Page Application...")
    print(f" URL: http://localhost:{port}")
    print(f" API Docs: http://localhost:{port}/docs")
    if host == "0.0.0.0":
        phone_url = f"http://{_lan_ip()}:{port}"
        print()
        lines = [f"PHONE SERVER URL:  {phone_url}",
                 "The AGROBOTAI app finds this automatically on the same",
                 "Wi-Fi. Otherwise: Login > Change > type the URL above."]
        print(" +" + "-" * 61 + "+")
        for line in lines:
            print(f" |  {line:<59}|")
        print(" +" + "-" * 61 + "+")
        print()
    print(" Press Ctrl+C to stop the server\n")

    # Automatically start Ollama LLM service in background
    threading.Thread(target=_init_ollama_background, daemon=True).start()

    # Automatically open the browser
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass

    uvicorn.run("server:app", host=host, port=port, reload=False, timeout_keep_alive=15,
                limit_concurrency=32, timeout_graceful_shutdown=5)


if __name__ == "__main__":
    main()

