"""
Creates (once) and shows the token the Raspberry Pi sensor agent uses to send readings.

    python scripts\\sensor_token.py          # create if missing, then print it
    python scripts\\sensor_token.py --new    # replace it (the Pi must be updated too)

The token is stored as SENSOR_INGEST_TOKEN in .env. Restart start.bat after creating it.
"""
from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"


def ensure_token(replace: bool = False) -> tuple[str, bool]:
    """Returns (token, created). Writes .env only when a new token is made."""
    text = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    match = re.search(r"^SENSOR_INGEST_TOKEN=(.*)$", text, flags=re.MULTILINE)
    current = match.group(1).strip() if match else ""
    if current and not replace:
        return current, False
    token = secrets.token_urlsafe(24)
    if match:
        text = text[:match.start()] + f"SENSOR_INGEST_TOKEN={token}" + text[match.end():]
    else:
        text = text.rstrip("\n") + ("\n" if text else "") + f"SENSOR_INGEST_TOKEN={token}\n"
    ENV.write_text(text, encoding="utf-8")
    return token, True


if __name__ == "__main__":
    token, created = ensure_token(replace="--new" in sys.argv)
    print(f"Sensor token: {token}")
    print("Paste it as \"sensor_token\" in the Raspberry Pi's config.json.")
    if created:
        print("A new token was saved to .env - restart start.bat so the server uses it.")
