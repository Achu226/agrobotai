"""
Runs the full app pipeline (inference_service.analyze, exactly what the phone gets) over a folder of photos.

    python scripts/eval_field_photos.py data/plantdoc/test          # labelled: <folder>/<class>/*.jpg
    python scripts/eval_field_photos.py path/to/my_outdoor_photos   # unlabelled: just lists each result

For a labelled folder it reports, per class, how often the app:
  - gave the correct disease label,
  - gave a wrong confident diagnosis (the dangerous case),
  - said "uncertain" / "not supported" / rejected the photo (safe answers).
`Other_plant` photos should never get a disease diagnosis.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

from src import inference_service, model_registry  # noqa: E402
from src.image_utils import load_rgb_array  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SAFE_STATES = {"uncertain", "unsupported_crop"}


def outcome(truth: str | None, result: dict | None, error_code: str | None) -> str:
    """Disease outcome; a pest false alarm is counted separately (these photos show leaves, not insects)."""
    if error_code:
        return "rejected_photo"  # poor quality / no leaf: the farmer is asked to retake
    d = result["disease"]
    if truth is None:
        return f"{d['state']}:{d.get('label')}"
    if d["state"] not in ("disease_detected", "no_disease_detected"):
        return "safe_unsure"  # uncertain / not a supported crop / unavailable
    if truth == "Other_plant":
        return "WRONG_diagnosed_other_plant"
    return "correct" if d.get("label") == truth else "WRONG_label"


def main(folder: Path) -> int:
    model_registry.load_all()
    files = sorted(f for f in folder.rglob("*") if f.suffix.lower() in EXTS)
    labelled = any(f.parent != folder for f in files)
    per_class: dict[str, Counter] = defaultdict(Counter)
    for f in files:
        truth = f.parent.name if labelled else None
        try:
            res, code = inference_service.analyze(load_rgb_array(f), include_advice=False), None
        except inference_service.InferenceError as exc:
            res, code = None, exc.code
        o = outcome(truth, res, code)
        per_class[truth or "all"][o] += 1
        if res and res["pest"]["state"] == "pest_detected":
            per_class[truth or "all"]["PEST_false_alarm"] += 1
        if not labelled:
            d = (res or {}).get("disease", {})
            print(f"{f.name}: {o} | {d.get('display_name')} {d.get('calibrated_confidence')}% | {code or ''}")
    total = Counter()
    for cls, c in sorted(per_class.items()):
        n = sum(c.values())
        total.update(c)
        print(f"{cls:45s} n={n:3d} " + " ".join(f"{k}={v}" for k, v in sorted(c.items())))
    n = sum(v for k, v in total.items() if k != "PEST_false_alarm")
    print(json.dumps({"photos": n, **{k: f"{100 * v / n:.1f}%" for k, v in sorted(total.items())}}))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
