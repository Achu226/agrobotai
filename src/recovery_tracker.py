"""
Crop Recovery Timeline & Plot Health Tracker
Monitors plant health changes over multiple scans and calculates recovery index
"""

from __future__ import annotations
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.config import OUTPUTS_DIR

DB_PATH = OUTPUTS_DIR / "scans.db"


def init_recovery_tables():
    """Initialize database tables for plot management and timeline tracking"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table for farm plots/fields
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS farm_plots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plot_name TEXT NOT NULL UNIQUE,
            crop_type TEXT NOT NULL,
            planting_date TEXT,
            field_size_acres REAL DEFAULT 1.0,
            notes TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    # Add plot_id column to scan_history if not present
    cursor.execute("PRAGMA table_info(scan_history)")
    columns = [col[1] for col in cursor.fetchall()]

    if "plot_id" not in columns:
        try:
            cursor.execute("ALTER TABLE scan_history ADD COLUMN plot_id INTEGER REFERENCES farm_plots(id)")
        except Exception:
            pass

    if "severity_pct" not in columns:
        try:
            cursor.execute("ALTER TABLE scan_history ADD COLUMN severity_pct REAL")
        except Exception:
            pass

    if "treatment_applied" not in columns:
        try:
            cursor.execute("ALTER TABLE scan_history ADD COLUMN treatment_applied TEXT")
        except Exception:
            pass

    conn.commit()
    conn.close()


def create_plot(
    plot_name: str,
    crop_type: str,
    planting_date: Optional[str] = None,
    field_size_acres: float = 1.0,
    notes: str = ""
) -> int:
    """Create a new farm plot for tracking"""
    init_recovery_tables()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    now = datetime.now().isoformat(timespec="seconds")
    cursor.execute(
        """
        INSERT OR IGNORE INTO farm_plots (plot_name, crop_type, planting_date, field_size_acres, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (plot_name, crop_type, planting_date, field_size_acres, notes, now)
    )
    plot_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return plot_id


def get_all_plots() -> List[Dict[str, Any]]:
    """Retrieve list of all registered farm plots"""
    init_recovery_tables()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, plot_name, crop_type, planting_date, field_size_acres, notes, created_at FROM farm_plots ORDER BY plot_name ASC")
    rows = cursor.fetchall()
    conn.close()

    plots = []
    for r in rows:
        plots.append({
            "id": r[0],
            "plot_name": r[1],
            "crop_type": r[2],
            "planting_date": r[3],
            "field_size_acres": r[4],
            "notes": r[5],
            "created_at": r[6]
        })
    return plots


def log_plot_scan(
    plot_id: int,
    scan_result: Dict[str, Any],
    treatment_applied: Optional[str] = None
) -> int:
    """Log a scan result linked to a specific farm plot"""
    init_recovery_tables()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    timestamp = scan_result.get("timestamp") or datetime.now().isoformat(timespec="seconds")
    crop = scan_result.get("crop", "Unknown")
    overall = scan_result.get("overall", {})
    overall_score = overall.get("overall_score")
    overall_status = overall.get("overall_status", "UNKNOWN")

    pest = scan_result.get("pest", {})
    disease = scan_result.get("disease", {})
    ndre = scan_result.get("ndre", {})
    cri = scan_result.get("cri", {})
    severity = scan_result.get("severity", {})

    pest_label = pest.get("display_name")
    pest_conf = pest.get("confidence")
    disease_label = disease.get("display_name")
    disease_conf = disease.get("confidence")
    ndre_score = ndre.get("score")
    cri_score = cri.get("score")
    severity_pct = severity.get("affected_percentage", 0.0)

    summary = {
        "timestamp": timestamp,
        "crop": crop,
        "overall": overall,
        "pest": pest,
        "disease": disease,
        "ndre": ndre,
        "cri": cri,
        "severity": severity,
        "treatment_applied": treatment_applied,
        "advice": scan_result.get("advice"),
    }

    cursor.execute(
        """
        INSERT INTO scan_history
        (timestamp, crop, overall_score, overall_status, pest_label, pest_confidence, disease_label, disease_confidence, ndre_score, cri_score, summary_json, plot_id, severity_pct, treatment_applied)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            plot_id,
            severity_pct,
            treatment_applied
        )
    )
    scan_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return scan_id


def get_plot_recovery_timeline(plot_id: int) -> Dict[str, Any]:
    """
    Get full timeline history for a plot and compute recovery metrics
    """
    init_recovery_tables()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get plot info
    cursor.execute("SELECT id, plot_name, crop_type, planting_date, field_size_acres FROM farm_plots WHERE id = ?", (plot_id,))
    plot_row = cursor.fetchone()

    if not plot_row:
        conn.close()
        return {"ok": False, "error": f"Plot ID {plot_id} not found"}

    plot_info = {
        "id": plot_row[0],
        "plot_name": plot_row[1],
        "crop_type": plot_row[2],
        "planting_date": plot_row[3],
        "field_size_acres": plot_row[4]
    }

    # Get scans in chronological order
    cursor.execute(
        """
        SELECT id, timestamp, overall_score, overall_status, pest_label, disease_label, severity_pct, treatment_applied, summary_json
        FROM scan_history
        WHERE plot_id = ?
        ORDER BY timestamp ASC
        """,
        (plot_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {
            "ok": True,
            "plot": plot_info,
            "scans_count": 0,
            "recovery_status": "No scans logged yet",
            "recovery_index": 0.0,
            "timeline": []
        }

    timeline = []
    scores = []
    severities = []

    for r in rows:
        score = r[2] if r[2] is not None else 50.0
        sev = r[6] if r[6] is not None else 0.0
        scores.append(score)
        severities.append(sev)

        timeline.append({
            "scan_id": r[0],
            "timestamp": r[1],
            "overall_score": score,
            "overall_status": r[3],
            "pest": r[4],
            "disease": r[5],
            "severity_percentage": sev,
            "treatment_applied": r[7]
        })

    # Calculate Recovery Metrics
    initial_score = scores[0]
    latest_score = scores[-1]
    initial_sev = severities[0]
    latest_sev = severities[-1]

    score_delta = round(latest_score - initial_score, 1)
    sev_reduction = round(initial_sev - latest_sev, 1)

    # Recovery Index: Positive is improving, negative is deteriorating
    if len(scores) > 1:
        if score_delta > 10 or sev_reduction > 5:
            recovery_status = "RECOVERING (Positive Treatment Response)"
            trend_icon = "📈"
        elif score_delta < -10 or sev_reduction < -5:
            recovery_status = "DETERIORATING (Treatment Ineffective / Disease Spread)"
            trend_icon = "📉"
        else:
            recovery_status = "STABILIZED (No Significant Progression)"
            trend_icon = "➡️"
    else:
        recovery_status = "BASELINE (Initial Scan Logged)"
        trend_icon = "🌱"

    return {
        "ok": True,
        "plot": plot_info,
        "scans_count": len(timeline),
        "initial_health_score": initial_score,
        "latest_health_score": latest_score,
        "score_improvement": score_delta,
        "severity_reduction_pct": sev_reduction,
        "recovery_status": f"{trend_icon} {recovery_status}",
        "timeline": timeline
    }
