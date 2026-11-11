import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from src.config import DISEASE_MODEL_PATH, PEST_MODEL_PATH, ROOT_DIR as ROOT
from src.disease_detector import load_disease_model, detect_disease
from src.pest_detector import load_pest_model, detect_pest

def run_self_check():
    print("--- MODEL SELF-CHECK IN PROGRESS ---")

    # 1. Load Models
    print(f"\n1. Loading Disease Model from {DISEASE_MODEL_PATH.name}...")
    try:
        disease_model = load_disease_model(str(DISEASE_MODEL_PATH))
        print("   [OK] Disease model loaded successfully.")
    except Exception as e:
        print(f"   [ERROR] Failed to load disease model: {e}")
        return

    print(f"2. Loading Pest Model from {PEST_MODEL_PATH.name}...")
    try:
        pest_model = load_pest_model(str(PEST_MODEL_PATH))
        print("   [OK] Pest model loaded successfully.")
    except Exception as e:
        print(f"   [ERROR] Failed to load pest model: {e}")
        return

    # test images and their true labels
    tests = [
        {
            "type": "disease",
            "path": str(ROOT / r"data\disease\PlantVillage\Pepper__bell___Bacterial_spot\0022d6b7-d47c-4ee2-ae9a-392a53f48647___JR_B.Spot 8964.JPG"),
            "true_label": "Pepper__bell___Bacterial_spot"
        },
        {
            "type": "disease",
            "path": str(ROOT / r"data\disease\PlantVillage\Tomato_healthy\000146ff-92a4-4db6-90ad-8fce2ae4fddd___GH_HL Leaf 259.1.JPG"),
            "true_label": "Tomato_healthy"
        },
        {
            "type": "pest",
            "path": str(ROOT / r"data\pest\test\aphids\jpg_10 - Copy.jpg"),
            "true_label": "aphids"
        },
        {
            "type": "pest",
            "path": str(ROOT / r"data\pest\test\armyworm\jpg_0.jpg"),
            "true_label": "armyworm"
        }
    ]

    print("\n--- INFERENCE TESTS ---")
    for idx, t in enumerate(tests):
        img_path = Path(t["path"])
        print(f"\nTest {idx+1}: {t['type'].upper()} MODEL")
        print(f"Input: {img_path.name}")
        print(f"Ground Truth expected: {t['true_label']}")

        if not img_path.exists():
            print("   [ERROR] Image file missing.")
            continue

        try:
            img = Image.open(str(img_path)).convert("RGB")
            rgb_arr = np.array(img)

            if t["type"] == "disease":
                res = detect_disease(rgb_arr, model=disease_model)
            else:
                res = detect_pest(rgb_arr, model=pest_model)

            if not res.get("ok"):
                print(f"   [FAILED] {res.get('error')}")
            else:
                predicted = res.get("label")
                conf = res.get("confidence")
                match = "[MATCH]" if str(predicted).lower().strip() == t["true_label"].lower().strip() else f"[MISMATCH - predicted {predicted}]"
                print(f"   Prediction: {predicted} (Confidence: {conf}%) {match}")
                print(f"   Display:    {res.get('display_name')}")
                print(f"   Status:     {res.get('status')}")

                # Check for open set rejection logic working
                if res.get("is_open_set"):
                    print(f"   [NOTE] Open-set rejection flagged this image.")

        except Exception as e:
            print(f"   [ERROR] Inference threw exception: {e}")

if __name__ == "__main__":
    run_self_check()