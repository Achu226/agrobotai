import json
import sqlite3

from src import config, store


def test_migration_keeps_legacy_web_history(tmp_path, monkeypatch):
    db = tmp_path / "legacy.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE scan_history (id INTEGER PRIMARY KEY, timestamp TEXT, crop TEXT, overall_score REAL,
        overall_status TEXT, pest_label TEXT, pest_confidence REAL, disease_label TEXT, disease_confidence REAL,
        ndre_score REAL, cri_score REAL, summary_json TEXT)""")
    conn.execute("INSERT INTO scan_history VALUES (1, '2026-10-10T10:00:00', 'Potato', 61.0, 'MILD', NULL, NULL, "
                 "'Potato Late Blight', 93.1, 70, 60, ?)", (json.dumps({"crop": "Potato"}),))
    conn.commit()
    conn.close()

    store.migrate()
    store.migrate()  # idempotent
    scans = store.list_scans()
    assert len(scans) == 1
    assert scans[0]["disease_label"] == "Potato Late Blight" and scans[0]["source"] == "web"
    assert store.get_scan(scans[0]["id"])["result"]["legacy"] is True


def test_review_refuses_failed_attempts():
    failed = store.insert_scan({"inference_status": "failed", "error": "boom"})
    assert store.review_scan(failed, admin_id=1, decision="approved", comment="") is None
