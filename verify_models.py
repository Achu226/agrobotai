"""
Model Verification Script
Reports what is actually inside the trained checkpoints and, with --eval,
measures real accuracy on the held-out test split (data/<task>/test).

    python verify_models.py          # checkpoint info + dataset counts
    python verify_models.py --eval   # also evaluate on the test split
"""
import sys
from pathlib import Path

import numpy as np
import torch

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.config import DISEASE_CLASSES, PEST_CLASSES  # noqa: E402
from src.disease_detector import load_disease_model  # noqa: E402
from src.image_utils import load_rgb_array, prepare_model_input  # noqa: E402
from src.pest_detector import load_pest_model  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

TASKS = {
    "pest": {"path": ROOT / "models" / "pest_model.pt", "loader": load_pest_model, "classes": PEST_CLASSES},
    "disease": {"path": ROOT / "models" / "disease_model.pt", "loader": load_disease_model, "classes": DISEASE_CLASSES},
}


def count_images(folder: Path) -> int:
    if not folder.exists():
        return 0
    return sum(1 for f in folder.rglob("*") if f.suffix.lower() in IMAGE_EXTS)


def checkpoint_info(path: Path) -> dict:
    ckpt = torch.load(str(path), map_location="cpu")
    if isinstance(ckpt, dict) and "model_state_dict" in ckpt:
        state = ckpt["model_state_dict"]
        return {
            "architecture": ckpt.get("model_name", "unknown"),
            "val_accuracy": ckpt.get("val_accuracy"),
            "num_classes": len(ckpt.get("classes", [])),
            "params_m": sum(t.numel() for t in state.values()) / 1e6,
        }
    return {"architecture": "efficientnet_b0 (legacy state_dict)", "val_accuracy": None,
            "num_classes": None, "params_m": sum(t.numel() for t in ckpt.values()) / 1e6}


def evaluate(wrapper, test_dir: Path, classes: dict) -> tuple[float, int, dict]:
    name_to_idx = {v: k for k, v in classes.items()}
    correct = total = 0
    per_class = {}
    for class_dir in sorted(p for p in test_dir.iterdir() if p.is_dir()):
        if class_dir.name not in name_to_idx:
            continue
        target = name_to_idx[class_dir.name]
        c_correct = c_total = 0
        for f in class_dir.iterdir():
            if f.suffix.lower() not in IMAGE_EXTS:
                continue
            try:
                batch = prepare_model_input(load_rgb_array(f))
            except Exception:
                continue
            # Plain single-view inference so the number reflects the model itself (no TTA)
            probs = wrapper.predict(batch, use_tta=False)[0]
            c_correct += int(np.argmax(probs) == target)
            c_total += 1
        per_class[class_dir.name] = (c_correct, c_total)
        correct += c_correct
        total += c_total
    return (100.0 * correct / total if total else 0.0), total, per_class


def main():
    run_eval = "--eval" in sys.argv
    print("=" * 64)
    print("HORTICBOTAI Model Verification")
    print("=" * 64)
    print(f"Torch {torch.__version__} | Device: {'cuda (' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'cpu'}")

    all_ok = True
    for task, cfg in TASKS.items():
        print(f"\n[{task.upper()} MODEL]")
        path = cfg["path"]
        if not path.exists():
            print(f"   ❌ Missing: {path}")
            all_ok = False
            continue
        info = checkpoint_info(path)
        print(f"   File: {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)")
        print(f"   Architecture: {info['architecture']} ({info['params_m']:.1f}M params)")
        print(f"   Classes: {info['num_classes'] or 'n/a'} (config expects {len(cfg['classes'])})")
        val = info["val_accuracy"]
        print(f"   Best validation accuracy (saved at training time): {f'{val:.2f}%' if val is not None else 'not recorded'}")

        data_dir = ROOT / "data" / task
        counts = {split: count_images(data_dir / split) for split in ("train", "val", "test")}
        print(f"   Dataset images: train={counts['train']:,} val={counts['val']:,} test={counts['test']:,}")

        try:
            wrapper = cfg["loader"]()
            print(f"   ✅ Loads correctly on {wrapper.device}")
        except Exception as exc:
            print(f"   ❌ Load failed: {exc}")
            all_ok = False
            continue

        if run_eval:
            test_dir = data_dir / "test"
            if not test_dir.exists():
                print("   ⚠️  No test split found, skipping evaluation")
                continue
            acc, total, per_class = evaluate(wrapper, test_dir, cfg["classes"])
            print(f"   🎯 Test accuracy: {acc:.2f}% on {total:,} held-out images")
            for cname, (c, t) in per_class.items():
                if t:
                    print(f"      {cname:<45} {100.0 * c / t:6.2f}%  ({c}/{t})")

    print("\n" + "=" * 64)
    print("Result:", "all models present and loadable" if all_ok else "problems found (see above)")
    if not run_eval:
        print("Tip: run with --eval to measure real test-set accuracy.")
    print("=" * 64)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
