import re

file_path = "D:/AGROBOTAI/src/ai_advisor.py"
with open(file_path, "r") as f:
    content = f.read()

prompt_fix = """Return valid JSON with this exact schema (Use Arrays of STRINGS ONLY for all lists except emergency_actions):
{
  "summary": {
    "headline": "String",
    "severity": "String",
    "confidence": "String",
    "farmer_message": "String"
  },
  "emergency_actions": [
    {
      "priority": "HIGH",
      "action": "String",
      "reason": "String"
    }
  ],
  "schedule": {
    "next_24_hours": ["String"],
    "days_2_3": ["String"],
    "days_4_7": ["String"]
  },
  "pest_disease_control": {
    "confirmed_findings": ["String"],
    "possible_findings": ["String"],
    "verification_steps": ["String"],
    "cultural_control": ["String"],
    "biological_control": ["String"],
    "chemical_control": ["String"]
  },
  "water_soil_nutrition": {
    "irrigation": ["String"],
    "soil_actions": ["String"],
    "nutrient_actions": ["String"],
    "sensor_status": "String"
  },
  "risk_field_notes": {
    "disease_risk": "String",
    "pest_risk": "String",
    "spread_risk": "String",
    "environmental_risk": "String",
    "monitoring_notes": ["String"],
    "next_scan": "String"
  },
  "safety": {
    "warnings": ["String"],
    "chemical_disclaimer": "String",
    "label_required": true
  }
}"""

content = re.sub(
    r'Return valid JSON with this exact schema:\n\{.*?\n\}"""', 
    prompt_fix + '"""', 
    content, 
    flags=re.DOTALL
)

with open(file_path, "w") as f:
    f.write(content)

print("Patched ai_advisor.py")
