"""
Fit confidence calibration (temperature scaling) and image-quality limits from the
project's own validation data, and write them to models/calibration.json.

    .venv\\Scripts\\python.exe scripts\\calibrate_models.py

Temperature scaling (Guo et al., 2017) learns one scalar T on the validation split so that
softmax(logits / T) better matches how often the model is actually right. The test split is
only used to report expected calibration error (ECE) before/after, never for fitting.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import DISEASE_CLASSES, PEST_CLASSES  # noqa: E402
from src.disease_detector import load_disease_model  # noqa: E402
from src.image_quality import measure_image_quality  # noqa: E402
from src.image_utils import load_rgb_array, prepare_model_input  # noqa: E402
from src.pest_detector import load_pest_model  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def split_files(task: str, split: str, classes: dict) -> list[tuple[Path, int]]:
    name_to_idx = {v: k for k, v in classes.items()}
    roots = [ROOT / "data" / task / split]
    if task == "disease":  # added crops (scripts/build_extended_dataset.py) and garden plants (build_garden_dataset.py)
        roots += [ROOT / "data" / "disease_ext" / split, ROOT / "data" / "disease_garden" / split]
    out = []
    for root in roots:
        for class_dir in sorted(root.iterdir()) if root.is_dir() else []:
            if class_dir.is_dir() and class_dir.name in name_to_idx:
                out += [(f, name_to_idx[class_dir.name]) for f in sorted(class_dir.iterdir()) if f.suffix.lower() in EXTS]
    return out


@torch.no_grad()
def collect(wrapper, files):
    logits, labels, quality = [], [], []
    for f, y in files:
        try:
            img = load_rgb_array(f)
        except Exception:
            continue
        quality.append(measure_image_quality(img))
        t = torch.from_numpy(prepare_model_input(img)).permute(0, 3, 1, 2).float().to(wrapper.device)
        logits.append(wrapper.model((t - wrapper.mean) / wrapper.std)[0].float().cpu())
        labels.append(y)
    return torch.stack(logits), torch.tensor(labels), quality


def ece(probs: torch.Tensor, labels: torch.Tensor, bins: int = 15) -> float:
    conf, pred = probs.max(1)
    correct = pred.eq(labels).float()
    edges = torch.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.float().mean().item() * abs(conf[m].mean().item() - correct[m].mean().item())
    return total


def fit_temperature(logits: torch.Tensor, labels: torch.Tensor) -> float:
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=200)

    def closure():
        opt.zero_grad()
        loss = F.cross_entropy(logits / log_t.exp(), labels)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp().item())


def summarize(name, wrapper, classes):
    t0 = time.time()
    val_logits, val_y, val_q = collect(wrapper, split_files(name, "val", classes))
    test_logits, test_y, test_q = collect(wrapper, split_files(name, "test", classes))
    temperature = fit_temperature(val_logits, val_y)
    before = ece(F.softmax(test_logits, 1), test_y)
    after = ece(F.softmax(test_logits / temperature, 1), test_y)
    acc = float(test_logits.argmax(1).eq(test_y).float().mean() * 100)
    print(f"[{name}] T={temperature:.3f}  test acc {acc:.2f}%  ECE {before:.4f} -> {after:.4f}  "
          f"(val n={len(val_y)}, test n={len(test_y)}, {time.time() - t0:.0f}s)")
    return {
        "temperature": round(temperature, 4),
        "test_accuracy_single_view": round(acc, 2),
        "ece_test_before": round(before, 4),
        "ece_test_after": round(after, 4),
        "n_val": len(val_y),
        "n_test": len(test_y),
    }, val_q + test_q


def main():
    disease, dq = summarize("disease", load_disease_model(), DISEASE_CLASSES)
    pest, pq = summarize("pest", load_pest_model(), PEST_CLASSES)

    q = {k: np.array([x[k] for x in dq + pq]) for k in ("sharpness", "brightness")}
    for k, v in q.items():
        print(f"[quality] {k}: p0.5={np.percentile(v, 0.5):.1f} p1={np.percentile(v, 1):.1f} "
              f"p5={np.percentile(v, 5):.1f} median={np.median(v):.1f} p99={np.percentile(v, 99):.1f}")

    out = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "method": "temperature scaling fitted on the validation split; ECE reported on the test split",
        "disease": disease,
        "pest": pest,
        "image_quality": {
            "note": "Limits are set just below the 0.5th percentile of the training-domain validation+test images.",
            "min_sharpness": round(float(np.percentile(q["sharpness"], 0.5)) * 0.8, 2),
            "min_brightness": round(float(np.percentile(q["brightness"], 0.5)) * 0.8, 2),
            "max_brightness": round(min(250.0, float(np.percentile(q["brightness"], 99.5)) * 1.05), 2),
            "n_images": int(len(q["sharpness"])),
        },
    }
    path = ROOT / "models" / "calibration.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
