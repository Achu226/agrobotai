"""
Loads the disease and pest models once and records their real status.

A model is reported "ready" only after its weights loaded and a test forward pass on a dummy
image produced the expected number of outputs. Load errors are kept so /models/status can show
them. Versions are derived from the weight file contents (architecture + SHA-256 prefix), so a
retrained model always gets a new version string.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import numpy as np

from src.config import DISEASE_CLASSES, INFERENCE_BACKEND, INFERENCE_TTA, MODELS_DIR, PEST_CLASSES, ROOT_DIR
from src.disease_detector import load_disease_model
from src.pest_detector import load_pest_model

SPECS = {
    "disease": {"file": "disease_model.pt", "loader": load_disease_model, "classes": DISEASE_CLASSES,
                "task": "image_classification", "dataset": "PlantVillage (tomato, potato, bell pepper)"},
    "pest": {"file": "pest_model.pt", "loader": load_pest_model, "classes": PEST_CLASSES,
             "task": "image_classification", "dataset": "IP102 subset (9 insect classes)"},
}

_lock = threading.Lock()
_state: dict[str, dict] = {}


def _sanitize(msg: str) -> str:
    # Never leak absolute paths of the laptop to clients
    return str(msg).replace(str(ROOT_DIR), "<project>").replace(str(ROOT_DIR).replace("\\", "/"), "<project>")


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _calibration() -> dict:
    try:
        return json.loads((MODELS_DIR / "calibration.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _load_one(name: str) -> dict:
    spec = SPECS[name]
    path = MODELS_DIR / spec["file"]
    info = {
        "name": name,
        "file": spec["file"],
        "task": spec["task"],
        "dataset": spec["dataset"],
        "classes": list(spec["classes"].values()),
        "num_classes": len(spec["classes"]),
        "ready": False,
        "error": None,
        "wrapper": None,
    }
    if INFERENCE_BACKEND == "onnx":
        path = MODELS_DIR / "onnx" / f"{name}_model.onnx"
        info["file"] = f"onnx/{path.name}"
    if not path.exists():
        how = "Export it on the laptop with scripts/export_onnx.py" if INFERENCE_BACKEND == "onnx" else "Train it with train_models.py"
        info["error"] = f"Model file models/{info['file']} is missing. {how} or copy it into models/."
        return info
    try:
        started = time.perf_counter()
        if INFERENCE_BACKEND == "onnx":
            from src.onnx_backend import OnnxWrapper

            meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            architecture = meta["architecture"]
            ckpt_classes = meta["classes"]
            source_sha = meta["source_sha256"]  # same version string as the PyTorch model it was exported from
        else:
            import torch

            ckpt = torch.load(str(path), map_location="cpu")
            meta = ckpt if isinstance(ckpt, dict) and "model_state_dict" in ckpt else {}
            architecture = meta.get("model_name", "efficientnet_b0")
            ckpt_classes = meta.get("classes")
            source_sha = _file_sha256(path)
            del ckpt
        if ckpt_classes is not None and list(ckpt_classes) != info["classes"]:
            raise RuntimeError("class list stored in the checkpoint does not match src/config.py — refusing to load")
        wrapper = OnnxWrapper(path) if INFERENCE_BACKEND == "onnx" else spec["loader"]()
        wrapper.use_tta = INFERENCE_TTA
        probs = np.asarray(wrapper.predict(np.zeros((1, 224, 224, 3), dtype=np.float32), use_tta=False))
        if probs.shape[-1] != info["num_classes"]:
            raise RuntimeError(f"model outputs {probs.shape[-1]} classes, expected {info['num_classes']}")
        cal = _calibration().get(name, {})
        info.update({
            "ready": True,
            "wrapper": wrapper,
            "architecture": architecture,
            "version": f"{architecture}-{source_sha[:12]}",
            "backend": INFERENCE_BACKEND,
            "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime)),
            "val_accuracy": meta.get("val_accuracy"),
            "test_accuracy": cal.get("test_accuracy_single_view"),
            "temperature": float(cal.get("temperature", 1.0)),
            "calibrated": "temperature" in cal,
            "device": str(wrapper.device),
            "tta": INFERENCE_TTA,
            "load_seconds": round(time.perf_counter() - started, 2),
        })
    except Exception as exc:  # noqa: BLE001 - every failure is reported, not swallowed
        info["error"] = _sanitize(f"Failed to load {spec['file']}: {exc}")
    return info


def load_all(force: bool = False) -> dict[str, dict]:
    with _lock:
        for name in SPECS:
            if force or name not in _state:
                _state[name] = _load_one(name)
        return _state


def get(name: str) -> dict:
    return load_all()[name]


def wrapper(name: str):
    info = get(name)
    return info["wrapper"] if info["ready"] else None


def set_state(name: str, info: dict):
    """Used by tests to install a fake model or a failure."""
    with _lock:
        _state[name] = info


def reset():
    with _lock:
        _state.clear()


def public_status(name: str, detailed: bool = False) -> dict:
    info = _state.get(name)
    if info is None:
        return {"ready": False, "state": "loading", "error": None}
    out = {
        "ready": info["ready"],
        "state": "ready" if info["ready"] else "unavailable",
        "version": info.get("version"),
        "num_classes": info["num_classes"],
        "error": info["error"],
    }
    if detailed:
        out.update({k: info.get(k) for k in ("file", "backend", "task", "dataset", "classes", "architecture", "trained_at",
                                             "val_accuracy", "test_accuracy", "calibrated", "device", "load_seconds")})
    return out


def runtime_info() -> dict:
    if INFERENCE_BACKEND == "onnx":
        try:
            import onnxruntime

            return {"torch": None, "onnxruntime": onnxruntime.__version__, "cuda_available": False, "gpu": None,
                    "inference_device": "cpu (onnxruntime)"}
        except Exception as exc:  # noqa: BLE001
            return {"torch": None, "cuda_available": False, "gpu": None, "inference_device": "unavailable", "error": str(exc)}
    try:
        import torch

        cuda = torch.cuda.is_available()
        return {
            "torch": torch.__version__,
            "cuda_available": cuda,
            "gpu": torch.cuda.get_device_name(0) if cuda else None,
            "inference_device": "cuda" if cuda else "cpu",
        }
    except Exception as exc:  # noqa: BLE001
        return {"torch": None, "cuda_available": False, "gpu": None, "inference_device": "unavailable", "error": str(exc)}
