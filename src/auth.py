"""
Password hashing, session tokens and FastAPI auth dependencies for the mobile API.

Passwords: PBKDF2-HMAC-SHA256 (310k iterations, random 16-byte salt).
Sessions: random 32-byte bearer tokens; only their SHA-256 hash is stored in the database.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request

from src import config, store

ITERATIONS = 310_000
MIN_PASSWORD_LEN = 8


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def validate_new_credentials(username: str, password: str):
    username = (username or "").strip()
    if not (3 <= len(username) <= 40) or not all(c.isalnum() or c in "._-" for c in username):
        raise HTTPException(status_code=422, detail="Username must be 3-40 characters: letters, digits, '.', '_' or '-'.")
    if len(password or "") < MIN_PASSWORD_LEN:
        raise HTTPException(status_code=422, detail=f"Password must be at least {MIN_PASSWORD_LEN} characters.")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def client_info(request: Request | None) -> tuple[str | None, str | None]:
    """(device, ip) of a login, for the admin's "who is logged in" page. The app sends X-Client."""
    if request is None:
        return None, None
    device = request.headers.get("x-client") or request.headers.get("user-agent") or ""
    return device[:160] or None, request.client.host if request.client else None


def issue_session(user_id: int, request: Request | None = None) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=config.SESSION_DAYS)).isoformat(timespec="seconds")
    store.create_session(_token_hash(token), user_id, expires, *client_info(request))
    return token, expires


def login(username: str, password: str, request: Request | None = None) -> tuple[dict, str, str]:
    found = store.get_user_auth(username or "")
    # Always run one PBKDF2 so response time does not reveal whether the username exists
    if not found:
        verify_password(password or "", hash_password("timing-equalizer"))
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    user, stored_hash = found
    if not user["is_active"] or not verify_password(password or "", stored_hash):
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    token, expires = issue_session(user["id"], request)
    return user, token, expires


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def revoke(request: Request):
    token = _bearer_token(request)
    if token:
        store.delete_session(_token_hash(token))


def current_user(request: Request) -> dict:
    token = _bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required.", headers={"WWW-Authenticate": "Bearer"})
    user = store.session_user(_token_hash(token))
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please sign in again.",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return user
