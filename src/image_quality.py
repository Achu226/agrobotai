"""
Image-quality checks run before any model inference.

Limits come from models/calibration.json (fitted on this project's own validation/test images
by scripts/calibrate_models.py). Without that file, conservative defaults are used.
These checks catch blurry, dark and over-exposed photos; they cannot prove a photo shows a
supported leaf — that is handled separately (foliage fraction + model uncertainty).
"""
from __future__ import annotations

import json
from functools import lru_cache

import cv2
import numpy as np

from src.config import MODELS_DIR

DEFAULT_LIMITS = {"min_sharpness": 15.0, "min_brightness": 35.0, "max_brightness": 235.0}
MIN_SIDE_PX = 64
MAX_SIDE_PX = 12000


@lru_cache(maxsize=1)
def quality_limits() -> dict:
    try:
        data = json.loads((MODELS_DIR / "calibration.json").read_text(encoding="utf-8"))
        limits = data.get("image_quality") or {}
        return {k: float(limits.get(k, v)) for k, v in DEFAULT_LIMITS.items()} | {"source": "calibration.json"}
    except (OSError, ValueError):
        return dict(DEFAULT_LIMITS) | {"source": "defaults"}


def measure_image_quality(image_rgb: np.ndarray) -> dict:
    """Sharpness = variance of the Laplacian on a 512px-wide grayscale copy; brightness = mean luma."""
    img = image_rgb.astype(np.uint8)
    h, w = img.shape[:2]
    if w > 512:
        img = cv2.resize(img, (512, max(1, int(h * 512 / w))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return {
        "sharpness": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "brightness": float(gray.mean()),
        "width": int(w),
        "height": int(h),
    }


def check_image_quality(image_rgb: np.ndarray) -> dict:
    """Returns {"ok": bool, "issues": [...], "metrics": {...}, "limits": {...}}."""
    m = measure_image_quality(image_rgb)
    lim = quality_limits()
    issues = []
    if min(m["width"], m["height"]) < MIN_SIDE_PX:
        issues.append({"code": "too_small", "message": f"Image is too small ({m['width']}x{m['height']}). Use at least {MIN_SIDE_PX}px per side."})
    if max(m["width"], m["height"]) > MAX_SIDE_PX:
        issues.append({"code": "too_large", "message": f"Image dimensions are too large ({m['width']}x{m['height']})."})
    if m["brightness"] < lim["min_brightness"]:
        issues.append({"code": "too_dark", "message": "Photo is too dark. Move to better light or turn on the flash and retake."})
    if m["brightness"] > lim["max_brightness"]:
        issues.append({"code": "overexposed", "message": "Photo is over-exposed. Avoid direct glare and retake."})
    if m["sharpness"] < lim["min_sharpness"]:
        issues.append({"code": "blurry", "message": "Photo is blurry. Hold the phone steady, tap to focus on the leaf and retake."})
    return {
        "ok": not issues,
        "issues": issues,
        "metrics": {k: round(v, 2) if isinstance(v, float) else v for k, v in m.items()},
        "limits": lim,
    }
