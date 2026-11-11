from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from src.config import OUTPUTS_DIR

DB_PATH = OUTPUTS_DIR / "scans.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            crop TEXT NOT NULL,
            overall_score REAL,
            overall_status TEXT,
            pest_label TEXT,
            pest_confidence REAL,
            disease_label TEXT,
            disease_confidence REAL,
            ndre_score REAL,
            cri_score REAL,
            summary_json TEXT NOT NULL
        )
    """
    )
    conn.commit()
    conn.close()


def _strip_images(value):
    """Drop embedded base64 images so history rows stay small."""
    if isinstance(value, dict):
        return {k: _strip_images(v) for k, v in value.items() if not str(k).endswith("base64")}
    if isinstance(value, list):
        return [_strip_images(v) for v in value]
    return value


def save_scan(result: dict) -> int:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    timestamp = result.get("timestamp") or datetime.now().isoformat(timespec="seconds")
    crop = result.get("crop", "Unknown")
    overall = result.get("overall", {})
    overall_score = overall.get("overall_score")
    overall_status = overall.get("overall_status", "UNKNOWN")

    pest = result.get("pest", {})
    disease = result.get("disease", {})
    ndre = result.get("ndre", {})
    cri = result.get("cri", {})

    pest_label = pest.get("display_name")
    pest_conf = pest.get("confidence")
    disease_label = disease.get("display_name")
    disease_conf = disease.get("confidence")
    ndre_score = ndre.get("score")
    cri_score = cri.get("score")

    # Store clean serializable summary
    summary = _strip_images({
        "timestamp": timestamp,
        "crop": crop,
        "overall": overall,
        "pest": pest,
        "disease": disease,
        "ndre": ndre,
        "cri": cri,
        "severity": result.get("severity"),
        "advice": result.get("advice"),
    })

    cursor.execute(
        """
        INSERT INTO scan_history 
        (timestamp, crop, overall_score, overall_status, pest_label, pest_confidence, disease_label, disease_confidence, ndre_score, cri_score, summary_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            timestamp,
            crop,
            overall_score,
            overall_status,
            pest_label,
            pest_conf,
            disease_label,
            disease_conf,
            ndre_score,
            cri_score,
            json.dumps(summary),
        ),
    )
    scan_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return scan_id


def get_scan_history(limit: int = 50) -> list[dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, timestamp, crop, overall_score, overall_status, pest_label, pest_confidence, disease_label, disease_confidence, summary_json
        FROM scan_history
        ORDER BY id DESC
        LIMIT ?
    """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()

    history = []
    for r in rows:
        history.append(
            {
                "id": r[0],
                "timestamp": r[1],
                "crop": r[2],
                "overall_score": r[3],
                "overall_status": r[4],
                "pest_label": r[5],
                "pest_confidence": r[6],
                "disease_label": r[7],
                "disease_confidence": r[8],
                "summary": json.loads(r[9]) if r[9] else {},
            }
        )
    return history


def delete_scan(scan_id: int) -> bool:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scan_history WHERE id = ?", (scan_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
