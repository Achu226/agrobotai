"""
Farmer advice and chat in 12 languages, using the local LLM (Ollama, OpenAI-compatible API).

- advise_scan(): turns one stored scan result (+ live sensor readings, if any) into a short advice
  card in the farmer's language. The LLM only explains findings it is given; it never adds new ones.
- chat(): answers a farmer's question in the language they typed (script detection) or chose.

Nothing is invented when the LLM is down: advice falls back to a small, clearly labelled rule book,
and chat reports that the advisor is offline instead of producing a canned answer.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

from src import agri_knowledge, config, languages

ADVICE_KEYS = ("do_now", "next_3_days", "next_7_days", "prevention", "safety")
ADVICE_TIMEOUT_SECONDS = float(getattr(config, "ADVICE_TIMEOUT_SECONDS", 240))


class AdvisorUnavailable(RuntimeError):
    """The local LLM could not be reached or returned nothing usable."""


# Keep the model loaded in GPU memory between questions. Ollama's default (5 min) meant the first
# question after a pause waited ~20 s for the model to reload.
KEEP_ALIVE = "24h"


def _ollama_url(base: str | None = None) -> str:
    base = (base or config.OPENAI_BASE_URL or "http://localhost:11434/v1").rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def _payload(model: str, messages: list[dict], max_tokens: int, stream: bool, json_mode: bool = False,
             keep_alive: str = KEEP_ALIVE) -> dict:
    body = {"model": model, "messages": messages, "stream": stream, "keep_alive": keep_alive,
            "options": {"temperature": 0.3, "num_predict": max_tokens, "num_ctx": 4096}}
    if json_mode:
        body["format"] = "json"
    return body


def _models() -> list[str]:
    # ADVISOR_MODEL (gemma3:4b writes good Tamil/Hindi) first; the older model if it is not installed
    return list(dict.fromkeys(m for m in (config.ADVISOR_MODEL, config.OPENAI_MODEL, "agri-qwen:7b") if m))


def _targets() -> list[tuple[str, list[str], str]]:
    """(Ollama URL, models, keep_alive) in order: the main advisor, then the optional fallback.
    On the Raspberry Pi the main advisor is the laptop's gemma3:4b and the fallback the Pi's own small
    model, unloaded after 2 minutes so it does not hold the Pi's RAM."""
    targets = [(_ollama_url(), _models(), KEEP_ALIVE)]
    if config.ADVISOR_FALLBACK_URL and config.ADVISOR_FALLBACK_MODEL:
        targets.append((_ollama_url(config.ADVISOR_FALLBACK_URL), [config.ADVISOR_FALLBACK_MODEL], "2m"))
    return targets


def _timeout():
    # Short connect timeout: a switched-off laptop hands over to the fallback in seconds, not minutes
    import httpx

    return httpx.Timeout(ADVICE_TIMEOUT_SECONDS, connect=3)


def _complete(messages: list[dict], max_tokens: int, json_mode: bool = False) -> tuple[str, str]:
    """One full answer from Ollama's native API (keeps the model resident via keep_alive)."""
    import httpx

    errors = []
    for url, models, keep_alive in _targets():
        for model in models:
            try:
                res = httpx.post(f"{url}/api/chat", json=_payload(model, messages, max_tokens, False, json_mode, keep_alive),
                                 timeout=_timeout())
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:  # that machine is off or unreachable: try the fallback
                errors.append(f"{url}: {exc}")
                break
            except httpx.HTTPError as exc:  # reached it, but it failed or timed out mid-answer
                raise AdvisorUnavailable(f"Local AI advisor unavailable: {exc}") from exc
            if res.status_code == 404:  # model not pulled in Ollama: try the next one
                errors.append(f"{model} not installed")
                continue
            if res.status_code >= 400:
                raise AdvisorUnavailable(f"Local AI advisor error {res.status_code}: {res.text[:200]}")
            content = (res.json().get("message") or {}).get("content") or ""
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            if not content:
                raise AdvisorUnavailable("Local AI advisor returned an empty answer.")
            return content, model
    raise AdvisorUnavailable(f"Local AI advisor unavailable: {'; '.join(errors)}")


def _stream(messages: list[dict], max_tokens: int):
    """Yields (model, text_piece) as Ollama generates, so the phone can show words immediately."""
    import httpx

    errors = []
    for url, models, keep_alive in _targets():
        for model in models:
            try:
                with httpx.stream("POST", f"{url}/api/chat", json=_payload(model, messages, max_tokens, True, keep_alive=keep_alive),
                                  timeout=_timeout()) as res:
                    if res.status_code == 404:
                        errors.append(f"{model} not installed")
                        continue
                    if res.status_code >= 400:
                        raise AdvisorUnavailable(f"Local AI advisor error {res.status_code}: {res.read()[:200]!r}")
                    for line in res.iter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        if chunk.get("error"):
                            raise AdvisorUnavailable(f"Local AI advisor error: {chunk['error']}")
                        piece = (chunk.get("message") or {}).get("content") or ""
                        if piece:
                            yield model, piece
                        if chunk.get("done"):
                            return
                    return
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:  # that machine is off or unreachable: try the fallback
                errors.append(f"{url}: {exc}")
                break
            except httpx.HTTPError as exc:
                raise AdvisorUnavailable(f"Local AI advisor unavailable: {exc}") from exc
    raise AdvisorUnavailable(f"Local AI advisor unavailable: {'; '.join(errors)}")


# ---------------------------------------------------------------- facts given to the LLM

def sensor_facts(devices: list[dict] | None) -> list[dict] | str:
    """Only real, recent readings are passed on; stale devices are reported as such."""
    if not devices:
        return "no sensor connected"
    now = datetime.now(timezone.utc)
    out = []
    for d in devices:
        age_min = int((now - datetime.fromisoformat(d["received_at"])).total_seconds() // 60)
        if age_min * 60 > config.SENSOR_STALE_SECONDS:
            out.append({"device": d["device_id"], "status": f"offline (last reading {age_min} min ago) - do not use"})
        else:
            out.append({"device": d["device_id"], "minutes_old": age_min,
                        "readings": {k: v for k, v in d["readings"].items() if v is not None}})
    return out


def scan_facts(result: dict, sensors: list[dict] | None = None) -> dict:
    disease, pest = result.get("disease") or {}, result.get("pest") or {}
    severity = result.get("severity") or {}
    return {
        "crop": (result.get("crop") or {}).get("reported") or (result.get("crop") or {}).get("selected") or "unknown",
        "overall": (result.get("summary") or {}).get("state"),
        "disease": {"state": disease.get("state"), "name": disease.get("display_name") if disease.get("label") else None,
                    "confidence_pct": disease.get("calibrated_confidence")},
        "pest": {"state": pest.get("state"), "name": pest.get("display_name") if pest.get("label") else None,
                 "confidence_pct": pest.get("calibrated_confidence")},
        "affected_leaf_area_pct": severity.get("affected_pct"),
        "severity_stage": severity.get("stage"),
        "health_index_0_100": (result.get("health_index") or {}).get("value"),
        "field_sensors": sensor_facts(sensors),
        "reference_facts": agri_knowledge.facts_for(disease.get("label"), pest.get("label")),
    }


def _language_rule(code: str) -> str:
    name = languages.display_name(code)
    return (f"Write EVERY sentence in {name}, using its own script, in simple words a farmer understands. "
            f"Do not answer in English unless the language is English. Disease, pest, crop, chemical and product "
            f"names stay in English (do not translate them).")


# ---------------------------------------------------------------- scan advice

ADVICE_PROMPT = """You are AGROBOTAI, a crop advisor for Indian smallholder farmers.
You receive the findings of an image analysis (and live field sensor readings, if any) as JSON.
Rules:
- Explain only the findings given. Never invent a disease, pest, number, or sensor value.
- Base every recommendation on "reference_facts" and never contradict them (for example, never suggest
  a fungicide for a virus). Prefer concrete actions from the facts over vague ones like "monitor".
- A finding with state "uncertain" or "possible_pest" is NOT confirmed: say it must be checked in the field.
- Use sensor readings only when they are present and not marked offline.
- For chemicals, name the active ingredient type and say to follow the product label and the local
  agriculture officer. Do not invent doses or pre-harvest intervals.
- {language_rule}
Return only JSON with exactly these English keys (values in the farmer's language):
{{"headline": "one short line", "farmer_message": "2-3 sentences",
 "do_now": ["max 4 items"], "next_3_days": ["max 3"], "next_7_days": ["max 3"],
 "prevention": ["max 3"], "safety": ["max 2"]}}"""

# Rule book used only when the LLM is offline. English and Tamil; other languages get English.
_RULE_BOOK = {
    "en": {
        "headline": "AI advisor offline - basic guidance only",
        "farmer_message": "The laptop's AI advisor is not running, so this is general guidance, not advice written for this scan.",
        "do_now": ["Remove and destroy badly affected leaves; do not compost them.",
                   "Check the underside of leaves on nearby plants for spots or insects."],
        "next_3_days": ["Water at the base in the morning; keep leaves dry."],
        "next_7_days": ["Scan new leaves again to see whether symptoms spread."],
        "prevention": ["Keep spacing between plants for air flow.", "Clean tools after working on sick plants."],
        "safety": ["Before any spray, ask the local agriculture officer and follow the product label."],
    },
    "ta": {
        "headline": "AI ஆலோசகர் இயங்கவில்லை - பொதுவான வழிகாட்டல் மட்டும்",
        "farmer_message": "லேப்டாப்பில் AI ஆலோசகர் இயங்கவில்லை. இது இந்த ஸ்கேனுக்கான ஆலோசனை அல்ல, பொதுவான வழிகாட்டல் மட்டுமே.",
        "do_now": ["அதிகம் பாதிக்கப்பட்ட இலைகளை அகற்றி அழிக்கவும்; உரக்குழியில் போட வேண்டாம்.",
                   "அருகிலுள்ள செடிகளின் இலைகளின் அடிப்பகுதியில் புள்ளிகள் அல்லது பூச்சிகள் உள்ளதா என பார்க்கவும்."],
        "next_3_days": ["காலையில் செடியின் அடியில் மட்டும் நீர் பாய்ச்சவும்; இலைகளை நனைக்க வேண்டாம்."],
        "next_7_days": ["புதிய இலைகளை மீண்டும் ஸ்கேன் செய்து நோய் பரவுகிறதா என பார்க்கவும்."],
        "prevention": ["காற்றோட்டத்திற்கு செடிகளுக்கு இடையே இடைவெளி விடவும்.",
                       "நோயுற்ற செடிகளில் வேலை செய்த பின் கருவிகளை சுத்தம் செய்யவும்."],
        "safety": ["மருந்து தெளிப்பதற்கு முன் வட்டார வேளாண்மை அலுவலரை அணுகி, லேபிளில் உள்ள அறிவுரையை பின்பற்றவும்."],
    },
}


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _card(data: dict, code: str, source: str, model: str | None, elapsed_s: float, error: str | None = None) -> dict:
    # Small models sometimes slip words from another script into a line (seen: Arabic inside Tamil);
    # such lines are garbled, so they are dropped rather than shown to the farmer.
    sections = [{"key": k, "title": languages.ADVICE_SECTION_TITLES[k][code],
                 "items": [i for i in _as_list(data.get(k)) if not languages.has_foreign_script(i, code)]}
                for k in ADVICE_KEYS]
    by_key = {s["key"]: s["items"] for s in sections}
    return {
        "state": "generated",
        "language": code,
        "source": source,
        "model": model,
        "error": error,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "elapsed_s": round(elapsed_s, 1),
        "headline": languages.strip_foreign_words(str(data.get("headline") or ""), code),
        "farmer_message": languages.strip_foreign_words(str(data.get("farmer_message") or ""), code),
        "sections": [s for s in sections if s["items"]],
        # Older app versions read these flat lists
        "immediate_actions": by_key["do_now"],
        "next_24_48_hours": by_key["next_3_days"],
        "next_7_days": by_key["next_7_days"],
        "prevention": by_key["prevention"],
        "warnings": by_key["safety"],
    }


def advise_scan(result: dict, language: str, sensors: list[dict] | None = None) -> dict:
    code = languages.normalize(language)
    started = time.perf_counter()
    messages = [
        {"role": "system", "content": ADVICE_PROMPT.format(language_rule=_language_rule(code))},
        {"role": "user", "content": json.dumps(scan_facts(result, sensors), ensure_ascii=False)},
    ]
    try:
        content, model = _complete(messages, max_tokens=1400, json_mode=True)
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        data = json.loads(match.group(0) if match else content)
        if not any(_as_list(data.get(k)) for k in ADVICE_KEYS):
            raise AdvisorUnavailable("Local AI advisor returned no advice items.")
        return _card(data, code, "local_llm", model, time.perf_counter() - started)
    except (AdvisorUnavailable, json.JSONDecodeError, ValueError) as exc:
        book_lang = code if code in _RULE_BOOK else "en"
        card = _card(_RULE_BOOK[book_lang], code, "rule_book_offline", None, time.perf_counter() - started, str(exc))
        if book_lang != code:
            card["note"] = "Rule book is available in English and Tamil only."
        return card


# ---------------------------------------------------------------- chat

CHAT_PROMPT = """You are AGROBOTAI, a friendly crop advisor for Indian smallholder farmers.
Answer the farmer's question practically, in at most 6 short sentences or bullet points.
- Start directly with the answer. No greetings, no "Namaste", no repeating the question.
- {language_rule}
- If "latest_scan" is given, the farmer is asking about that crop and finding: name it and answer for it.
- Write disease and pest names exactly as given in the facts (English); do not translate them.
- If the scan's overall state is "uncertain" (or a finding is "uncertain"/"possible_pest"), say clearly that
  the photo did not give a confirmed diagnosis, suggest retaking a clear close-up, and give only general care.
- If you are not sure, say so and suggest asking the local agriculture officer (KVK).
- Never invent sensor values, test results or diagnoses. Use only the facts below when you refer to them.
- When "reference_facts" are given, your answer must agree with them (e.g. never suggest a fungicide for a virus).
- For chemicals, name the active ingredient type and say to follow the product label; do not invent doses.
Facts about this farmer's field (may be empty):
{facts}"""


CHAT_MAX_TOKENS = 450


def _chat_messages(message: str, code: str, history: list[dict] | None, scan_result: dict | None,
                   sensors: list[dict] | None) -> list[dict]:
    facts = {"latest_scan": scan_facts(scan_result) if scan_result else "none",
             "field_sensors": sensor_facts(sensors)}
    messages = [{"role": "system", "content": CHAT_PROMPT.format(language_rule=_language_rule(code),
                                                                 facts=json.dumps(facts, ensure_ascii=False))}]
    for turn in (history or [])[-8:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": str(turn["content"])[:2000]})
    messages.append({"role": "user", "content": message})
    return messages


def _clean(text: str, code: str) -> str:
    """Drops foreign-script words line by line, keeping the surrounding spaces/newlines intact
    (streamed chunks are joined back together, so their edges matter)."""
    def one(line: str) -> str:
        if not line.strip():
            return line
        lead = line[: len(line) - len(line.lstrip())]
        trail = line[len(line.rstrip()):]
        return lead + languages.strip_foreign_words(line, code) + trail

    return "\n".join(one(line) for line in text.split("\n"))


def chat(message: str, language: str | None, history: list[dict] | None = None,
         scan_result: dict | None = None, sensors: list[dict] | None = None) -> dict:
    code = languages.detect(message, languages.normalize(language))
    started = time.perf_counter()
    answer, model = _complete(_chat_messages(message, code, history, scan_result, sensors), max_tokens=CHAT_MAX_TOKENS)
    return {"answer": _clean(answer, code).strip(), "language": code, "language_name": languages.display_name(code),
            "source": "local_llm", "model": model, "elapsed_s": round(time.perf_counter() - started, 1)}


def chat_stream(message: str, language: str | None, history: list[dict] | None = None,
                scan_result: dict | None = None, sensors: list[dict] | None = None):
    """Yields events: {"type": "start", ...}, {"type": "delta", "text"}..., {"type": "done", ...}.

    Text is released at word boundaries so foreign-script words can still be filtered out.
    Raises AdvisorUnavailable before the first event when the LLM is not reachable.
    """
    code = languages.detect(message, languages.normalize(language))
    started = time.perf_counter()
    pieces = _stream(_chat_messages(message, code, history, scan_result, sensors), CHAT_MAX_TOKENS)
    first = next(pieces, None)  # surface connection errors before anything is sent
    if first is None:
        raise AdvisorUnavailable("Local AI advisor returned an empty answer.")
    model = first[0]
    first_token_s = round(time.perf_counter() - started, 2)
    yield {"type": "start", "language": code, "language_name": languages.display_name(code), "model": model}
    buffer, full = first[1], []
    for _, piece in pieces:
        buffer += piece
        cut = max(buffer.rfind(" "), buffer.rfind("\n"))
        if cut > 0:
            out = _clean(buffer[:cut + 1], code)
            buffer = buffer[cut + 1:]
            if out:
                full.append(out)
                yield {"type": "delta", "text": out}
    out = _clean(buffer, code)
    if out:
        full.append(out)
        yield {"type": "delta", "text": out}
    yield {"type": "done", "answer": "".join(full).strip(), "language": code,
           "language_name": languages.display_name(code), "source": "local_llm", "model": model,
           "first_token_s": first_token_s, "elapsed_s": round(time.perf_counter() - started, 1)}
