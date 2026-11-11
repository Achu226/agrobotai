"""
Quick Test Script - Verify HORTICBOTAI Setup
Run this to check if all modules, PyTorch models, and React builds load correctly
"""

import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

print("=" * 60)
print("🧪 HORTICBOTAI Setup Verification")
print("=" * 60)

# Test 1: Check Python version
print("\n1. Python Version:")
print(f"   {sys.version}")
if sys.version_info < (3, 10):
    print("   ⚠️  WARNING: Python 3.10+ recommended")

# Test 2: Import core backend libraries
print("\n2. Testing Core Backend Libraries...")
try:
    import numpy as np
    import cv2
    from PIL import Image
    import fastapi
    import uvicorn
    import torch
    import torchvision
    import timm
    print("   ✅ Core libraries OK (numpy, opencv, PIL, fastapi, uvicorn, torch, timm)")
except ImportError as e:
    print(f"   ❌ Import failed: {e}")
    print("   Run: pip install -r requirements.txt")

# Test 3: Import project modules
print("\n3. Testing Project Modules...")
try:
    from src.config import CROPS, PEST_CLASSES, DISEASE_CLASSES
    from src.pipeline import analyze_image
    from src.health_engine import combine_health
    from src.pest_detector import detect_pest, load_pest_model
    from src.disease_detector import detect_disease, load_disease_model
    print("   ✅ Deep Learning & Core Diagnostic modules OK")
except ImportError as e:
    print(f"   ❌ Import failed: {e}")

# Test 4: Import advanced agronomic feature modules
print("\n4. Testing Advanced Feature Modules...")
try:
    from src.disease_severity import calculate_disease_severity
    from src.nutrient_deficiency import analyze_nutrient_deficiency
    from src.weather_forecast import WeatherService, calculate_disease_risk
    from src.dosage_calculator import DosageCalculator
    from src.multilingual_chatbot import MultilingualFarmingAssistant, SUPPORTED_LANGUAGES
    from src.recovery_tracker import create_plot, get_all_plots
    print("   ✅ All advanced modules OK (Severity, Nutrients, Weather, Dosage, Chatbot, Tracker)")
except ImportError as e:
    print(f"   ❌ Import failed: {e}")

# Test 5: Check for model files
print("\n5. Checking Model Files & Weights...")
from src.config import PEST_MODEL_PATH, DISEASE_MODEL_PATH

if PEST_MODEL_PATH.exists():
    print(f"   ✅ Pest model found: {PEST_MODEL_PATH.name}")
else:
    print(f"   ℹ️  Pest model path: {PEST_MODEL_PATH} (PyTorch EfficientNet transfer learning will load dynamically)")

if DISEASE_MODEL_PATH.exists():
    print(f"   ✅ Disease model found: {DISEASE_MODEL_PATH.name}")
else:
    print(f"   ℹ️  Disease model path: {DISEASE_MODEL_PATH} (PyTorch EfficientNet transfer learning will load dynamically)")

# Test 6: Check PyTorch Execution Device
print("\n6. PyTorch Execution Environment...")
try:
    if torch.cuda.is_available():
        print(f"   ✅ CUDA Available: {torch.cuda.get_device_name(0)}")
        print(f"   ✅ CUDA Version: {torch.version.cuda}")
    else:
        print("   ✅ PyTorch running in CPU mode (Optimized for inference)")
except Exception as e:
    print(f"   ⚠️ PyTorch status: {e}")

# Test 7: Verify Frontend Static Build
print("\n7. Checking React Frontend Build...")
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if (frontend_dist / "index.html").exists():
    print(f"   ✅ React Single-Page Application build found: {frontend_dist}")
else:
    print(f"   ⚠️ React build missing. Run: cd frontend && npm run build")

# Test 8: Environment variables
print("\n8. Configuration Check...")
from src.config import OPENAI_API_KEY, OUTPUTS_DIR

if OPENAI_API_KEY:
    print(f"   ✅ OpenAI/Groq API Key configured")
else:
    print("   ℹ️ OpenAI API Key not set (will use local fallback agronomic advisor)")

print(f"   ✅ Output directory: {OUTPUTS_DIR}")

# Test 9: Quick functionality test
print("\n9. Quick End-to-End Functionality Test...")
try:
    test_img = np.zeros((224, 224, 3), dtype=np.uint8)
    test_img[:, :] = [100, 150, 100]  # Green leaf mock

    from src.image_utils import validate_plant_image
    is_valid, msg, frac = validate_plant_image(test_img)
    print(f"   ✅ Image validation works (valid={is_valid}, frac={frac:.2f})")

    from src.disease_severity import calculate_disease_severity
    severity = calculate_disease_severity(test_img)
    print(f"   ✅ Disease severity segmentation works (affected={severity.get('affected_percentage', 0)}%)")

    dosage = DosageCalculator.calculate_dosage("Early Blight", field_size_acres=2.0)
    print(f"   ✅ Precision dosage calculator works (tanks={dosage.get('number_of_tanks_required')})")

except Exception as e:
    print(f"   ❌ Functionality test failed: {e}")

print("\n" + "=" * 60)
print("🎉 Setup Verification Complete!")
print("=" * 60)
print("\n📋 Next Steps:")
print("   1. Launch the Application: python server.py (or run start.bat)")
print("   2. Open your browser to: http://localhost:8000")
print("   3. Access Interactive API Docs: http://localhost:8000/docs\n")
