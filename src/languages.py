"""
The 12 languages AGROBOTAI advises farmers in, plus script-based language detection.

Detection is by Unicode script: every Indian language here except Hindi/Marathi (both Devanagari)
has its own script, so a question typed in Tamil letters is answered in Tamil. Latin text and
Devanagari fall back to the farmer's chosen language (Marathi users get Marathi, others Hindi).
"""
from __future__ import annotations

import re

# code: (English name, native name)
LANGUAGES: dict[str, tuple[str, str]] = {
    "ta": ("Tamil", "தமிழ்"),
    "en": ("English", "English"),
    "hi": ("Hindi", "हिन्दी"),
    "te": ("Telugu", "తెలుగు"),
    "kn": ("Kannada", "ಕನ್ನಡ"),
    "ml": ("Malayalam", "മലയാളം"),
    "mr": ("Marathi", "मराठी"),
    "bn": ("Bengali", "বাংলা"),
    "gu": ("Gujarati", "ગુજરાતી"),
    "pa": ("Punjabi", "ਪੰਜਾਬੀ"),
    "or": ("Odia", "ଓଡ଼ିଆ"),
    "ur": ("Urdu", "اردو"),
}
DEFAULT_LANGUAGE = "ta"

_SCRIPTS = [
    ("ta", r"[஀-௿]"),
    ("te", r"[ఀ-౿]"),
    ("kn", r"[ಀ-೿]"),
    ("ml", r"[ഀ-ൿ]"),
    ("bn", r"[ঀ-৿]"),
    ("gu", r"[઀-૿]"),
    ("pa", r"[਀-੿]"),
    ("or", r"[଀-୿]"),
    ("ur", r"[؀-ۿ]"),
    ("hi", r"[ऀ-ॿ]"),
]

# Section titles for the advice card, so the whole card reads in the farmer's language
ADVICE_SECTION_TITLES: dict[str, dict[str, str]] = {
    "do_now": {"en": "Do now", "ta": "உடனே செய்ய வேண்டியவை", "hi": "अभी करें", "te": "వెంటనే చేయాల్సినవి",
               "kn": "ತಕ್ಷಣ ಮಾಡಬೇಕಾದವು", "ml": "ഉടൻ ചെയ്യേണ്ടവ", "mr": "आत्ता करा", "bn": "এখনই করুন",
               "gu": "હમણાં કરો", "pa": "ਹੁਣੇ ਕਰੋ", "or": "ବର୍ତ୍ତମାନ କରନ୍ତୁ", "ur": "ابھی کریں"},
    "next_3_days": {"en": "Next 3 days", "ta": "அடுத்த 3 நாட்கள்", "hi": "अगले 3 दिन", "te": "తదుపరి 3 రోజులు",
                    "kn": "ಮುಂದಿನ 3 ದಿನಗಳು", "ml": "അടുത്ത 3 ദിവസം", "mr": "पुढील 3 दिवस", "bn": "পরবর্তী ৩ দিন",
                    "gu": "આગામી 3 દિવસ", "pa": "ਅਗਲੇ 3 ਦਿਨ", "or": "ପରବର୍ତ୍ତୀ 3 ଦିନ", "ur": "اگلے 3 دن"},
    "next_7_days": {"en": "This week", "ta": "இந்த வாரம்", "hi": "इस सप्ताह", "te": "ఈ వారం", "kn": "ಈ ವಾರ",
                    "ml": "ഈ ആഴ്ച", "mr": "या आठवड्यात", "bn": "এই সপ্তাহে", "gu": "આ અઠવાડિયે", "pa": "ਇਸ ਹਫ਼ਤੇ",
                    "or": "ଏହି ସପ୍ତାହ", "ur": "اس ہفتے"},
    "prevention": {"en": "Prevention", "ta": "தடுப்பு முறைகள்", "hi": "रोकथाम", "te": "నివారణ", "kn": "ತಡೆಗಟ್ಟುವಿಕೆ",
                   "ml": "പ്രതിരോധം", "mr": "प्रतिबंध", "bn": "প্রতিরোধ", "gu": "નિવારણ", "pa": "ਰੋਕਥਾਮ",
                   "or": "ପ୍ରତିରୋଧ", "ur": "روک تھام"},
    "safety": {"en": "Safety", "ta": "பாதுகாப்பு", "hi": "सुरक्षा", "te": "భద్రత", "kn": "ಸುರಕ್ಷತೆ", "ml": "സുരക്ഷ",
               "mr": "सुरक्षा", "bn": "নিরাপত্তা", "gu": "સલામતી", "pa": "ਸੁਰੱਖਿਆ", "or": "ସୁରକ୍ଷା", "ur": "حفاظت"},
}

CHAT_SUGGESTIONS: dict[str, list[str]] = {
    "en": ["How do I control this disease organically?", "When should I spray, and how often?",
           "How much water does my crop need now?"],
    "ta": ["இந்த நோயை இயற்கை முறையில் எப்படி கட்டுப்படுத்துவது?", "எப்போது, எத்தனை முறை மருந்து தெளிக்க வேண்டும்?",
           "இப்போது என் பயிருக்கு எவ்வளவு தண்ணீர் தேவை?"],
    "hi": ["इस रोग को जैविक तरीके से कैसे नियंत्रित करें?", "छिड़काव कब और कितनी बार करें?",
           "अभी मेरी फसल को कितना पानी चाहिए?"],
    "te": ["ఈ వ్యాధిని సేంద్రియ పద్ధతిలో ఎలా నియంత్రించాలి?", "ఎప్పుడు, ఎన్నిసార్లు పిచికారీ చేయాలి?",
           "ఇప్పుడు నా పంటకు ఎంత నీరు కావాలి?"],
    "kn": ["ಈ ರೋಗವನ್ನು ಸಾವಯವ ವಿಧಾನದಲ್ಲಿ ಹೇಗೆ ನಿಯಂತ್ರಿಸುವುದು?", "ಯಾವಾಗ ಮತ್ತು ಎಷ್ಟು ಬಾರಿ ಸಿಂಪಡಿಸಬೇಕು?",
           "ಈಗ ನನ್ನ ಬೆಳೆಗೆ ಎಷ್ಟು ನೀರು ಬೇಕು?"],
    "ml": ["ഈ രോഗം ജൈവ രീതിയിൽ എങ്ങനെ നിയന്ത്രിക്കാം?", "എപ്പോൾ, എത്ര തവണ തളിക്കണം?",
           "ഇപ്പോൾ എന്റെ വിളയ്ക്ക് എത്ര വെള്ളം വേണം?"],
    "mr": ["हा रोग सेंद्रिय पद्धतीने कसा नियंत्रित करावा?", "फवारणी केव्हा आणि किती वेळा करावी?",
           "सध्या माझ्या पिकाला किती पाणी लागेल?"],
    "bn": ["এই রোগ জৈব উপায়ে কীভাবে নিয়ন্ত্রণ করব?", "কখন এবং কতবার স্প্রে করব?", "এখন আমার ফসলে কতটা জল দরকার?"],
    "gu": ["આ રોગને સજીવ રીતે કેવી રીતે નિયંત્રિત કરવો?", "છંટકાવ ક્યારે અને કેટલી વાર કરવો?",
           "હાલ મારા પાકને કેટલું પાણી જોઈએ?"],
    "pa": ["ਇਸ ਬਿਮਾਰੀ ਨੂੰ ਜੈਵਿਕ ਤਰੀਕੇ ਨਾਲ ਕਿਵੇਂ ਕਾਬੂ ਕਰੀਏ?", "ਛਿੜਕਾਅ ਕਦੋਂ ਅਤੇ ਕਿੰਨੀ ਵਾਰ ਕਰੀਏ?",
           "ਹੁਣ ਮੇਰੀ ਫ਼ਸਲ ਨੂੰ ਕਿੰਨਾ ਪਾਣੀ ਚਾਹੀਦਾ ਹੈ?"],
    "or": ["ଏହି ରୋଗକୁ ଜୈବିକ ଉପାୟରେ କିପରି ନିୟନ୍ତ୍ରଣ କରିବି?", "କେବେ ଓ କେତେଥର ସ୍ପ୍ରେ କରିବି?",
           "ଏବେ ମୋ ଫସଲକୁ କେତେ ପାଣି ଦରକାର?"],
    "ur": ["اس بیماری کو نامیاتی طریقے سے کیسے قابو کریں؟", "اسپرے کب اور کتنی بار کریں؟", "ابھی میری فصل کو کتنا پانی چاہیے؟"],
}


def normalize(code: str | None) -> str:
    code = (code or "").strip().lower()
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def display_name(code: str) -> str:
    english, native = LANGUAGES[normalize(code)]
    return english if english == native else f"{english} ({native})"


def detect(text: str, preferred: str | None = None) -> str:
    """Language of `text` by script; falls back to `preferred` for Latin text and digits."""
    preferred = normalize(preferred)
    counts = {code: len(re.findall(pattern, text or "")) for code, pattern in _SCRIPTS}
    best = max(counts, key=counts.get)
    if counts[best] == 0:
        return preferred
    if best == "hi" and preferred == "mr":
        return "mr"
    return best


def public_list() -> list[dict]:
    return [{"code": c, "name": e, "native": n, "suggestions": CHAT_SUGGESTIONS[c]} for c, (e, n) in LANGUAGES.items()]


def _foreign_pattern(code: str) -> re.Pattern:
    """Letters of every script that does not belong to `code` (Latin is always allowed:
    crop, chemical and product names often stay in English)."""
    own = {"hi": {"hi"}, "mr": {"hi"}}.get(code, {code})
    return re.compile("|".join(p for c, p in _SCRIPTS if c not in own))


def has_foreign_script(text: str, code: str) -> bool:
    """True when `text` mixes in another Indian/Arabic script, a sign of a garbled LLM line."""
    return bool(_foreign_pattern(normalize(code)).search(text or ""))


def strip_foreign_words(text: str, code: str) -> str:
    """Removes words written in a script that does not belong to `code`."""
    pattern = _foreign_pattern(normalize(code))
    return re.sub(r"[ \t]{2,}", " ", " ".join(w for w in (text or "").split(" ") if not pattern.search(w))).strip()
