import sys
from pathlib import Path

# Add src to python path for imports
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from src.config import DISEASE_MODEL_PATH
from src.disease_detector import load_disease_model, detect_disease
from PIL import Image

def test_disease_model():
    print(f"Loading disease model from {DISEASE_MODEL_PATH}...")
    model = load_disease_model(str(DISEASE_MODEL_PATH))

    test_img_path = Path(__file__).parent.parent / "data" / "tomato-septoria-leaf-spot-closeup.jpg"

    if not test_img_path.exists():
        print(f"Test image not found at {test_img_path}")
        return

    print(f"\nRunning prediction on {test_img_path.name}...")
    import numpy as np
    img = Image.open(str(test_img_path)).convert("RGB")
    rgb_arr = np.array(img)

    result = detect_disease(rgb_arr, model=model)

    print("\n--- PREDICTION RESULT ---")
    print(f"Label: {result.get('label')}")
    print(f"Display Name: {result.get('display_name')}")
    print(f"Confidence: {result.get('confidence')}%")
    print(f"Status: {result.get('status')}")
    if not result.get("ok"):
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    test_disease_model()