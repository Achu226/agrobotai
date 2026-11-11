"""
Export the trained disease and pest models to ONNX for the Raspberry Pi (run on the laptop).

    .venv\\Scripts\\python.exe scripts\\export_onnx.py

Writes models/onnx/<name>_model.onnx + <name>_model.json (classes, architecture, accuracy, source
SHA-256), then checks the ONNX output against PyTorch on real test photos and refuses to keep an
export whose predictions differ.
"""
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import DISEASE_CLASSES, MODELS_DIR, PEST_CLASSES  # noqa: E402
from src.disease_detector import load_disease_model  # noqa: E402
from src.image_utils import load_rgb_array, prepare_model_input  # noqa: E402
from src.onnx_backend import OnnxWrapper  # noqa: E402
from src.pest_detector import load_pest_model  # noqa: E402

OUT = MODELS_DIR / "onnx"
JOBS = {
    "disease": (load_disease_model, DISEASE_CLASSES, ROOT / "data/disease/test"),
    "pest": (load_pest_model, PEST_CLASSES, ROOT / "data/pest/test"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sample_photos(folder: Path, n: int = 24) -> list[Path]:
    files = [f for f in folder.rglob("*") if f.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    random.Random(0).shuffle(files)
    return files[:n]


def export(name: str) -> dict:
    loader, classes, test_dir = JOBS[name]
    src = MODELS_DIR / f"{name}_model.pt"
    ckpt = torch.load(str(src), map_location="cpu", weights_only=False)
    wrapper = loader()
    model = wrapper.model.to("cpu").eval()
    wrapper.device, wrapper.mean, wrapper.std = torch.device("cpu"), wrapper.mean.cpu(), wrapper.std.cpu()

    OUT.mkdir(parents=True, exist_ok=True)
    onnx_path = OUT / f"{name}_model.onnx"
    torch.onnx.export(model, torch.zeros(1, 3, 224, 224), str(onnx_path), input_names=["image"], output_names=["logits"],
                      dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}}, opset_version=17, dynamo=False)

    # Verify on real photos: same top-1 class and near-identical probabilities (single view and TTA)
    onnx_wrapper = OnnxWrapper(onnx_path)
    photos = sample_photos(test_dir)
    max_diff, agree, timings = 0.0, 0, []
    for p in photos:
        x = prepare_model_input(load_rgb_array(p))
        for tta in (False, True):
            ref = wrapper.predict(x, use_tta=tta)
            t = time.perf_counter()
            got = onnx_wrapper.predict(x, use_tta=tta)
            timings.append(time.perf_counter() - t)
            max_diff = max(max_diff, float(np.abs(ref - got).max()))
            agree += int(ref.argmax() == got.argmax())
    checks = 2 * len(photos)
    if not photos or agree != checks or max_diff > 1e-3:
        onnx_path.unlink(missing_ok=True)
        raise SystemExit(f"{name}: ONNX output differs from PyTorch (top-1 agree {agree}/{checks}, max diff {max_diff:.2e}) - export removed")

    meta = {
        "name": name,
        "architecture": ckpt.get("model_name", "efficientnet_b0"),
        "classes": list(classes.values()),
        "input": {"shape": [None, 3, 224, 224], "layout": "NCHW", "range": "0-1 then ImageNet mean/std"},
        "val_accuracy": ckpt.get("val_accuracy"),
        "source_file": src.name,
        "source_sha256": sha256(src),
        "onnx_sha256": sha256(onnx_path),
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "verified": {"photos": len(photos), "top1_agreement": f"{agree}/{checks}", "max_prob_diff": max_diff},
    }
    assert meta["classes"] == list(ckpt.get("classes", meta["classes"])), "checkpoint classes differ from src/config.py"
    (OUT / f"{name}_model.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[OK] {name}: {onnx_path.relative_to(ROOT)} ({onnx_path.stat().st_size / 1e6:.0f} MB), "
          f"top-1 agree {agree}/{checks}, max prob diff {max_diff:.1e}, laptop CPU {1000 * np.median(timings):.0f} ms/call")
    return meta


if __name__ == "__main__":
    for job in sys.argv[1:] or JOBS:
        export(job)
