import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.resolve()))
from src.multilingual_chatbot import MultilingualFarmingAssistant
from src.ollama_manager import ensure_ollama_ready

def test_chatbot():
    print("Checking Ollama readiness...")
    ensure_ollama_ready()

    print("\nInitializing Chatbot in English...")
    bot_en = MultilingualFarmingAssistant(language="en", api_key="ollama")

    diagnostic_info = {
        "crop": "Tomato",
        "pest_name": "Aphids",
        "disease_name": "Healthy",
        "overall_health_score": 75,
        "spectral_anomalies": ["Mild NDRE depression indicating early stress"]
    }

    user_query = "What should I do immediately to control these aphids before they spread?"

    print(f"\nSending Query to Local LLM: {bot_en.api_key} via base_url: http://localhost:11434/v1")
    response = bot_en.ask_question(user_query, context=diagnostic_info)

    print("\nRESPONSE (English):")
    print(response.get("answer", "ERROR or EMPTY"))
    print("Status:", "OK" if response.get("ok") else "FAILED")
    if not response.get("ok"):
        print("Error details:", response.get("error"))
        print("Source:", response.get("source"))

if __name__ == "__main__":
    test_chatbot()