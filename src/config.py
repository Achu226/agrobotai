from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env", override=True)
except ImportError:
    pass

MODELS_DIR = ROOT_DIR / "models"
# "torch" on the laptop (GPU); "onnx" on devices without PyTorch such as the Raspberry Pi (models/onnx/*.onnx).
# Empty = torch when it is installed, otherwise onnx.
INFERENCE_BACKEND = os.getenv("AGROBOT_BACKEND", "").strip().lower()
if INFERENCE_BACKEND not in ("torch", "onnx"):
    import importlib.util

    INFERENCE_BACKEND = "torch" if importlib.util.find_spec("torch") else "onnx"
OUTPUTS_DIR = ROOT_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

PEST_MODEL_PATH = Path(os.getenv("PEST_MODEL_PATH", MODELS_DIR / "pest_model.h5"))
DISEASE_MODEL_PATH = Path(os.getenv("DISEASE_MODEL_PATH", MODELS_DIR / "disease_model.h5"))

IMAGE_SIZE = (224, 224)
SUPPORTED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

CROPS = (
    "Tomato",
    "Potato",
    "Bell Pepper",
    "Green Chilli",
    "Brinjal",
    "Corn (Maize)",
    "Rice (Paddy)",
    "Wheat",
    "Cotton",
    "Sugarcane",
    "Soybean",
    "Banana",
    "Apple",
    "Grape",
    "Orange",
    "Peach",
    "Cherry",
    "Strawberry",
    "Squash",
    "Blueberry",
    "Raspberry",
    "Rose",
    "Money Plant",
    "Hibiscus",
    "Marigold",
)

# Notebook inference used keras.utils.img_to_array(img) / 255 only.
# Training also passed vgg16.preprocess_input, but get_img_array did not.
PREPROCESS_MODE = os.getenv("PREPROCESS_MODE", "notebook")

LOW_CONFIDENCE_THRESHOLD = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.45"))
HIGH_CONFIDENCE_THRESHOLD = float(os.getenv("HIGH_CONFIDENCE_THRESHOLD", "0.75"))

# Open-Set Insect Pest Rejection Thresholds
PEST_CONFIDENCE_THRESHOLD = float(os.getenv("PEST_CONFIDENCE_THRESHOLD", "0.72"))
PEST_MARGIN_THRESHOLD = float(os.getenv("PEST_MARGIN_THRESHOLD", "0.25"))
PEST_EVIDENCE_THRESHOLD = float(os.getenv("PEST_EVIDENCE_THRESHOLD", "0.35"))
PEST_UNCERTAIN_LOWER_THRESHOLD = float(os.getenv("PEST_UNCERTAIN_LOWER_THRESHOLD", "0.50"))

# Cross-check with the disease model. The pest CNN was trained only on insect photos, so on a
# plain leaf close-up it still picks some pest. If the disease model is this sure the image is
# an ordinary leaf, a pest is only confirmed at PEST_STRONG_CONFIDENCE_THRESHOLD or above.
# Uses the disease model's single-view (no TTA) top probability. Measured on held-out data
# (321 pest photos / 400 pest-free leaves): pest recall 96.6%, false alarms on clean leaves 2.0%
# (previous evidence-based gate: 91.6% / 33.8%).
PEST_LEAF_SCENE_THRESHOLD = float(os.getenv("PEST_LEAF_SCENE_THRESHOLD", "0.97"))
PEST_STRONG_CONFIDENCE_THRESHOLD = float(os.getenv("PEST_STRONG_CONFIDENCE_THRESHOLD", "0.97"))

HEALTH_WEIGHTS = {
    "pest": float(os.getenv("WEIGHT_PEST", "0.30")),
    "disease": float(os.getenv("WEIGHT_DISEASE", "0.35")),
    "ndre": float(os.getenv("WEIGHT_NDRE", "0.20")),
    "cri": float(os.getenv("WEIGHT_CRI", "0.15")),
}

HEALTH_STATUS_THRESHOLDS = {
    "healthy": float(os.getenv("STATUS_HEALTHY", "80")),
    "mild": float(os.getenv("STATUS_MILD", "60")),
    "moderate": float(os.getenv("STATUS_MODERATE", "40")),
}

NDRE_THRESHOLDS = {
    "low": 0.35,
    "moderate": 0.65,
}

CRI_THRESHOLDS = {
    "low": 0.35,
    "moderate": 0.65,
}

PEST_CLASSES = {
    0: "aphids",
    1: "armyworm",
    2: "beetle",
    3: "bollworm",
    4: "grasshopper",
    5: "mites",
    6: "mosquito",
    7: "sawfly",
    8: "stem_borer",
    # Leaves without insects (scripts/build_no_pest_class.py): lets the model say "no pest" itself
    9: "no_pest",
}

PEST_DISPLAY_NAMES = {
    "aphids": "Aphids",
    "armyworm": "Armyworm",
    "beetle": "Beetle",
    "bollworm": "Bollworm",
    "grasshopper": "Grasshopper",
    "mites": "Mites",
    "mosquito": "Mosquito",
    "sawfly": "Sawfly",
    "stem_borer": "Stem Borer",
    "no_pest": "No pest",
}

PEST_SEVERITY = {
    "aphids": 0.70,
    "armyworm": 0.90,
    "beetle": 0.60,
    "bollworm": 0.85,
    "grasshopper": 0.55,
    "mites": 0.75,
    "mosquito": 0.40,
    "sawfly": 0.70,
    "stem_borer": 0.90,
    "no_pest": 0.0,
}

_BASE_DISEASE_CLASSES = [
    "Pepper__bell___Bacterial_spot", "Pepper__bell___healthy", "Potato___Early_blight", "Potato___Late_blight",
    "Potato___healthy", "Tomato_Bacterial_spot", "Tomato_Early_blight", "Tomato_Late_blight", "Tomato_Leaf_Mold",
    "Tomato_Septoria_leaf_spot", "Tomato_Spider_mites_Two_spotted_spider_mite", "Tomato__Target_Spot",
    "Tomato__Tomato_YellowLeaf__Curl_Virus", "Tomato__Tomato_mosaic_virus", "Tomato_healthy",
    # Field model (scripts/train_field_model.py): any plant the model does not know, so it is never misdiagnosed
    "Other_plant",
]
# Added by scripts/train_extended_model.py (rice, banana, 11 PlantVillage crops), in output order
_EXTENDED_DISEASE_CLASSES = [
    "Apple_black_rot", "Apple_cedar_rust", "Apple_healthy", "Apple_scab", "Banana_cordana", "Banana_healthy",
    "Banana_pestalotiopsis", "Banana_sigatoka", "Blueberry_healthy", "Cherry_healthy", "Cherry_powdery_mildew",
    "Grape_black_rot", "Grape_esca", "Grape_healthy", "Grape_leaf_blight", "Maize_common_rust", "Maize_gray_leaf_spot",
    "Maize_healthy", "Maize_northern_leaf_blight", "Orange_citrus_greening", "Peach_bacterial_spot", "Peach_healthy",
    "Raspberry_healthy", "Rice_bacterial_blight", "Rice_blast", "Rice_brown_spot", "Rice_healthy", "Rice_tungro",
    "Soybean_healthy", "Squash_powdery_mildew", "Strawberry_healthy", "Strawberry_leaf_scorch",
]

# Home-garden plants (scripts/build_garden_dataset.py), in output order after the classes above
_GARDEN_DISEASE_CLASSES = [
    "Hibiscus_bacterial_leaf_spot", "Hibiscus_healthy", "Hibiscus_nutrient_deficiency", "Marigold_alternaria_blight",
    "Marigold_healthy", "Marigold_pest_damage", "Money_plant_bacterial_wilt", "Money_plant_healthy",
    "Money_plant_manganese_toxicity", "Rose_dry_leaf", "Rose_healthy", "Rose_insect_damage", "Rose_leaf_spot",
    "Rose_nutrient_deficiency",
]


def _deployed_disease_classes() -> list[str]:
    """Class order of the deployed disease model, from models/disease_classes.json (written with the model);
    the 16-class list when the file is missing or unknown, so an old model keeps working."""
    import json

    try:
        names = json.loads((MODELS_DIR / "disease_classes.json").read_text(encoding="utf-8"))["classes"]
    except (OSError, ValueError, KeyError):
        return _BASE_DISEASE_CLASSES
    known = set(_BASE_DISEASE_CLASSES) | set(_EXTENDED_DISEASE_CLASSES) | set(_GARDEN_DISEASE_CLASSES)
    return names if names[: len(_BASE_DISEASE_CLASSES)] == _BASE_DISEASE_CLASSES and set(names) <= known else _BASE_DISEASE_CLASSES


DISEASE_CLASSES = dict(enumerate(_deployed_disease_classes()))

OTHER_PLANT_CLASS = "Other_plant"

HEALTHY_DISEASE_CLASSES = {
    "Pepper__bell___healthy",
    "Potato___healthy",
    "Tomato_healthy",
} | {c for c in _EXTENDED_DISEASE_CLASSES + _GARDEN_DISEASE_CLASSES if c.endswith("_healthy")}

DISEASE_DISPLAY_NAMES = {
    "Pepper__bell___Bacterial_spot": "Pepper Bell Bacterial Spot",
    "Pepper__bell___healthy": "Pepper Bell Healthy",
    "Potato___Early_blight": "Potato Early Blight",
    "Potato___Late_blight": "Potato Late Blight",
    "Potato___healthy": "Potato Healthy",
    "Tomato_Bacterial_spot": "Tomato Bacterial Spot",
    "Tomato_Early_blight": "Tomato Early Blight",
    "Tomato_Late_blight": "Tomato Late Blight",
    "Tomato_Leaf_Mold": "Tomato Leaf Mold",
    "Tomato_Septoria_leaf_spot": "Tomato Septoria Leaf Spot",
    "Tomato_Spider_mites_Two_spotted_spider_mite": "Tomato Spider Mites (Two-Spotted)",
    "Tomato__Target_Spot": "Tomato Target Spot",
    "Tomato__Tomato_YellowLeaf__Curl_Virus": "Tomato Yellow Leaf Curl Virus",
    "Tomato__Tomato_mosaic_virus": "Tomato Mosaic Virus",
    "Tomato_healthy": "Tomato Healthy",
    "Other_plant": "Not tomato, potato or bell pepper" if len(DISEASE_CLASSES) <= 16 else "Not a supported crop",
    "Rice_bacterial_blight": "Rice Bacterial Leaf Blight",
    "Rice_blast": "Rice Blast",
    "Rice_brown_spot": "Rice Brown Spot",
    "Rice_tungro": "Rice Tungro Virus",
    "Rice_healthy": "Rice Healthy",
    "Banana_cordana": "Banana Cordana Leaf Spot",
    "Banana_pestalotiopsis": "Banana Pestalotiopsis Leaf Spot",
    "Banana_sigatoka": "Banana Sigatoka",
    "Banana_healthy": "Banana Healthy",
    "Apple_scab": "Apple Scab",
    "Apple_black_rot": "Apple Black Rot",
    "Apple_cedar_rust": "Apple Cedar Rust",
    "Apple_healthy": "Apple Healthy",
    "Blueberry_healthy": "Blueberry Healthy",
    "Cherry_powdery_mildew": "Cherry Powdery Mildew",
    "Cherry_healthy": "Cherry Healthy",
    "Maize_gray_leaf_spot": "Maize Gray Leaf Spot",
    "Maize_common_rust": "Maize Common Rust",
    "Maize_northern_leaf_blight": "Maize Northern Leaf Blight",
    "Maize_healthy": "Maize Healthy",
    "Grape_black_rot": "Grape Black Rot",
    "Grape_esca": "Grape Esca (Black Measles)",
    "Grape_leaf_blight": "Grape Leaf Blight",
    "Grape_healthy": "Grape Healthy",
    "Orange_citrus_greening": "Citrus Greening (HLB)",
    "Peach_bacterial_spot": "Peach Bacterial Spot",
    "Peach_healthy": "Peach Healthy",
    "Raspberry_healthy": "Raspberry Healthy",
    "Soybean_healthy": "Soybean Healthy",
    "Squash_powdery_mildew": "Squash Powdery Mildew",
    "Strawberry_leaf_scorch": "Strawberry Leaf Scorch",
    "Strawberry_healthy": "Strawberry Healthy",
    "Rose_leaf_spot": "Rose Leaf Spot (black spot)",
    "Rose_insect_damage": "Rose Insect Damage",
    "Rose_dry_leaf": "Rose Dry Leaves (water or heat stress)",
    "Rose_nutrient_deficiency": "Rose Nutrient Deficiency (yellow leaves)",
    "Rose_healthy": "Rose Healthy",
    "Money_plant_bacterial_wilt": "Money Plant Bacterial Wilt",
    "Money_plant_manganese_toxicity": "Money Plant Manganese Toxicity",
    "Money_plant_healthy": "Money Plant Healthy",
    "Hibiscus_bacterial_leaf_spot": "Hibiscus Bacterial Leaf Spot",
    "Hibiscus_nutrient_deficiency": "Hibiscus Nutrient Deficiency (yellow leaves)",
    "Hibiscus_healthy": "Hibiscus Healthy",
    "Marigold_alternaria_blight": "Marigold Alternaria Leaf Blight",
    "Marigold_pest_damage": "Marigold Pest Damage",
    "Marigold_healthy": "Marigold Healthy",
}

DISEASE_SEVERITY = {
    "Pepper__bell___Bacterial_spot": 0.75,
    "Pepper__bell___healthy": 0.0,
    "Potato___Early_blight": 0.80,
    "Potato___Late_blight": 0.90,
    "Potato___healthy": 0.0,
    "Tomato_Bacterial_spot": 0.80,
    "Tomato_Early_blight": 0.80,
    "Tomato_Late_blight": 0.90,
    "Tomato_Leaf_Mold": 0.65,
    "Tomato_Septoria_leaf_spot": 0.70,
    "Tomato_Spider_mites_Two_spotted_spider_mite": 0.70,
    "Tomato__Target_Spot": 0.65,
    "Tomato__Tomato_YellowLeaf__Curl_Virus": 0.85,
    "Tomato__Tomato_mosaic_virus": 0.80,
    "Tomato_healthy": 0.0,
    "Other_plant": 0.0,
    "Rice_bacterial_blight": 0.85, "Rice_blast": 0.90, "Rice_brown_spot": 0.70, "Rice_tungro": 0.90,
    "Banana_cordana": 0.60, "Banana_pestalotiopsis": 0.60, "Banana_sigatoka": 0.80,
    "Apple_scab": 0.70, "Apple_black_rot": 0.80, "Apple_cedar_rust": 0.65, "Cherry_powdery_mildew": 0.60,
    "Maize_gray_leaf_spot": 0.75, "Maize_common_rust": 0.60, "Maize_northern_leaf_blight": 0.75,
    "Grape_black_rot": 0.80, "Grape_esca": 0.85, "Grape_leaf_blight": 0.70, "Orange_citrus_greening": 0.95,
    "Peach_bacterial_spot": 0.70, "Squash_powdery_mildew": 0.60, "Strawberry_leaf_scorch": 0.65,
    "Rose_leaf_spot": 0.65, "Rose_insect_damage": 0.45, "Rose_dry_leaf": 0.35, "Rose_nutrient_deficiency": 0.40,
    "Money_plant_bacterial_wilt": 0.85, "Money_plant_manganese_toxicity": 0.50, "Hibiscus_bacterial_leaf_spot": 0.65,
    "Hibiscus_nutrient_deficiency": 0.40, "Marigold_alternaria_blight": 0.70, "Marigold_pest_damage": 0.50,
} | {c: 0.0 for c in _EXTENDED_DISEASE_CLASSES + _GARDEN_DISEASE_CLASSES if c.endswith("_healthy")}

# Disease result is reported as "uncertain" below this calibrated confidence (0-1).
# Measured on the held-out sets: at 0.90, 1.7% of test leaves become "uncertain", accuracy on the
# rest is 99.90%, and 29% of insect photos still pass (the pest cross-check catches most of those).
DISEASE_UNCERTAIN_THRESHOLD = float(os.getenv("DISEASE_UNCERTAIN_THRESHOLD", "0.90"))
# Crops the disease model was trained on (PlantVillage subset). Other crops cannot be diagnosed.
_CROP_OF_PREFIX = {
    "Pepper": "Bell Pepper", "Potato": "Potato", "Tomato": "Tomato", "Rice": "Rice (Paddy)", "Banana": "Banana",
    "Maize": "Corn (Maize)", "Apple": "Apple", "Grape": "Grape", "Orange": "Orange", "Peach": "Peach", "Cherry": "Cherry",
    "Strawberry": "Strawberry", "Squash": "Squash", "Soybean": "Soybean", "Blueberry": "Blueberry", "Raspberry": "Raspberry",
    "Rose": "Rose", "Money": "Money Plant", "Hibiscus": "Hibiscus", "Marigold": "Marigold",
}


def crop_of_disease_label(label: str) -> str | None:
    """'Rice_blast' -> 'Rice (Paddy)'; None for Other_plant."""
    return None if label == "Other_plant" else _CROP_OF_PREFIX.get(label.split("_")[0])


_deployed_crops = [c for c in map(crop_of_disease_label, DISEASE_CLASSES.values()) if c]
# The original three first (messages and the app list them in this order), then the added crops
SUPPORTED_DISEASE_CROPS = tuple(dict.fromkeys([c for c in ("Tomato", "Potato", "Bell Pepper") if c in _deployed_crops] + _deployed_crops))

# ---- LAN server / mobile API ----
SERVER_HOST = os.getenv("AGROBOT_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("AGROBOT_PORT", "8000"))
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "10"))
ALLOW_FARMER_SIGNUP = os.getenv("ALLOW_FARMER_SIGNUP", "true").strip().lower() in ("1", "true", "yes")
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "30"))
# Shared secret the Raspberry Pi / ESP32 gateway sends in the X-Sensor-Token header
SENSOR_INGEST_TOKEN = os.getenv("SENSOR_INGEST_TOKEN", "").strip()
SENSOR_STALE_SECONDS = int(os.getenv("SENSOR_STALE_SECONDS", "300"))
# Field alerts from live sensor readings (general crop defaults; override in .env for your crop)
ALERT_SOIL_DRY_PCT = float(os.getenv("ALERT_SOIL_DRY_PCT", "25"))
ALERT_SOIL_WET_PCT = float(os.getenv("ALERT_SOIL_WET_PCT", "85"))
ALERT_HEAT_C = float(os.getenv("ALERT_HEAT_C", "38"))
# Raspberry Pi CPU temperature that raises a phone warning (the Pi slows itself down at 80 C)
ALERT_PI_TEMP_C = float(os.getenv("ALERT_PI_TEMP_C", "75"))
# Irrigation advice: below this moisture water soon; rain of at least this much (mm, today+tomorrow, >=60% chance) = skip
IRRIGATION_SOON_PCT = float(os.getenv("IRRIGATION_SOON_PCT", "40"))
IRRIGATION_RAIN_MM = float(os.getenv("IRRIGATION_RAIN_MM", "5"))
# Cool + very humid air favours late blight and other leaf diseases
ALERT_BLIGHT_HUMIDITY_PCT = float(os.getenv("ALERT_BLIGHT_HUMIDITY_PCT", "90"))
ALERT_BLIGHT_TEMP_MIN_C = float(os.getenv("ALERT_BLIGHT_TEMP_MIN_C", "10"))
ALERT_BLIGHT_TEMP_MAX_C = float(os.getenv("ALERT_BLIGHT_TEMP_MAX_C", "25"))
DB_PATH = Path(os.getenv("AGROBOT_DB_PATH", OUTPUTS_DIR / "scans.db"))
SCAN_IMAGES_DIR = OUTPUTS_DIR / "scan_images"
LOG_DIR = ROOT_DIR / "logs"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "agri-qwen:7b").strip()
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))
# Advice/chat run on the laptop LLM; Tamil and other Indic scripts need many tokens, so allow longer
ADVICE_TIMEOUT_SECONDS = float(os.getenv("ADVICE_TIMEOUT_SECONDS", "240"))
# Model for farmer advice/chat in 12 languages (Ollama name). gemma3:4b writes fluent Tamil/Hindi;
# agri-qwen:7b (Qwen 7B) produced meaningless Tamil in testing. Falls back to OPENAI_MODEL if not installed.
ADVISOR_MODEL = os.getenv("ADVISOR_MODEL", "gemma3:4b").strip() or OPENAI_MODEL
# Optional second advisor used only when the main one cannot be reached (Raspberry Pi: the laptop is
# the main advisor, the Pi's own small model the fallback). Empty = no fallback.
ADVISOR_FALLBACK_URL = os.getenv("ADVISOR_FALLBACK_URL", "").strip()
ADVISOR_FALLBACK_MODEL = os.getenv("ADVISOR_FALLBACK_MODEL", "").strip()
# Raspberry Pi only: turn the Pi off after this many hours without any request (0 = never).
# An open phone app counts as use (it checks alerts every minute). Plug the Pi in again to start it.
AUTO_OFF_IDLE_HOURS = float(os.getenv("AUTO_OFF_IDLE_HOURS", "0") or 0)
# Test-time augmentation: average 5 views of each photo (slower, steadier). "false" = 1 view, about 3x
# faster on the Raspberry Pi; switch it off only after measuring accuracy on the test photos.
INFERENCE_TTA = os.getenv("INFERENCE_TTA", "true").strip().lower() not in ("0", "false", "no", "off")
# Free key from data.gov.in for Agmarknet mandi prices (scripts/set_market_key.ps1 stores it). Empty = prices off.
DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY", "").strip()
# Pi status on the laptop website. On the Pi: STATUS_TOKEN (random key) lets /api/v1/device/report
# answer. On the laptop: PI_URL + PI_STATUS_TOKEN (same key) let the admin page show the Pi. Empty = off.
STATUS_TOKEN = os.getenv("STATUS_TOKEN", "").strip()
PI_URL = os.getenv("PI_URL", "").strip().rstrip("/")
PI_STATUS_TOKEN = os.getenv("PI_STATUS_TOKEN", "").strip()

# ElevenLabs Studio Voice Configuration
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM").strip()
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip()

RGB_SPECTRAL_LIMITATION = (
    "True NDRE needs NIR + Red-Edge bands and true CRI needs narrow-band "
    "reflectance near 510/550/700 nm. This app uses RGB proxies from your "
    "notebooks (ExG for chlorophyll/NDRE, CRI1 = 1/B - 1/G for carotenoid). "
    "Values are relative indices for comparison, not lab-accurate pigment measurements."
)
