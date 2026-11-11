import json

import pytest
from fastapi.testclient import TestClient

import server
from src import config, farm_advisor, languages, store
from tests.conftest import LAN_PHONE
from tests.test_api_v1 import _analyze, _install_both, _register

TYLCV = "Tomato__Tomato_YellowLeaf__Curl_Virus"


@pytest.fixture()
def phone():
    return TestClient(server.app, client=LAN_PHONE)


def _llm_returns(monkeypatch, content, calls=None):
    def fake(messages, max_tokens, json_mode=False):
        if calls is not None:
            calls.append(messages)
        return content, "gemma3:4b"

    monkeypatch.setattr(farm_advisor, "_complete", fake)


def _llm_down(monkeypatch):
    def fake(*a, **k):
        raise farm_advisor.AdvisorUnavailable("Local AI advisor unavailable: connection refused")

    monkeypatch.setattr(farm_advisor, "_complete", fake)


def _result(label=TYLCV):
    return {"summary": {"state": "disease_detected"}, "crop": {"reported": "Tomato"},
            "disease": {"state": "disease_detected", "label": label, "display_name": "Tomato Yellow Leaf Curl Virus",
                        "calibrated_confidence": 99.9},
            "pest": {"state": "no_pest_detected", "label": None}, "severity": {"affected_pct": 5.5}}


# ---------------------------------------------------------------- languages

def test_twelve_languages_with_titles_and_suggestions():
    assert len(languages.LANGUAGES) == 12
    for code in languages.LANGUAGES:
        assert all(code in titles for titles in languages.ADVICE_SECTION_TITLES.values())
        assert languages.CHAT_SUGGESTIONS[code]


@pytest.mark.parametrize("text, preferred, expected", [
    ("இலை சுருள் நோய்", "en", "ta"),
    ("ఆకు మచ్చ", "ta", "te"),
    ("पत्ते पीले हैं", "ta", "hi"),
    ("पाने पिवळी", "mr", "mr"),
    ("how do I spray", "ta", "ta"),  # Latin text: answer in the chosen language
    ("پتے پیلے ہیں", "en", "ur"),
])
def test_language_detected_from_script(text, preferred, expected):
    assert languages.detect(text, preferred) == expected


def test_mixed_script_lines_are_detected_and_cleaned():
    assert languages.has_foreign_script("நிற محلول நீரில் தெளிக்கவும்", "ta")
    assert not languages.has_foreign_script("வேப்ப எண்ணெய் (neem oil) தெளிக்கவும்", "ta")
    assert languages.strip_foreign_words("KVK (कृषि केंद्र) அணுகவும்", "ta") == "KVK அணுகவும்"


# ---------------------------------------------------------------- scan advice

def test_advice_card_in_tamil_drops_garbled_lines(monkeypatch):
    calls = []
    _llm_returns(monkeypatch, json.dumps({
        "headline": "தக்காளி இலை சுருள் வைரஸ்", "farmer_message": "பாதிக்கப்பட்ட செடிகளை அகற்றவும்.",
        "do_now": ["பாதிக்கப்பட்ட செடிகளை அகற்றவும்", "நிற محلول நீரில் தெளிக்கவும்"],
        "next_3_days": ["மஞ்சள் ஒட்டும் பொறிகள் வைக்கவும்"], "next_7_days": [], "prevention": [], "safety": []},
        ensure_ascii=False), calls)
    card = farm_advisor.advise_scan(_result(), "ta")
    assert card["source"] == "local_llm" and card["language"] == "ta"
    assert card["sections"][0]["title"] == "உடனே செய்ய வேண்டியவை"
    assert card["sections"][0]["items"] == ["பாதிக்கப்பட்ட செடிகளை அகற்றவும்"]  # the Arabic-mixed line is gone
    assert card["immediate_actions"] == card["sections"][0]["items"]  # flat lists for older apps
    # The LLM was told the language and given the verified virus facts
    system, user = calls[0][0]["content"], json.loads(calls[0][1]["content"])
    assert "Tamil" in system
    assert any("do NOT work" in fact for fact in user["reference_facts"][TYLCV])


def test_advice_falls_back_to_labelled_rule_book_when_llm_down(monkeypatch):
    _llm_down(monkeypatch)
    ta = farm_advisor.advise_scan(_result(), "ta")
    assert ta["source"] == "rule_book_offline" and "connection refused" in ta["error"]
    assert ta["sections"][0]["title"] == "உடனே செய்ய வேண்டியவை"
    te = farm_advisor.advise_scan(_result(), "te")
    assert te["source"] == "rule_book_offline" and "English and Tamil" in te["note"]


def test_only_fresh_sensor_readings_reach_the_advisor(monkeypatch):
    monkeypatch.setattr(config, "SENSOR_STALE_SECONDS", 300)
    fresh = {"device_id": "pi-1", "received_at": store.now_iso(), "readings": {"soil_moisture_pct": 31.0, "soil_ph": None}}
    old = {"device_id": "pi-2", "received_at": "2020-01-01T00:00:00+05:30", "readings": {"soil_moisture_pct": 90.0}}
    facts = farm_advisor.sensor_facts([fresh, old])
    assert facts[0]["readings"] == {"soil_moisture_pct": 31.0}
    assert "do not use" in facts[1]["status"] and "readings" not in facts[1]
    assert farm_advisor.sensor_facts([]) == "no sensor connected"


# ---------------------------------------------------------------- API

def test_scan_advice_endpoint_generates_once_per_language_then_caches(phone, monkeypatch):
    _install_both()
    headers, _ = _register(phone)
    scan_id = _analyze(phone, headers).json()["scan"]["id"]
    calls = []
    _llm_returns(monkeypatch, json.dumps({"headline": "h", "farmer_message": "m", "do_now": ["remove leaves"],
                                          "next_3_days": [], "next_7_days": [], "prevention": [], "safety": []}), calls)
    first = phone.post(f"/api/v1/scans/{scan_id}/advice", headers=headers, json={"language": "en"}).json()
    again = phone.post(f"/api/v1/scans/{scan_id}/advice", headers=headers, json={"language": "en"}).json()
    assert first["cached"] is False and again["cached"] is True and len(calls) == 1
    assert first["advice"]["sections"][0]["items"] == ["remove leaves"]
    stored = store.get_scan(scan_id)["result"]
    assert stored["advice_by_language"]["en"]["source"] == "local_llm"


def test_scan_advice_is_private_to_the_owner(phone, monkeypatch):
    _install_both()
    owner, _ = _register(phone, "farmer1")
    other, _ = _register(phone, "farmer2")
    scan_id = _analyze(phone, owner).json()["scan"]["id"]
    _llm_down(monkeypatch)
    assert phone.post(f"/api/v1/scans/{scan_id}/advice", headers=other, json={"language": "ta"}).status_code == 404


def test_chat_answers_in_typed_language_and_reports_offline_honestly(phone, monkeypatch):
    headers, _ = _register(phone)
    _llm_returns(monkeypatch, "வெள்ளை ஈக்களை கட்டுப்படுத்தவும்.")
    res = phone.post("/api/v1/chat", headers=headers, json={"message": "என்ன செய்வது?", "language": "en"})
    assert res.status_code == 200 and res.json()["language"] == "ta"

    _llm_down(monkeypatch)
    res = phone.post("/api/v1/chat", headers=headers, json={"message": "hello", "language": "ta"})
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "advisor_unavailable"
    assert "answer" not in res.json()  # no canned answer when the AI is offline


def test_languages_endpoint_is_reachable_from_phone(phone):
    body = phone.get("/api/v1/languages").json()
    assert body["default"] == "ta" and len(body["languages"]) == 12


def test_sensor_history_returns_only_real_readings(phone, monkeypatch):
    monkeypatch.setattr(config, "SENSOR_INGEST_TOKEN", "tok")
    headers, _ = _register(phone)
    for moisture in (30.5, 31.0):
        assert phone.post("/api/v1/sensors/readings", headers={"X-Sensor-Token": "tok"},
                          json={"device_id": "pi-1", "readings": {"soil_moisture_pct": moisture}}).status_code == 201
    rows = phone.get("/api/v1/sensors/history", headers=headers, params={"device_id": "pi-1"}).json()["readings"]
    assert [r["readings"]["soil_moisture_pct"] for r in rows] == [30.5, 31.0]
    assert phone.get("/api/v1/sensors/history", headers=headers, params={"device_id": "nope"}).json()["readings"] == []


def test_impossible_sensor_values_are_refused(phone, monkeypatch):
    monkeypatch.setattr(config, "SENSOR_INGEST_TOKEN", "tok")
    res = phone.post("/api/v1/sensors/readings", headers={"X-Sensor-Token": "tok"},
                     json={"device_id": "pi-1", "readings": {"soil_moisture_pct": 140}})
    assert res.status_code == 422 and "outside the possible range" in res.text
    assert store.latest_sensor_readings() == []


# ---------------------------------------------------------------- streaming chat & scan context

def _llm_streams(monkeypatch, pieces, calls=None):
    def fake(messages, max_tokens):
        if calls is not None:
            calls.append(messages)
        for p in pieces:
            yield "gemma3:4b", p

    monkeypatch.setattr(farm_advisor, "_stream", fake)


def _events(res):
    return [json.loads(line) for line in res.text.splitlines() if line.strip()]


def test_stream_keeps_spaces_and_drops_foreign_words(monkeypatch):
    _llm_streams(monkeypatch, ["Remove ", "infected plants. ", "Use yellow", " sticky traps (कृषि) ", "now."])
    events = list(farm_advisor.chat_stream("what to do?", "en"))
    assert [e["type"] for e in events][0] == "start" and events[-1]["type"] == "done"
    text = "".join(e["text"] for e in events if e["type"] == "delta")
    assert text == "Remove infected plants. Use yellow sticky traps now."
    assert events[-1]["answer"] == text


def test_chat_stream_endpoint_uses_latest_scan_by_default(phone, monkeypatch):
    _install_both()
    headers, _ = _register(phone)
    scan_id = _analyze(phone, headers).json()["scan"]["id"]
    calls = []
    _llm_streams(monkeypatch, ["Tomato ", "Early Blight: ", "remove lower leaves."], calls)
    res = phone.post("/api/v1/chat/stream", headers=headers, json={"message": "How do I control this?", "language": "en"})
    assert res.status_code == 200 and res.headers["content-type"].startswith("application/x-ndjson")
    events = _events(res)
    assert events[0]["type"] == "start" and events[0]["context"]["scan_id"] == scan_id
    assert events[-1]["type"] == "done" and "remove lower leaves" in events[-1]["answer"]
    system_prompt = calls[0][0]["content"]
    assert "Tomato Early Blight" in system_prompt  # the advisor saw the farmer's scan
    assert "No greetings" in system_prompt


def test_chat_without_scan_context_when_disabled(phone, monkeypatch):
    _install_both()
    headers, _ = _register(phone)
    _analyze(phone, headers)
    calls = []
    _llm_streams(monkeypatch, ["General ", "answer."], calls)
    events = _events(phone.post("/api/v1/chat/stream", headers=headers,
                                json={"message": "hi", "language": "en", "use_latest_scan": False}))
    assert events[0]["context"] is None
    assert '"latest_scan": "none"' in calls[0][0]["content"]


def test_chat_stream_reports_offline_advisor(phone, monkeypatch):
    def down(messages, max_tokens):
        raise farm_advisor.AdvisorUnavailable("connection refused")
        yield  # pragma: no cover

    monkeypatch.setattr(farm_advisor, "_stream", down)
    headers, _ = _register(phone)
    events = _events(phone.post("/api/v1/chat/stream", headers=headers, json={"message": "hello", "language": "ta"}))
    assert events == [{"type": "error", "code": "advisor_unavailable", "detail": events[0]["detail"],
                       "message": "connection refused"}]
    assert "not running" in events[0]["detail"]


def test_advice_uses_fallback_advisor_only_when_main_is_unreachable(monkeypatch):
    import httpx

    monkeypatch.setattr(config, "OPENAI_BASE_URL", "http://laptop:11434/v1")
    monkeypatch.setattr(config, "ADVISOR_FALLBACK_URL", "http://localhost:11434")
    monkeypatch.setattr(config, "ADVISOR_FALLBACK_MODEL", "gemma3:1b")
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json["model"], json["keep_alive"]))
        if "laptop" in url:
            raise httpx.ConnectError("laptop is off")
        return httpx.Response(200, json={"message": {"content": "real answer"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert farm_advisor._complete([{"role": "user", "content": "hi"}], 50) == ("real answer", "gemma3:1b")
    assert calls[0][0] == "http://laptop:11434/api/chat"
    assert calls[-1] == ("http://localhost:11434/api/chat", "gemma3:1b", "2m")

    monkeypatch.setattr(config, "ADVISOR_FALLBACK_URL", "")
    with pytest.raises(farm_advisor.AdvisorUnavailable, match="laptop is off"):
        farm_advisor._complete([{"role": "user", "content": "hi"}], 50)


def test_switched_off_laptop_connect_timeout_also_uses_fallback(monkeypatch):
    import httpx

    monkeypatch.setattr(config, "OPENAI_BASE_URL", "http://laptop:11434/v1")
    monkeypatch.setattr(config, "ADVISOR_FALLBACK_URL", "http://localhost:11434")
    monkeypatch.setattr(config, "ADVISOR_FALLBACK_MODEL", "gemma3:1b")

    def fake_post(url, json, timeout):
        if "laptop" in url:  # no ARP reply from a powered-off laptop: connect times out
            raise httpx.ConnectTimeout("timed out")
        return httpx.Response(200, json={"message": {"content": "pi answer"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert farm_advisor._complete([{"role": "user", "content": "hi"}], 50) == ("pi answer", "gemma3:1b")
