"""
Disease & pest library for farmers: the verified fact sheets in `agri_knowledge.py`, in the farmer's language.

English is the source. Other languages are translated once by the local LLM (farm_advisor) and cached in
outputs/library_cache/<lang>.json; a translation that fails falls back to the English text, marked as such.
"""
from __future__ import annotations

import json
import re
import threading

from src import agri_knowledge, config, farm_advisor, languages
from src.library_curated import CURATED

CACHE_DIR = config.OUTPUTS_DIR / "library_cache"
_lock = threading.Lock()


def _crop(label: str) -> str:
    from src.config import crop_of_disease_label

    return crop_of_disease_label(label) or "Other"


def entries() -> list[dict]:
    """All library entries in English (the source of truth)."""
    out = []
    deployed = set(config.DISEASE_CLASSES.values())
    for label, facts in agri_knowledge.DISEASE_FACTS.items():
        if label not in deployed:  # only what the deployed model can actually recognise
            continue
        out.append({"key": label, "kind": "healthy" if label.endswith("healthy") else "disease", "crop": _crop(label),
                    "name": config.DISEASE_DISPLAY_NAMES.get(label, label), "facts": facts})
    for label, facts in agri_knowledge.PEST_FACTS.items():
        out.append({"key": label, "kind": "pest", "crop": None,
                    "name": config.PEST_DISPLAY_NAMES.get(label, label), "facts": facts})
    return out


def _cache_path(code: str):
    return CACHE_DIR / f"{code}.json"


def _load(code: str) -> dict:
    try:
        return json.loads(_cache_path(code).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(code: str, cache: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(code).write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


TRANSLATE_PROMPT = """Translate this crop-protection fact sheet for farmers from English into {language}.
Rules: keep the meaning exactly; do not add or drop any advice; keep Latin pathogen names, "Bt", product types and
numbers as they are; use simple words. {language_rule}
Return only JSON with the same keys: {{"name": "...", "facts": ["...", ...]}} with the same number of facts."""


def _translate(entry: dict, code: str) -> dict | None:
    messages = [
        {"role": "system", "content": TRANSLATE_PROMPT.format(language=languages.display_name(code),
                                                             language_rule=farm_advisor._language_rule(code))},
        {"role": "user", "content": json.dumps({"name": entry["name"], "facts": entry["facts"]}, ensure_ascii=False)},
    ]
    try:
        content, model = farm_advisor._complete(messages, max_tokens=1500, json_mode=True)
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        data = json.loads(match.group(0) if match else content)
        facts = [str(f).strip() for f in data.get("facts") or []]
        name = str(data.get("name") or "").strip()
    except (farm_advisor.AdvisorUnavailable, ValueError, AttributeError):
        return None
    # A translation that lost facts or mixes scripts is not shown to farmers
    if len(facts) != len(entry["facts"]) or not name or any(languages.has_foreign_script(t, code) for t in [name, *facts]):
        return None
    return {"name": name, "facts": facts, "model": model}


def localized(code: str, translate_missing: bool, keys: set[str] | None = None) -> list[dict]:
    """Entries in `code`. Missing translations are made (and cached) only when `translate_missing`."""
    code = languages.normalize(code)
    items = [e for e in entries() if keys is None or e["key"] in keys]
    if code == "en":
        return [e | {"language": "en", "translated": False} for e in items]
    curated = CURATED.get(code, {})
    with _lock:
        cache = _load(code)
        changed = False
        out = []
        for e in items:
            if e["key"] in curated:  # hand-written translation always wins
                name, facts = curated[e["key"]]
                out.append(e | {"name": name, "facts": facts, "english_name": e["name"], "english_facts": e["facts"],
                                "language": code, "translated": True, "reviewed": True})
                continue
            t = cache.get(e["key"])
            if t is None and translate_missing:
                t = _translate(e, code)
                if t:
                    cache[e["key"]] = t
                    changed = True
            if t:
                out.append(e | {"name": t["name"], "facts": t["facts"], "english_name": e["name"],
                                "english_facts": e["facts"], "language": code, "translated": True, "reviewed": False})
            else:
                out.append(e | {"language": "en", "translated": False})
        if changed:
            _save(code, cache)
    return out
