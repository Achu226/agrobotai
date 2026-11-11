import os
import sys
import json
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.multilingual_chatbot import MultilingualFarmingAssistant
from src.ai_advisor import generate_advice

print("=" * 60)
print("TESTING 100% OFFLINE LOCAL LLM INTEGRATION (OLLAMA GPU)")
print("=" * 60)

# 1. Test Multilingual Chatbot in Tamil
print("\n[1] Testing Multilingual Assistant (Tamil Question)...")
ta_bot = MultilingualFarmingAssistant(language="ta")
context = {
    "crop": "Tomato",
    "pest": {"ok": False, "value": "No Pest"},
    "disease": {"ok": True, "display_name": "Tomato Early Blight", "confidence": 99.2},
    "severity": {"ok": True, "stage": "Early Stage", "affected_area_percent": 8.5},
    "overall": {"overall_score": 58, "overall_status": "MILD STRESS"}
}

t0 = time.time()
ta_response = ta_bot.ask_question("தக்காளி இலை கருகல் நோயை குணப்படுத்த என்ன மருந்து தெளிக்க வேண்டும்?", context=context)
latency_ta = time.time() - t0

print(f"Status: {'SUCCESS' if ta_response.get('ok') else 'FAILED'}")
print(f"Latency: {latency_ta:.2f}s")
print(f"Language: {ta_response.get('language')}")
print(f"Answer Preview:\n{ta_response.get('answer')[:300]}...")

# 2. Test Multilingual Chatbot in Hindi
print("\n[2] Testing Multilingual Assistant (Hindi Question)...")
hi_bot = MultilingualFarmingAssistant(language="hi")
t0 = time.time()
hi_response = hi_bot.ask_question("आलू में अगेती झुलसा रोग के लिए जैविक उपचार क्या है?", context=context)
latency_hi = time.time() - t0

print(f"Status: {'SUCCESS' if hi_response.get('ok') else 'FAILED'}")
print(f"Latency: {latency_hi:.2f}s")
print(f"Language: {hi_response.get('language')}")
print(f"Answer Preview:\n{hi_response.get('answer')[:300]}...")

# 3. Test AI Advisor Structured JSON Generation
print("\n[3] Testing Structured AI Agronomist Advisory JSON...")
pest_payload = {"ok": False, "error": "No pest"}
disease_payload = {"ok": True, "display_name": "Tomato Early Blight", "confidence": 98.5, "score": 35}
ndre_payload = {"ok": True, "score": 75}
cri_payload = {"ok": True, "score": 80}
overall_payload = {"ok": True, "overall_score": 62, "overall_status": "MILD STRESS", "failed_modules": []}

t0 = time.time()
advice = generate_advice(
    crop="Tomato",
    pest=pest_payload,
    disease=disease_payload,
    ndre=ndre_payload,
    cri=cri_payload,
    overall=overall_payload
)
latency_advice = time.time() - t0

print(f"Status: {'SUCCESS' if advice.get('ok') else 'FAILED'}")
print(f"Source: {advice.get('source')}")
print(f"Latency: {latency_advice:.2f}s")
print("Immediate Actions:", advice.get("immediate_actions"))
print("Disease Management:", advice.get("disease_management"))
print("\nAll Local LLM tests completed!")
