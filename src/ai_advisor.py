from __future__ import annotations

import json

from src.config import (
    LOW_CONFIDENCE_THRESHOLD,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TIMEOUT_SECONDS,
    RGB_SPECTRAL_LIMITATION,
)

ADVISOR_SYSTEM_PROMPT = """You are an expert agricultural advisor for smallholder farmers.
You receive structured detection results from a Python pipeline. You MUST:
- Interpret only the provided results.
- Never invent a pest, disease, NDRE/CRI value, score, or confidence.
- Never recalculate numerical health scores.
- Treat RGB-derived ExG as "RGB-derived vegetation proxy" and CRI as "RGB-derived carotenoid proxy", not actual multispectral/laboratory measurements.
- For low confidence findings (below ~50-60%), explicitly state "Verification Required" and don't assume the disease/pest is confirmed.
- Avoid unsafe pesticide recipes, specific unapproved chemical doses, or making up PHI numbers.
- Recommend following locally approved agricultural guidance and product labels.
- Keep advice practical, crop-specific, and easy to follow.

Return valid JSON with this exact schema (Use Arrays of STRINGS ONLY for all lists except emergency_actions):
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

def build_advisor_payload(crop, pest, disease, ndre, cri, overall, severity_data=None, nutrient_data=None):
    payload = {
        "crop": crop,
        "crop_confidence": None,
        "disease": {
            "name": disease.get("display_name") or disease.get("class") or "Healthy",
            "confidence": disease.get("confidence_raw", 0.0) * 100 if getattr(disease, 'get', None) and "confidence_raw" in disease else disease.get("confidence", 0.0),
            "score": disease.get("score")
        },
        "pest": {
            "name": pest.get("display_name") or pest.get("class") or "No pests detected",
            "top_prediction": pest.get("class"),
            "confidence": pest.get("confidence_raw", 0.0) * 100 if getattr(pest, 'get', None) and "confidence_raw" in pest else pest.get("confidence", 0.0),
            "probability_margin": pest.get("evidence_score", None),
            "visual_evidence": pest.get("pest_detected", False),
            "verification_required": pest.get("pest_detected", False) and pest.get("low_confidence", False)
        },
        "lesion": {
            "affected_area_percent": severity_data.get("affected_area_percent", None) if severity_data else None,
            "healthy_area_percent": severity_data.get("healthy_area_percent", None) if severity_data else None,
            "stage": severity_data.get("stage", "Unknown") if severity_data else None,
            "health_score": severity_data.get("health_score", None) if severity_data else None
        },
        "plant_health": {
            "score": overall.get("overall_score"),
            "status": overall.get("overall_status"),
            "diagnostic_confidence": overall.get("assessment_confidence")
        },
        "vegetation": {
            "exg_proxy": ndre.get("value"),
            "greenness_score": ndre.get("score"),
            "interpretation": ndre.get("status")
        },
        "carotenoid": {
            "cri_proxy": cri.get("value"),
            "stress_score": cri.get("score")
        },
        "nutrient": {
            "status": nutrient_data.get("status") if nutrient_data else "No visible nutrient stress detected",
            "confidence": nutrient_data.get("confidence") if nutrient_data else "None"
        },
        "soil": {
            "npk": None, "ph": None, "moisture": None, "temperature": None
        },
        "weather": {
            "temperature": None, "humidity": None, "rain_probability": None
        },
        "field": {
            "area_acres": 1, "growth_stage": None
        }
    }
    return payload

def _fallback_advice(crop: str, pest: dict, disease: dict, ndre: dict, cri: dict, overall: dict) -> dict:
    warnings = []
    immediate = []
    if pest.get("ok") and pest.get("pest_detected"):
        immediate.append({"priority": "HIGH", "action": f"Inspect plants for {pest.get('display_name')}.", "reason": "Pest activity flagged."})
    if disease.get("ok") and not disease.get("is_healthy_class"):
        immediate.append({"priority": "HIGH", "action": f"Look for {disease.get('display_name')} symptoms on nearby plants.", "reason": "Disease detected."})

    return {
        "ok": True,
        "source": "fallback",
        "summary": {
            "headline": "Automatic Local Rules Applied",
            "severity": overall.get("overall_status", "Unknown"),
            "confidence": overall.get("assessment_confidence", "Unknown"),
            "farmer_message": "Local AI advisor is unavailable. Using deterministic rule-based guidance."
        },
        "emergency_actions": immediate or [{"priority": "LOW", "action": "No high-priority emergency actions required.", "reason": "Plant appears relatively healthy."}],
        "schedule": {
            "next_24_hours": ["Inspect plants visually in the field."],
            "days_2_3": ["Check for symptom spreading or pest activity."],
            "days_4_7": ["Maintain irrigation and monitor new growth."]
        },
        "pest_disease_control": {
            "confirmed_findings": [],
            "possible_findings": [],
            "verification_steps": ["Always verify model findings manually in the field before acting."],
            "cultural_control": ["Ensure proper spacing and airflow."],
            "biological_control": [],
            "chemical_control": ["Use only locally approved treatments and follow labels strictly."]
        },
        "water_soil_nutrition": {
            "irrigation": ["Water morning or evening, avoid waterlogging."],
            "soil_actions": [],
            "nutrient_actions": [],
            "sensor_status": "No live sensor data available."
        },
        "risk_field_notes": {
            "disease_risk": "Varies by local weather",
            "pest_risk": "Varies by local weather",
            "spread_risk": "Unknown",
            "environmental_risk": "Unknown",
            "monitoring_notes": ["Monitor regularly."],
            "next_scan": "In 3-7 days if symptoms persist."
        },
        "safety": {
            "warnings": warnings,
            "chemical_disclaimer": "Always consult local agricultural experts. Model results are advisory.",
            "label_required": True
        }
    }

def generate_advice(
    crop: str, pest: dict, disease: dict, ndre: dict, cri: dict, overall: dict,
    api_key: str | None = None, severity_data: dict | None = None, nutrient_data: dict | None = None, location: str | None = None
) -> dict:
    from src.config import OPENAI_BASE_URL
    fallback = _fallback_advice(crop, pest, disease, ndre, cri, overall)
    effective_api_key = (api_key or OPENAI_API_KEY or "ollama").strip()
    base_url = OPENAI_BASE_URL or "http://localhost:11434/v1"

    payload = build_advisor_payload(crop, pest, disease, ndre, cri, overall, severity_data, nutrient_data)

    try:
        from openai import OpenAI
        client_kwargs = {"api_key": effective_api_key, "timeout": OPENAI_TIMEOUT_SECONDS}
        if base_url:
            client_kwargs["base_url"] = base_url

        model = OPENAI_MODEL or "agri-qwen:7b"

        # Override to use the required agri-qwen model as per prompt guidelines when connecting locally!
        if "localhost:11434" in base_url or "127.0.0.1" in base_url:
            model = "agri-qwen:7b"

        client = OpenAI(**client_kwargs)

        req_params = {
            "model": model,
            "temperature": 0.25,
            "messages": [
                {"role": "system", "content": ADVISOR_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)}
            ]
        }

        req_params["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**req_params)
        content = response.choices[0].message.content

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        parsed = json.loads(content)
        parsed["ok"] = True
        parsed["source"] = "local_llm"

        # Ensure all required keys exist
        default_keys = ["summary", "emergency_actions", "schedule", "pest_disease_control", "water_soil_nutrition", "risk_field_notes", "safety"]
        for k in default_keys:
            if k not in parsed:
                parsed[k] = fallback[k]

        return parsed
    except Exception as exc:
        print(f"[AI Advisor] LLM Generation Error: {exc}")
        fallback["source"] = "fallback_api_error"
        fallback["error"] = str(exc)
        return fallback