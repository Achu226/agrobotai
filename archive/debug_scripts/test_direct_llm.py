import json
from src.ai_advisor import generate_advice
crop = "Tomato"
disease = {"class": "Early Blight", "display_name": "Tomato Early Blight", "confidence": 98.5}
pest = {"pest_detected": False}
ndre = {"value": 0.45, "score": 60, "status": "Moderate Stress"}
cri = {"value": 3.1, "score": 85, "status": "Healthy"}
overall = {"overall_score": 75, "overall_status": "Attention Required", "assessment_confidence": 91.0}

advice = generate_advice(crop, pest, disease, ndre, cri, overall)
print(json.dumps(advice, indent=2))
