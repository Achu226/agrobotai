"""Crop calendar: the usual field tasks by days after sowing / transplanting, saved as farm-diary reminders.

Timings are general guides for Tamil Nadu field crops (TNAU crop production guide style) for a medium-duration
variety. They are approximate: varieties, season and soil change them, so the app says so and the farmer can edit
or delete any reminder. No doses are given here (the fertilizer calculator and the label give those).
"""
from __future__ import annotations

from datetime import date, timedelta

NOTE = {"en": "Approximate dates for a medium-duration variety — adjust to your variety and your agriculture officer's advice.",
        "ta": "இவை நடுத்தர கால ரகத்திற்கான தோராயமான நாட்கள் — உங்கள் ரகம் மற்றும் வேளாண் அலுவலர் ஆலோசனைப்படி மாற்றிக்கொள்ளுங்கள்."}

_BASAL = ("fertilizer", "Basal fertilizer at planting (as per soil test)", "நடவின்போது அடியுரம் (மண் பரிசோதனைப்படி)")
_SCAN = ("note", "Check leaves for disease and pests — scan with AGROBOTAI", "இலைகளில் நோய், பூச்சி உள்ளதா பாருங்கள் — AGROBOTAI-ல் ஸ்கேன் செய்யுங்கள்")

# crop: (days to harvest, [(day, diary kind, English task, Tamil task), ...]); day 0 = sowing / transplanting
CALENDAR: dict[str, tuple[int, list[tuple[int, str, str, str]]]] = {
    "Rice (Paddy)": (120, [
        (0, *_BASAL),
        (15, "weeding", "First hand weeding", "முதல் களை எடுத்தல்"),
        (21, "fertilizer", "First nitrogen top dressing (tillering)", "முதல் மேலுரம் — தழைச்சத்து (தூர் கட்டும் பருவம்)"),
        (30, "weeding", "Second weeding", "இரண்டாம் களை எடுத்தல்"),
        (40, *_SCAN),
        (45, "fertilizer", "Second nitrogen top dressing (panicle initiation)", "இரண்டாம் மேலுரம் (கதிர் உருவாகும் பருவம்)"),
        (70, *_SCAN),
        (110, "irrigation", "Stop irrigation about 10 days before harvest", "அறுவடைக்கு 10 நாள் முன் நீர் பாய்ச்சுவதை நிறுத்துங்கள்"),
        (120, "harvest", "Harvest when 80% of grains turn golden", "80% நெல்மணிகள் பொன்னிறமானதும் அறுவடை"),
    ]),
    "Tomato": (120, [
        (0, *_BASAL),
        (3, "irrigation", "Life irrigation after transplanting", "நடவுக்குப் பின் உயிர்த் தண்ணீர்"),
        (25, "weeding", "Weeding and earthing up", "களை எடுத்து மண் அணைத்தல்"),
        (30, "fertilizer", "First top dressing", "முதல் மேலுரம்"),
        (35, "note", "Stake the plants", "செடிகளுக்குக் குச்சி நட்டு கட்டுதல்"),
        (45, *_SCAN),
        (60, "fertilizer", "Second top dressing (flowering)", "இரண்டாம் மேலுரம் (பூக்கும் பருவம்)"),
        (70, "harvest", "First picking — then every 4–5 days", "முதல் பறிப்பு — பின் 4–5 நாளுக்கு ஒருமுறை"),
    ]),
    "Potato": (100, [
        (0, *_BASAL),
        (25, "weeding", "Weeding", "களை எடுத்தல்"),
        (30, "fertilizer", "Top dressing and earthing up", "மேலுரம் இட்டு மண் அணைத்தல்"),
        (45, *_SCAN),
        (60, "weeding", "Second earthing up", "இரண்டாம் மண் அணைத்தல்"),
        (85, "irrigation", "Stop irrigation; cut the haulms 10 days before harvest", "நீர் நிறுத்தி, அறுவடைக்கு 10 நாள் முன் தண்டுகளை வெட்டுங்கள்"),
        (100, "harvest", "Harvest the tubers", "கிழங்கு அறுவடை"),
    ]),
    "Bell Pepper": (150, [
        (0, *_BASAL),
        (30, "weeding", "Weeding and earthing up", "களை எடுத்து மண் அணைத்தல்"),
        (30, "fertilizer", "First top dressing", "முதல் மேலுரம்"),
        (45, *_SCAN),
        (60, "fertilizer", "Second top dressing", "இரண்டாம் மேலுரம்"),
        (75, "harvest", "First picking", "முதல் பறிப்பு"),
    ]),
    "Green Chilli": (150, [
        (0, *_BASAL),
        (30, "weeding", "Weeding and earthing up", "களை எடுத்து மண் அணைத்தல்"),
        (30, "fertilizer", "First top dressing", "முதல் மேலுரம்"),
        (45, *_SCAN),
        (60, "fertilizer", "Second top dressing", "இரண்டாம் மேலுரம்"),
        (75, "harvest", "First picking of green chillies", "முதல் பச்சை மிளகாய் பறிப்பு"),
    ]),
    "Brinjal": (150, [
        (0, *_BASAL),
        (30, "weeding", "Weeding and earthing up", "களை எடுத்து மண் அணைத்தல்"),
        (30, "fertilizer", "First top dressing", "முதல் மேலுரம்"),
        (40, *_SCAN),
        (60, "fertilizer", "Second top dressing", "இரண்டாம் மேலுரம்"),
        (60, "harvest", "First picking — then every 4–5 days", "முதல் பறிப்பு — பின் 4–5 நாளுக்கு ஒருமுறை"),
    ]),
    "Corn (Maize)": (105, [
        (0, *_BASAL),
        (18, "weeding", "Hand weeding", "களை எடுத்தல்"),
        (25, "fertilizer", "First nitrogen top dressing", "முதல் தழைச்சத்து மேலுரம்"),
        (35, *_SCAN),
        (45, "fertilizer", "Second nitrogen top dressing", "இரண்டாம் தழைச்சத்து மேலுரம்"),
        (55, "irrigation", "Do not miss irrigation at tasselling and silking", "ஆண் பூ, பட்டு வரும் பருவத்தில் நீர் தவறாமல் பாய்ச்சுங்கள்"),
        (105, "harvest", "Harvest when the husk dries and grains are hard", "மேல் தோல் காய்ந்து மணிகள் கடினமானதும் அறுவடை"),
    ]),
    "Soybean": (95, [
        (0, *_BASAL),
        (20, "weeding", "First weeding", "முதல் களை எடுத்தல்"),
        (35, "weeding", "Second weeding", "இரண்டாம் களை எடுத்தல்"),
        (40, *_SCAN),
        (50, "irrigation", "Irrigate at flowering and pod filling", "பூக்கும், காய் பிடிக்கும் பருவத்தில் நீர் பாய்ச்சுங்கள்"),
        (95, "harvest", "Harvest when most pods turn brown", "பெரும்பாலான காய்கள் பழுப்பானதும் அறுவடை"),
    ]),
    "Cotton": (160, [
        (0, *_BASAL),
        (20, "weeding", "Thinning and first weeding", "பயிர் களைதல், முதல் களை எடுத்தல்"),
        (40, "fertilizer", "Nitrogen top dressing", "தழைச்சத்து மேலுரம்"),
        (45, "weeding", "Second weeding and earthing up", "இரண்டாம் களை, மண் அணைத்தல்"),
        (60, *_SCAN),
        (130, "harvest", "First picking of open bolls", "வெடித்த காய்களின் முதல் பஞ்சு எடுப்பு"),
    ]),
    "Banana": (330, [
        (0, *_BASAL),
        (90, "fertilizer", "Fertilizer (3rd month)", "உரம் (3-வது மாதம்)"),
        (150, "fertilizer", "Fertilizer (5th month)", "உரம் (5-வது மாதம்)"),
        (150, *_SCAN),
        (210, "fertilizer", "Fertilizer (7th month)", "உரம் (7-வது மாதம்)"),
        (240, "note", "Remove extra suckers; prop the plants", "தேவையற்ற பக்கக் கன்றுகளை அகற்றி, முட்டுக் கொடுங்கள்"),
        (330, "harvest", "Harvest when the fingers are well filled", "காய்கள் நன்கு திரண்டதும் அறுவடை"),
    ]),
}


def plan(crop: str, sown_on: date, language: str = "en") -> dict:
    """Dated tasks for a crop sown/transplanted on `sown_on`. Raises KeyError for a crop without a calendar."""
    days, stages = CALENDAR[crop]
    ta = language == "ta"
    return {
        "crop": crop, "sown_on": sown_on.isoformat(), "harvest_on": (sown_on + timedelta(days=days)).isoformat(),
        "note": NOTE["ta" if ta else "en"],
        "tasks": [{"day": d, "date": (sown_on + timedelta(days=d)).isoformat(), "kind": kind, "task": t_ta if ta else t_en}
                  for d, kind, t_en, t_ta in stages],
    }
