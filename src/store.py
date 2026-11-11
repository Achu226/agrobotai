"""
Persistent storage (SQLite) for users, sessions, scans, admin reviews and sensor readings.

The schema is versioned: `migrate()` applies numbered migrations once and records them in
`schema_version`, so existing data (including legacy `scan_history` rows written by older
versions of the web UI) is preserved.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src import config

REVIEW_STATES = ("pending", "approved", "rejected")
INFERENCE_STATES = ("succeeded", "partial", "failed")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def db_path() -> Path:
    return Path(config.DB_PATH)


@contextmanager
def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migration_1(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            full_name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL CHECK (role IN ('farmer', 'admin')),
            password_hash TEXT NOT NULL,
            farm_name TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            source TEXT NOT NULL DEFAULT 'mobile',
            client_request_id TEXT,
            captured_at TEXT,
            received_at TEXT NOT NULL,
            crop_selected TEXT,
            crop_reported TEXT,
            image_path TEXT,
            inference_status TEXT NOT NULL CHECK (inference_status IN ('succeeded', 'partial', 'failed')),
            summary_state TEXT,
            disease_label TEXT,
            disease_state TEXT,
            disease_confidence REAL,
            pest_label TEXT,
            pest_state TEXT,
            pest_confidence REAL,
            health_index REAL,
            severity_pct REAL,
            model_versions TEXT,
            result_json TEXT,
            error TEXT,
            review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected')),
            reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            reviewed_at TEXT,
            review_comment TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_scans_client_request
            ON scans(user_id, client_request_id) WHERE client_request_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS ix_scans_user ON scans(user_id, id);
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            received_at TEXT NOT NULL,
            measured_at TEXT,
            readings_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sensor_device ON sensor_readings(device_id, id);
        """
    )
    # Carry over history written by the older web UI (table `scan_history`), if present
    legacy = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scan_history'").fetchone()
    if legacy:
        for row in conn.execute("SELECT * FROM scan_history").fetchall():
            summary = json.loads(row["summary_json"] or "{}")
            conn.execute(
                """INSERT INTO scans (uuid, source, received_at, captured_at, crop_reported, inference_status,
                       disease_label, disease_confidence, pest_label, pest_confidence, health_index, result_json)
                   VALUES (?, 'web', ?, ?, ?, 'succeeded', ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), row["timestamp"], row["timestamp"], row["crop"], row["disease_label"],
                 row["disease_confidence"], row["pest_label"], row["pest_confidence"], row["overall_score"],
                 json.dumps({"legacy": True, **summary})),
            )


def _migration_2(conn: sqlite3.Connection):
    # Plot / plant name chosen by the farmer, to track recovery across scans of the same plot
    conn.execute("ALTER TABLE scans ADD COLUMN plot TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_scans_user_plot ON scans(user_id, plot)")


def _migration_3(conn: sqlite3.Connection):
    # Which device a login came from (admin "who is logged in" page)
    conn.execute("ALTER TABLE sessions ADD COLUMN device TEXT")
    conn.execute("ALTER TABLE sessions ADD COLUMN ip TEXT")
    # Farm diary: what the farmer did on each plot, with an optional reminder date
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS diary_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plot TEXT NOT NULL,
            kind TEXT NOT NULL,
            product TEXT,
            quantity TEXT,
            cost REAL,
            note TEXT,
            done_on TEXT NOT NULL,
            remind_on TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_diary_user ON diary_entries(user_id, done_on);
        """
    )


def _migration_4(conn: sqlite3.Connection):
    # Repeating care reminders ("water every 3 days"): days between reminders, NULL = one-time
    conn.execute("ALTER TABLE diary_entries ADD COLUMN repeat_days INTEGER")


MIGRATIONS = [_migration_1, _migration_2, _migration_3, _migration_4]


def migrate():
    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        current = row["v"] or 0
        for version, migration in enumerate(MIGRATIONS, start=1):
            if version > current:
                migration(conn)
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


# ---------------------------------------------------------------- users & sessions

def _user_dict(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "full_name": row["full_name"],
        "role": row["role"],
        "farm_name": row["farm_name"],
        "location": row["location"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def create_user(username: str, password_hash: str, role: str, full_name: str = "", farm_name: str = "", location: str = "") -> dict:
    migrate()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, full_name, role, password_hash, farm_name, location, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (username.strip(), full_name.strip(), role, password_hash, farm_name.strip(), location.strip(), now_iso()),
        )
        return _user_dict(conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


def get_user_auth(username: str) -> tuple[dict, str] | None:
    migrate()
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
        return (_user_dict(row), row["password_hash"]) if row else None


def get_user(user_id: int) -> dict | None:
    with connect() as conn:
        return _user_dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def set_password(user_id: int, password_hash: str):
    with connect() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def list_users() -> list[dict]:
    migrate()
    with connect() as conn:
        rows = conn.execute(
            """SELECT u.*, (SELECT COUNT(*) FROM scans s WHERE s.user_id = u.id AND s.inference_status != 'failed') AS scan_count
               FROM users u ORDER BY u.id"""
        ).fetchall()
        return [_user_dict(r) | {"scan_count": r["scan_count"]} for r in rows]


def count_admins() -> int:
    migrate()
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1").fetchone()[0]


def create_session(token_hash: str, user_id: int, expires_at: str, device: str | None = None, ip: str | None = None):
    migrate()
    with connect() as conn:
        t = now_iso()
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, last_seen, device, ip) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_hash, user_id, t, expires_at, t, device, ip))


def list_sessions() -> list[dict]:
    """Unexpired logins with their user, newest activity first (never the token)."""
    migrate()
    with connect() as conn:
        rows = conn.execute(
            """SELECT s.created_at, s.expires_at, s.last_seen, s.device, s.ip,
                      u.id AS user_id, u.username, u.full_name, u.role, u.location
               FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE u.is_active = 1 ORDER BY s.last_seen DESC"""
        ).fetchall()
    now = datetime.now(timezone.utc)
    return [dict(r) for r in rows if datetime.fromisoformat(r["expires_at"]) >= now]


def session_user(token_hash: str) -> dict | None:
    migrate()
    with connect() as conn:
        row = conn.execute(
            """SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND u.is_active = 1""",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            return None
        conn.execute("UPDATE sessions SET last_seen = ? WHERE token_hash = ?", (now_iso(), token_hash))
        return _user_dict(row)


def delete_session(token_hash: str):
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


# ---------------------------------------------------------------- farm diary

DIARY_COLUMNS = ("id", "plot", "kind", "product", "quantity", "cost", "note", "done_on", "remind_on", "created_at", "repeat_days")


def next_reminder(remind_on: str | None, repeat_days: int | None, today: date) -> str | None:
    """A repeating reminder whose date has passed moves to its next date (today counts as still due)."""
    if not remind_on or not repeat_days:
        return remind_on
    first = date.fromisoformat(remind_on)
    missed = (today - first).days
    return remind_on if missed <= 0 else (first + timedelta(days=-(-missed // repeat_days) * repeat_days)).isoformat()


def _diary_dict(row) -> dict:
    d = dict(row)
    d["remind_on"] = next_reminder(d["remind_on"], d["repeat_days"], date.today())
    return d


def add_diary_entry(user_id: int, entry: dict) -> dict:
    migrate()
    with connect() as conn:
        new_id = conn.execute(
            """INSERT INTO diary_entries (user_id, plot, kind, product, quantity, cost, note, done_on, remind_on, created_at,
                                          repeat_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, entry["plot"], entry["kind"], entry.get("product"), entry.get("quantity"), entry.get("cost"),
             entry.get("note"), entry["done_on"], entry.get("remind_on"), now_iso(), entry.get("repeat_days")),
        ).lastrowid
        row = conn.execute(f"SELECT {', '.join(DIARY_COLUMNS)} FROM diary_entries WHERE id = ?", (new_id,)).fetchone()
    return _diary_dict(row)


def list_diary(user_id: int, plot: str | None = None) -> list[dict]:
    migrate()
    where, args = "user_id = ?", [user_id]
    if plot:
        where += " AND plot = ? COLLATE NOCASE"
        args.append(plot)
    with connect() as conn:
        rows = conn.execute(f"SELECT {', '.join(DIARY_COLUMNS)} FROM diary_entries WHERE {where} ORDER BY done_on DESC, id DESC",
                            args).fetchall()
    return [_diary_dict(r) for r in rows]


def delete_diary_entry(user_id: int, entry_id: int) -> bool:
    with connect() as conn:
        return conn.execute("DELETE FROM diary_entries WHERE id = ? AND user_id = ?", (entry_id, user_id)).rowcount > 0


# ---------------------------------------------------------------- scans

SCAN_LIST_COLUMNS = """s.id, s.uuid, s.user_id, u.username, u.full_name, s.source, s.captured_at, s.received_at,
    s.crop_selected, s.crop_reported, s.inference_status, s.summary_state, s.disease_label, s.disease_state,
    s.disease_confidence, s.pest_label, s.pest_state, s.pest_confidence, s.health_index, s.severity_pct,
    s.model_versions, s.error, s.review_status, s.reviewed_by, r.username AS reviewer_username,
    s.reviewed_at, s.review_comment, s.plot, s.image_path IS NOT NULL AS has_image"""


def _scan_dict(row, include_result: bool = False) -> dict:
    d = {k: row[k] for k in row.keys() if k not in ("result_json", "image_path")}
    d["model_versions"] = json.loads(row["model_versions"]) if row["model_versions"] else {}
    d["has_image"] = bool(row["has_image"])
    if include_result:
        d["result"] = json.loads(row["result_json"]) if row["result_json"] else None
    return d


def find_scan_by_request(user_id: int | None, client_request_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            f"""SELECT {SCAN_LIST_COLUMNS}, s.result_json FROM scans s LEFT JOIN users u ON u.id = s.user_id
                LEFT JOIN users r ON r.id = s.reviewed_by WHERE s.user_id IS ? AND s.client_request_id = ?""",
            (user_id, client_request_id),
        ).fetchone()
        return _scan_dict(row, include_result=True) if row else None


def insert_scan(record: dict) -> int:
    """`record` keys match the scans columns. Returns the new scan id."""
    migrate()
    record = dict(record)
    record.setdefault("uuid", str(uuid.uuid4()))
    record.setdefault("received_at", now_iso())
    for key in ("model_versions", "result_json"):
        if key in record and not isinstance(record[key], (str, type(None))):
            record[key] = json.dumps(record[key])
    cols = ", ".join(record)
    marks = ", ".join("?" for _ in record)
    with connect() as conn:
        return conn.execute(f"INSERT INTO scans ({cols}) VALUES ({marks})", tuple(record.values())).lastrowid


def get_scan(scan_id: int, include_result: bool = True) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            f"""SELECT {SCAN_LIST_COLUMNS}, s.result_json FROM scans s LEFT JOIN users u ON u.id = s.user_id
                LEFT JOIN users r ON r.id = s.reviewed_by WHERE s.id = ?""",
            (scan_id,),
        ).fetchone()
        return _scan_dict(row, include_result) if row else None


def update_scan_result(scan_id: int, result: dict):
    with connect() as conn:
        conn.execute("UPDATE scans SET result_json = ? WHERE id = ?", (json.dumps(result), scan_id))


def sensor_history(device_id: str, since_iso: str, limit: int = 2000) -> list[dict]:
    migrate()
    with connect() as conn:
        rows = conn.execute(
            """SELECT received_at, measured_at, readings_json FROM sensor_readings
               WHERE device_id = ? AND received_at >= ? ORDER BY id DESC LIMIT ?""",
            (device_id, since_iso, limit),
        ).fetchall()
    return [{"received_at": r["received_at"], "measured_at": r["measured_at"], "readings": json.loads(r["readings_json"])}
            for r in reversed(rows)]


def get_scan_image_path(scan_id: int) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT image_path FROM scans WHERE id = ?", (scan_id,)).fetchone()
        return row["image_path"] if row else None


def list_scans(user_id: int | None = None, review_status: str | None = None, include_failed: bool = False,
               source: str | None = None, limit: int = 50) -> list[dict]:
    migrate()
    where, args = [], []
    if user_id is not None:
        where.append("s.user_id = ?")
        args.append(user_id)
    if review_status:
        where.append("s.review_status = ?")
        args.append(review_status)
    if not include_failed:
        where.append("s.inference_status != 'failed'")
    if source:
        where.append("s.source = ?")
        args.append(source)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT {SCAN_LIST_COLUMNS} FROM scans s LEFT JOIN users u ON u.id = s.user_id
                LEFT JOIN users r ON r.id = s.reviewed_by {clause} ORDER BY s.id DESC LIMIT ?""",
            (*args, limit),
        ).fetchall()
        return [_scan_dict(r) for r in rows]


def plots(user_id: int) -> list[dict]:
    """The user's successful scans grouped by plot name, oldest first within each plot."""
    migrate()
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, plot, COALESCE(captured_at, received_at) AS at, severity_pct, health_index,
                      summary_state, disease_label, pest_label
               FROM scans WHERE user_id = ? AND plot IS NOT NULL AND plot != '' AND inference_status != 'failed'
               ORDER BY plot COLLATE NOCASE, at, id""",
            (user_id,),
        ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r["plot"], []).append(
            {"id": r["id"], "captured_at": r["at"], "severity_pct": r["severity_pct"], "health_index": r["health_index"],
             "summary_state": r["summary_state"], "disease_label": r["disease_label"], "pest_label": r["pest_label"]})
    return [{"plot": name, "scans": scans} for name, scans in grouped.items()]


def delete_scan(scan_id: int) -> str | None | bool:
    """Deletes the scan; returns its image path (may be None), or False when it did not exist."""
    with connect() as conn:
        row = conn.execute("SELECT image_path FROM scans WHERE id = ?", (scan_id,)).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
        return row["image_path"]


def review_scan(scan_id: int, admin_id: int, decision: str, comment: str) -> dict | None:
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be 'approved' or 'rejected'")
    with connect() as conn:
        cur = conn.execute(
            """UPDATE scans SET review_status = ?, reviewed_by = ?, reviewed_at = ?, review_comment = ?
               WHERE id = ? AND inference_status != 'failed'""",
            (decision, admin_id, now_iso(), comment.strip(), scan_id),
        )
        if cur.rowcount == 0:
            return None
    return get_scan(scan_id, include_result=False)


def scan_stats() -> dict:
    migrate()
    with connect() as conn:
        q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "successful_scans": q("SELECT COUNT(*) FROM scans WHERE inference_status != 'failed'"),
            "failed_attempts": q("SELECT COUNT(*) FROM scans WHERE inference_status = 'failed'"),
            "pending_review": q("SELECT COUNT(*) FROM scans WHERE review_status = 'pending' AND inference_status != 'failed'"),
            "approved": q("SELECT COUNT(*) FROM scans WHERE review_status = 'approved'"),
            "rejected": q("SELECT COUNT(*) FROM scans WHERE review_status = 'rejected'"),
            "farmers": q("SELECT COUNT(*) FROM users WHERE role = 'farmer'"),
            "admins": q("SELECT COUNT(*) FROM users WHERE role = 'admin'"),
        }


def outbreaks(days: int = 30, exclude_user_id: int | None = None) -> dict:
    """Confirmed detections (disease or pest) in the last `days`, by condition and by farmer location.
    Uncertain, healthy and failed scans are not counted."""
    migrate()
    # received_at is stored as local time with offset, so compare in the same form
    since = (datetime.now().astimezone() - timedelta(days=days)).isoformat(timespec="seconds")
    with connect() as conn:
        rows = conn.execute("""
            SELECT CASE WHEN s.disease_state = 'disease_detected' THEN s.disease_label END AS disease,
                   CASE WHEN s.pest_state = 'pest_detected' THEN s.pest_label END AS pest,
                   COALESCE(NULLIF(TRIM(u.location), ''), 'Unknown') AS location, s.received_at
            FROM scans s JOIN users u ON u.id = s.user_id
            WHERE s.received_at >= ? AND (s.disease_state = 'disease_detected' OR s.pest_state = 'pest_detected')
                  AND s.user_id IS NOT ?
        """, (since, exclude_user_id)).fetchall()
    by_condition: dict = {}
    by_place: dict = {}
    for r in rows:
        for label, kind in ((r["disease"], "disease"), (r["pest"], "pest")):
            if not label:
                continue
            c = by_condition.setdefault(label, {"label": label, "kind": kind, "count": 0, "last_seen": r["received_at"], "places": set()})
            c["count"] += 1
            c["last_seen"] = max(c["last_seen"], r["received_at"])
            c["places"].add(r["location"])
            p = by_place.setdefault((r["location"], label), {"location": r["location"], "label": label, "kind": kind, "count": 0,
                                                             "last_seen": r["received_at"]})
            p["count"] += 1
            p["last_seen"] = max(p["last_seen"], r["received_at"])
    conditions = sorted(({**c, "places": sorted(c["places"])} for c in by_condition.values()), key=lambda c: -c["count"])
    return {"days": days, "confirmed_scans": len(rows), "by_condition": conditions,
            "by_location": sorted(by_place.values(), key=lambda p: (p["location"], -p["count"]))}


# ---------------------------------------------------------------- sensors

def insert_sensor_reading(device_id: str, readings: dict, measured_at: str | None) -> int:
    migrate()
    with connect() as conn:
        return conn.execute(
            "INSERT INTO sensor_readings (device_id, received_at, measured_at, readings_json) VALUES (?, ?, ?, ?)",
            (device_id, now_iso(), measured_at, json.dumps(readings)),
        ).lastrowid


def latest_sensor_readings() -> list[dict]:
    migrate()
    with connect() as conn:
        rows = conn.execute(
            """SELECT r.* FROM sensor_readings r
               JOIN (SELECT device_id, MAX(id) AS id FROM sensor_readings GROUP BY device_id) m ON m.id = r.id
               ORDER BY r.device_id"""
        ).fetchall()
        return [
            {"device_id": r["device_id"], "received_at": r["received_at"], "measured_at": r["measured_at"],
             "readings": json.loads(r["readings_json"])}
            for r in rows
        ]
