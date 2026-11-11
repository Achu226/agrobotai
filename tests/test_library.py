import json

import pytest
from fastapi.testclient import TestClient

import server
from src import agri_knowledge, farm_advisor, languages, library
from src.library_curated import TA
from tests.conftest import LAN_PHONE
from tests.test_api_v1 import _register

TYLCV = "Tomato__Tomato_YellowLeaf__Curl_Virus"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "CACHE_DIR", tmp_path / "library_cache")


def _llm(monkeypatch, reply):
    calls = []

    def fake(messages, max_tokens, json_mode=False):
        calls.append(json.loads(messages[1]["content"]))
        return reply(calls[-1]), "gemma3:4b"

    monkeypatch.setattr(farm_advisor, "_complete", fake)
    return calls


def test_library_has_every_deployed_disease_and_every_pest():
    from src import config

    keys = {e["key"] for e in library.entries()}
    deployed = set(config.DISEASE_CLASSES.values()) - {config.OTHER_PLANT_CLASS}
    # Only diseases the deployed model can recognise (facts for the 48-class model stay hidden until it is deployed)
    assert keys == (set(agri_knowledge.DISEASE_FACTS) & deployed) | set(agri_knowledge.PEST_FACTS)
    assert deployed <= set(agri_knowledge.DISEASE_FACTS)  # every recognisable disease has facts
    tylcv = next(e for e in library.entries() if e["key"] == TYLCV)
    assert tylcv["kind"] == "disease" and tylcv["crop"] == "Tomato"


def test_reviewed_tamil_covers_every_entry_fact_for_fact(monkeypatch):
    calls = _llm(monkeypatch, lambda src: "{}")
    english = {e["key"]: e for e in library.entries()}
    # Hand-written Tamil for every original entry and for the Tamil Nadu crops (rice, banana) of the 48-class model;
    # the other added crops use the labelled machine translation
    must = {k for k in english if not k.split("_")[0] in ("Apple", "Blueberry", "Cherry", "Grape", "Maize", "Orange",
                                                         "Peach", "Raspberry", "Soybean", "Squash", "Strawberry")}
    assert must <= set(TA) <= set(english) | set(agri_knowledge.DISEASE_FACTS)  # Tamil may wait for its model
    for key, (name, facts) in TA.items():
        if key in english:
            assert len(facts) == len(english[key]["facts"]), key
        assert not any(languages.has_foreign_script(t, "ta") for t in [name, *facts]), key
    entries = library.localized("ta", translate_missing=False)
    assert all(e["reviewed"] and e["language"] == "ta" for e in entries if e["key"] in must) and calls == []


def test_translation_is_cached_and_keeps_english_original(monkeypatch):
    calls = _llm(monkeypatch, lambda src: json.dumps(
        {"name": "टमाटर पीला पत्ता मोड़ वायरस", "facts": ["तथ्य"] * len(src["facts"])}, ensure_ascii=False))
    first = library.localized("hi", True, {TYLCV})[0]
    again = library.localized("hi", True, {TYLCV})[0]
    assert len(calls) == 1
    assert first["translated"] and not first["reviewed"] and first["name"] == "टमाटर पीला पत्ता मोड़ वायरस" == again["name"]
    assert first["english_facts"] == agri_knowledge.DISEASE_FACTS[TYLCV]


@pytest.mark.parametrize("reply", [
    lambda src: json.dumps({"name": "नाम", "facts": ["एक"]}, ensure_ascii=False),  # facts dropped
    lambda src: json.dumps({"name": "नाम محلول", "facts": ["x"] * len(src["facts"])}, ensure_ascii=False),  # mixed script
    lambda src: "not json",
])
def test_bad_translations_fall_back_to_english(monkeypatch, reply):
    _llm(monkeypatch, reply)
    e = library.localized("hi", True, {TYLCV})[0]
    assert e["translated"] is False and e["facts"] == agri_knowledge.DISEASE_FACTS[TYLCV]


def test_list_never_calls_the_llm(monkeypatch):
    calls = _llm(monkeypatch, lambda src: "{}")
    assert all(not e["translated"] for e in library.localized("hi", translate_missing=False))
    assert calls == []


def test_library_endpoints(monkeypatch):
    phone = TestClient(server.app, client=LAN_PHONE)
    headers, _ = _register(phone)
    _llm(monkeypatch, lambda src: json.dumps({"name": "माहू", "facts": ["त"] * len(src["facts"])}, ensure_ascii=False))
    from src import config

    deployed = set(config.DISEASE_CLASSES.values()) - {config.OTHER_PLANT_CLASS}
    assert len(phone.get("/api/v1/library?language=ta", headers=headers).json()["entries"]) == len(deployed) + len(agri_knowledge.PEST_FACTS)
    assert phone.get("/api/v1/library/aphids?language=ta", headers=headers).json()["entry"]["name"] == "அசுவினி"
    entry = phone.get("/api/v1/library/aphids?language=hi", headers=headers).json()["entry"]
    assert entry["name"] == "माहू" and entry["kind"] == "pest"
    assert phone.get("/api/v1/library/nonsense?language=ta", headers=headers).status_code == 404
    assert phone.get("/api/v1/library?language=ta").status_code == 401
