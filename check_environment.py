from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def check(name: str, fn):
    try:
        fn()
        print(f"[OK] {name}")
        return True
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def main():
    print("Python:", sys.version)
    print("Project:", ROOT)
    ok = True

    def import_core():
        import numpy  # noqa: F401
        import PIL  # noqa: F401
        import cv2  # noqa: F401
        import streamlit  # noqa: F401
        from dotenv import load_dotenv  # noqa: F401

    ok &= check("core packages", import_core)

    def import_src():
        from src.config import PEST_CLASSES, DISEASE_CLASSES  # noqa: F401
        from src.pipeline import analyze_image  # noqa: F401
        from src.health_engine import combine_health  # noqa: F401

    ok &= check("project modules", import_src)

    def check_tf():
        import tensorflow as tf  # noqa: F401
        from tensorflow.keras.models import load_model  # noqa: F401

        print("    TensorFlow:", tf.__version__)

    tf_ok = check("tensorflow", check_tf)
    if not tf_ok:
        print("    Official TensorFlow wheels need Python 3.10-3.12, not 3.13/3.14.")
        print("    Install Python 3.11, recreate .venv, then: pip install tensorflow==2.15.1")
        print("    NDRE/CRI/health/advisor still run without TensorFlow; pest/disease will be unavailable.")
        ok = False

    def check_models():
        from src.config import MODELS_DIR

        pest_ok = (MODELS_DIR / "pest_model.pt").exists() or (MODELS_DIR / "pest_model.h5").exists()
        disease_ok = (MODELS_DIR / "disease_model.pt").exists() or (MODELS_DIR / "disease_model.h5").exists()

        if not pest_ok:
            raise FileNotFoundError("Missing pest_model.pt or pest_model.h5 in models/")
        if not disease_ok:
            raise FileNotFoundError("Missing disease_model.pt or disease_model.h5 in models/")

    models_ok = check("trained model files", check_models)
    if not models_ok:
        print("    Place pest_model.h5 and disease_model.h5 inside models/")
        ok = False

    def check_env():
        from src.config import OPENAI_API_KEY

        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is empty. Copy .env.example to .env")

    env_ok = check("OpenAI API key", check_env)
    if not env_ok:
        print("    App will still run; farmer advice will use the local fallback.")

    print("")
    if ok:
        print("Environment looks ready. Run: streamlit run app.py")
        return 0
    print("Environment has missing pieces. The app can still start, but some modules may be unavailable.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
