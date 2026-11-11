"""
Multilingual Farming Assistant Chatbot & Agronomic NLP Engine
Supports Tamil, Hindi, English, Telugu, Kannada, Malayalam, Marathi, Bengali, Punjabi, Gujarati.
Provides deep-domain plant pathology, pest management, bio-inputs, and dosage guidance for Indian farmers.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_TIMEOUT_SECONDS


# Supported languages
SUPPORTED_LANGUAGES = {
    "ta": "Tamil (தமிழ்)",
    "hi": "Hindi (हिन्दी)",
    "en": "English",
    "te": "Telugu (తెలుగు)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "ml": "Malayalam (മലയാളം)",
    "mr": "Marathi (मराठी)",
    "bn": "Bengali (বাংলা)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "gu": "Gujarati (ગુજરાતી)"
}


# Pre-computed agricultural knowledge base for instant responses & fallback
AGRI_KNOWLEDGE_BASE_TAMIL = {
    "treatment": """பயிர் பாதுகாப்பு மற்றும் மருந்து தெளிப்பு வழிகாட்டல்:

1. **பூஞ்சைக் கொல்லி (Fungicide)**:
   - ஆரம்ப நிலை: மேன்கோசெப் (Mancozeb 75% WP) - 2 கிராம் / லிட்டர் தண்ணீர்
   - தீவிர நிலை: அஸோக்ஸிஸ்ட்ரோபின் + டைபனோகோனசோல் (Azoxystrobin + Difenoconazole) - 1 மி.லி / லிட்டர் தண்ணீர்

2. **பூச்சிக் கொல்லி (Insecticide)**:
   - இலைப்பேன் / அசுவினி: வேப்ப எண்ணெய் (Neem Oil 10,000 ppm) - 3 மி.லி / லிட்டர் அல்லது இமிடாக்ளோப்ரிட் (Imidacloprid 17.8% SL) - 0.5 மி.லி / லிட்டர்

3. **தெளிக்கும் நேரம்**:
   - காலை 6:00 - 9:00 மணி அல்லது மாலை 4:30 - 6:30 மணிக்குள் இலைகளின் அடிப்பகுதியில் படுமாறு தெளிக்கவும்.
   - தெளிக்கும் போது முகக்கவசம் மற்றும் கையுறைகள் அணியவும்.""",

    "organic": """இயற்கை மற்றும் இயற்கை வேளாண்மை தீர்வுகள் (Organic & Bio-Control):

1. **பஞ்சகாவ்யா கரைசல்**:
   - 3% பஞ்சகாவ்யா (30 மி.லி / லிட்டர் தண்ணீர்) 10-15 நாட்கள் இடைவெளியில் தெளித்தால் செடியின் நோய் எதிர்ப்பு சக்தி அதிகரிக்கும்.

2. **மூலிகைப் பூச்சி விரட்டி (5 இலை கரைசல்)**:
   - வேம்பு, ஆடாதோடை, நொச்சி, எருக்கு, துளசி இலைகளை மாட்டுச் சிறுநீரில் 10 நாட்கள் ஊறவைத்து வடிகட்டி (30 மி.லி / லிட்டர்) தெளிக்கவும்.

3. **உயிரியல் கட்டுப்பாட்டு காரணிகள் (Bio-Control)**:
   - சூடோமோனாஸ் புளோரசன்ஸ் (Pseudomonas fluorescens) - 5 கிராம் / லிட்டர்
   - டிரைக்கோடெர்மா விரிடி (Trichoderma viride) - 5 கிராம் / லிட்டர் மண்ணில் இடவும்.""",

    "irrigation": """பாசன மற்றும் ஈரப்பத மேலாண்மை:

1. செடியின் வேர் பகுதியில் மட்டுமே நீர் பாய்ச்சவும். இலைகளின் மேல் தண்ணீர் தெளிப்பதை தவிர்க்கவும் (ஈரப்பதம் பூஞ்சை நோய்களை பரப்பும்).
2. சொட்டு நீர் பாசனம் (Drip Irrigation) சிறந்த பலன் தரும்.
3. வடிகால் வசதியை உறுதி செய்து வயலில் தேங்கி நிற்கும் தண்ணீரை உடனடியாக வெளியேற்றவும்.""",

    "fertilizer": """ஒருங்கிணைந்த ஊட்டச்சத்து மற்றும் உர மேலாண்மை:

1. **அடி உரம் (Basal)**: ஏக்கருக்கு 5 டன் மக்கிய தொழு உரம் + 50 கிலோ வேப்பம் புண்ணாக்கு இடவும்.
2. **நுண்ணூட்டச்சத்து (Micronutrients)**: துத்தநாகம் (Zinc) மற்றும் போரான் (Boron) குறைபாட்டிற்கு நுண்ணூட்டக் கலவை 2 கிராம்/லிட்டர் தெளிக்கவும்.
3. **வளர்ச்சி ஊக்கி**: மீன் அமிலம் (Fish Amino) 5 மி.லி / லிட்டர் தெளிப்பது இலைகளுக்கு பசுமையும் வலிமையும் தரும்."""
}


class MultilingualFarmingAssistant:
    """
    Multilingual chatbot that helps farmers with crop health questions.
    Uses local Ollama LLM (agri-qwen:7b) or OpenAI/Groq with robust agricultural context.
    """

    def __init__(self, api_key: Optional[str] = None, language: str = "ta"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "") or OPENAI_API_KEY or "ollama"
        self.language = language
        self.language_name = SUPPORTED_LANGUAGES.get(language, "Tamil (தமிழ்)")
        self.conversation_history = []

    def ask_question(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ask an agricultural question in any supported Indian language or English.

        Args:
            question: Farmer's question
            context: Diagnostic context from image analysis (crop, pest, disease, score)

        Returns:
            Dict containing answer, language, and method.
        """
        base_url = (os.getenv("OPENAI_BASE_URL", "") or OPENAI_BASE_URL or "http://localhost:11434/v1").strip()
        api_key = self.api_key or os.getenv("OPENAI_API_KEY", "") or OPENAI_API_KEY or "ollama"

        try:
            from openai import OpenAI

            # Handle base URL routing (Local Ollama vs Cloud)
            if api_key.startswith("gsk_"):
                client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1", timeout=OPENAI_TIMEOUT_SECONDS)
                model_name = "llama-3.3-70b-versatile"
            elif base_url:
                client = OpenAI(api_key=api_key, base_url=base_url, timeout=OPENAI_TIMEOUT_SECONDS)
                model_name = (os.getenv("OPENAI_MODEL", "") or OPENAI_MODEL or "agri-qwen:7b").strip()
            else:
                client = OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT_SECONDS)
                model_name = (os.getenv("OPENAI_MODEL", "") or OPENAI_MODEL or "gpt-4o-mini").strip()

            # Build context-rich agronomy prompt
            system_prompt = self._build_system_prompt(context)

            # Add question to history
            self.conversation_history.append({"role": "user", "content": question})

            # Call LLM
            messages = [{"role": "system", "content": system_prompt}] + self.conversation_history

            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.25,
                max_tokens=900
            )

            answer = response.choices[0].message.content.strip()

            # Clean any internal reasoning tokens like <think>...</think> if present
            answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()

            # Add to history
            self.conversation_history.append({"role": "assistant", "content": answer})

            return {
                "ok": True,
                "question": question,
                "answer": answer,
                "language": self.language_name,
                "method": "llm"
            }

        except Exception as e:
            print(f"[MultilingualChatbot] LLM invocation note: {e}. Generating expert agronomic response.")
            fallback = self._get_fallback_answer(question, context)
            return {
                "ok": True,
                "question": question,
                "answer": fallback,
                "language": self.language_name,
                "method": "agronomy_knowledge_engine"
            }

    def _build_system_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        """Build system prompt with diagnostic context and strict Indian language rules."""

        lang_instruction = f"""You are HORTICBOTAI Virtual Agronomist — an expert agricultural scientist, plant pathologist, and crop advisory consultant with 20+ years of field experience across India.

🚨 STRICT LANGUAGE DIRECTIVE 🚨
- Target Language: {self.language_name}
- You MUST write your ENTIRE response exclusively in {self.language_name} script.
- If the target language is Tamil (தமிழ்), reply ONLY in natural, respectful, fluent Tamil (தூய மற்றும் எளிய தமிழ்).
- If the target language is Hindi (हिन्दी), reply ONLY in natural, respectful, fluent Hindi.
- NEVER mix English sentences into the regional language response.

Agronomic Advisory Standards:
1. **Diagnosis & Pathology**: Explain what the disease/pest is, how it spreads (humidity, rain, wind), and the severity stage.
2. **Integrated Pest & Disease Management (IPM)**:
   - Cultural/Sanitation: Removing affected leaves/stems, sterilizing tools, field drainage.
   - Biological/Bio-control: Trichoderma viride, Pseudomonas fluorescens, Bacillus subtilis, Beauveria bassiana.
   - Organic: Neem oil (வேப்பெண்ணெய் 10000 ppm), Panchagavya, Dashaparni kashayam.
   - Chemical Control: Exact chemical active ingredients (e.g., Mancozeb, Azoxystrobin, Chlorantraniliprole, Imidacloprid) with accurate mixing dosage (e.g. 2g/L or 1ml/L).
3. **Application Timing & Safety**:
   - Spray early morning (6-9 AM) or late evening (4:30-6:30 PM).
   - Wear protective gloves and masks. Mention Pre-Harvest Interval (PHI).
4. **Tone**: Direct, encouraging, farmer-friendly, highly practical. Use numbered bullet points.
"""

        if context:
            crop = context.get("crop", "Crop")
            pest = context.get("pest", {})
            disease = context.get("disease", {})
            overall = context.get("overall", {})
            overall_status = overall.get("overall_status", "Analyzed")
            health_score = overall.get("overall_score", "N/A")
            severity = context.get("severity", {})
            nutrients = context.get("nutrients", {})
            ndre = context.get("ndre", {})
            cri = context.get("cri", {})

            context_info = f"""
Current Diagnostic Report for Field Analysis:
- Crop: {crop}
- Overall Foliage Health Score: {health_score}/100 ({overall_status})
"""
            if pest.get("ok") and pest.get("value") != "No Pest":
                pest_name = pest.get("display_name") or pest.get("value")
                confidence = pest.get("confidence", "Unknown")
                context_info += f"- Identified Insect Pest: {pest_name} (Confidence: {confidence}%)\n"

            if disease.get("ok") and disease.get("display_name"):
                disease_name = disease.get("display_name")
                confidence = disease.get("confidence", "Unknown")
                context_info += f"- Identified Foliar Disease: {disease_name} (Confidence: {confidence}%)\n"

            if severity.get("ok"):
                aff_area = severity.get("affected_area_percent", 0)
                stage = severity.get("stage", "Unknown")
                context_info += f"- Severity Stage: {stage} ({aff_area:.1f}% leaf surface affected)\n"

            if nutrients.get("ok") and nutrients.get("deficiency") != "None":
                deficiency = nutrients.get("deficiency")
                context_info += f"- Chlorophyll/Nutrient Deficiency: {deficiency}\n"

            if ndre.get("ok"):
                context_info += f"- NDRE Pigment Index: {ndre.get('score')}/100\n"

            if cri.get("ok"):
                context_info += f"- Carotenoid Stress Index (CRI): {cri.get('score')}/100\n"

            lang_instruction += context_info

        return lang_instruction

    def _get_fallback_answer(self, question: str, context: Optional[Dict[str, Any]]) -> str:
        """Provide domain-rich agricultural answers when offline or loading."""
        q_lower = question.lower()
        crop_name = context.get("crop", "பயிர்") if context else "பயிர்"
        disease_name = context.get("disease", {}).get("display_name") if context else None
        pest_name = context.get("pest", {}).get("display_name") if context else None

        # Check for matching topics
        if any(w in question for w in ["இயற்கை", "organic", "bio", "பஞ்சகாவ்யா", "வேம்பு", "பூச்சி விரட்டி"]):
            topic_content = AGRI_KNOWLEDGE_BASE_TAMIL["organic"]
        elif any(w in question for w in ["தண்ணீர்", "பாசனம்", "irrigation", "நீர்"]):
            topic_content = AGRI_KNOWLEDGE_BASE_TAMIL["irrigation"]
        elif any(w in question for w in ["உரம்", "fertilizer", "npk", "சத்து"]):
            topic_content = AGRI_KNOWLEDGE_BASE_TAMIL["fertilizer"]
        else:
            topic_content = AGRI_KNOWLEDGE_BASE_TAMIL["treatment"]

        if self.language == "ta":
            intro = f"வணக்கம்! உங்கள் {crop_name} பயிருக்கான பரிந்துரைகள்:\n\n"
            if disease_name:
                intro += f"📌 கண்டறியப்பட்ட நோய்: **{disease_name}**\n"
            if pest_name:
                intro += f"📌 கண்டறியப்பட்ட பூச்சி: **{pest_name}**\n\n"

            return f"""{intro}{topic_content}

💡 *கூடுதல் ஆலோசனைக்கு உங்கள் வட்டார வேளாண்மை உதவி அலுவலரை (AEO) தொடர்பு கொள்ளலாம்.*"""

        elif self.language == "hi":
            return f"""नमस्ते! आपकी {crop_name} फसल के लिए कृषि परामर्श:

1. **उपचार एवं छिड़काव**:
   - फफूंदनाशक: मैंकोजेब (Mancozeb 75% WP) - 2 ग्राम प्रति लीटर पानी में मिलाकर छिड़कें।
   - कीटनाशक: नीम का तेल (Neem Oil 10,000 ppm) - 3 मि.ली. प्रति लीटर।
2. **छिड़काव का सही समय**: सुबह 6 से 9 बजे अथवा शाम को 4:30 के बाद।
3. **सुरक्षा**: छिड़काव करते समय मास्क और दस्ताने का प्रयोग करें।

जैविक समाधान के लिए ट्राइकोडर्मा विरिडी 5 ग्राम प्रति लीटर पानी में प्रयोग करें।"""

        # English
        return f"""Hello! Here is the precision advisory for your {crop_name}:

1. **Chemical Treatment**:
   - Fungicide: Mancozeb 75% WP @ 2.0 g/L or Azoxystrobin + Difenoconazole @ 1.0 ml/L
   - Pest Control: Neem Oil (10,000 ppm) @ 3.0 ml/L or Imidacloprid 17.8% SL @ 0.5 ml/L
2. **Organic Bio-Control**:
   - Foliar application of Pseudomonas fluorescens @ 5 g/L
   - Soil drenching with Trichoderma viride @ 5 g/L
3. **Application Protocol**:
   - Spray early morning (6:00 - 9:00 AM) or late evening
   - Ensure full coverage of the abaxial (underside) leaf surface."""

    def get_common_questions(self) -> List[Dict[str, str]]:
        """Get list of common farming questions in the selected language."""
        questions = {
            "ta": [
                {"q": "இந்த நோய்க்கான சிறந்த மருந்து என்ன?", "topic": "treatment"},
                {"q": "இயற்கை பூச்சி விரட்டி தயாரிப்பது எப்படி?", "topic": "organic"},
                {"q": "எத்தனை நாட்களுக்கு ஒருமுறை மருந்து தெளிக்க வேண்டும்?", "topic": "recovery"},
                {"q": "பாசன நீர் அளவு மற்றும் நேரம் என்ன?", "topic": "irrigation"},
                {"q": "உர மேலாண்மை மற்றும் NPK அளவு என்ன?", "topic": "fertilizer"}
            ],
            "hi": [
                {"q": "इस बीमारी के लिए सबसे अच्छी दवा कौन सी है?", "topic": "treatment"},
                {"q": "जैविक कीटनाशक कैसे बनाएं?", "topic": "organic"},
                {"q": "कितने दिनों में छिड़काव दोहराना चाहिए?", "topic": "recovery"},
                {"q": "उर्वरक एवं सिंचाई की सही मात्रा क्या है?", "topic": "fertilizer"}
            ],
            "en": [
                {"q": "What is the best treatment for this issue?", "topic": "treatment"},
                {"q": "How to prepare organic pest repellents?", "topic": "organic"},
                {"q": "What is the recommended spraying schedule?", "topic": "recovery"},
                {"q": "What are the fertilizer and irrigation guidelines?", "topic": "fertilizer"}
            ]
        }
        return questions.get(self.language, questions["en"])

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
