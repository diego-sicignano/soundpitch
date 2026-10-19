"""S7: the HTTP contract, WebVTT and Azure AI Speech (stubbed)."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import tts
from app.contracts import MatchHeader, Preset, Session
from app.main import app

client = TestClient(app)


def test_health_reports_the_llm_mode(monkeypatch):
    monkeypatch.delenv("SOUNDPITCH_LLM", raising=False)
    assert client.get("/api/health").json() == {"status": "ok", "llm": "scripted"}


def test_match_header():
    header = MatchHeader.model_validate(client.get("/api/match").json())
    assert (header.home_goals, header.away_goals) == (2, 1)
    assert [g.minute for g in header.goals] == [16, 52, 78]
    assert header.home.name == "Northgate Red"


def test_presets():
    presets = [Preset.model_validate(p) for p in client.get("/api/presets").json()]
    assert [p.id for p in presets] == ["kickoff", "goal_1", "goal_2", "goal_3", "final_whistle"]


def test_session_is_a_valid_contract_and_honours_parameters():
    response = client.get("/api/session", params={"preset": "goal_2", "lang": "it", "detail": "full", "rate": 1.2})
    assert response.status_code == 200
    session = Session.model_validate(response.json())
    assert session.preset == "goal_2" and session.lang == "it" and session.profile.rate == 1.2
    assert session.cues and session.report.overlaps == 0
    assert client.get("/api/session").json()["preset"] == "goal_1"


def test_session_scenarios_flow_through_the_api(monkeypatch):
    from app import main

    main._session.cache_clear()
    monkeypatch.setenv("SOUNDPITCH_LLM", "always_bad")
    report = client.get("/api/session", params={"preset": "goal_3"}).json()["report"]
    assert report["fallback"] == report["moments"] and report["attempts"] == 3
    main._session.cache_clear()


def test_unknown_preset_and_invalid_parameters():
    missing = client.get("/api/session", params={"preset": "nope"})
    assert missing.status_code == 404 and missing.json()["code"] == "preset_not_found"
    assert client.get("/api/session", params={"detail": "extreme"}).status_code == 422
    assert client.get("/api/session", params={"rate": 3}).status_code == 422
    assert client.get("/api/session.vtt", params={"preset": "nope"}).status_code == 404


def test_webvtt_endpoint():
    response = client.get("/api/session.vtt", params={"preset": "goal_1"})
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/vtt")
    assert response.text.startswith("WEBVTT\n\n1\n00:00:")
    assert " --> " in response.text


@pytest.fixture(autouse=True)
def clean_tts(monkeypatch):
    for name in ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION", "SOUNDPITCH_TTS_PER_MINUTE"):
        monkeypatch.delenv(name, raising=False)
    tts.LIMITER.reset()
    yield
    tts.LIMITER.reset()


def stub_azure(monkeypatch, handler):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "secret")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "swedencentral")
    monkeypatch.setattr(tts, "make_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))


def test_tts_is_not_implemented_without_azure_settings():
    response = client.post("/api/tts", json={"text": "Goal!"})
    assert response.status_code == 501 and response.json()["code"] == "tts_not_configured"


def test_tts_sends_ssml_to_azure_and_returns_the_audio(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["key"], seen["body"] = str(request.url), request.headers["ocp-apim-subscription-key"], request.content.decode()
        return httpx.Response(200, content=b"ID3-audio")

    stub_azure(monkeypatch, handler)
    response = client.post("/api/tts", json={"text": "Goal! Marsh & Reyes", "lang": "it", "rate": 1.4})
    assert response.status_code == 200 and response.content == b"ID3-audio"
    assert response.headers["content-type"] == "audio/mpeg"
    assert seen["url"] == "https://swedencentral.tts.speech.microsoft.com/cognitiveservices/v1"
    assert seen["key"] == "secret"
    assert "it-IT-DiegoNeural" in seen["body"] and "rate='+40%'" in seen["body"]
    assert "Marsh &amp; Reyes" in seen["body"]


def test_tts_reports_azure_failures_as_bad_gateway(monkeypatch):
    stub_azure(monkeypatch, lambda request: httpx.Response(401))
    response = client.post("/api/tts", json={"text": "Goal!"})
    assert response.status_code == 502 and "401" in response.json()["message"]

    def unreachable(request):
        raise httpx.ConnectError("boom")

    stub_azure(monkeypatch, unreachable)
    assert client.post("/api/tts", json={"text": "Goal!"}).status_code == 502


def test_tts_validates_input_and_rate_limits(monkeypatch):
    assert client.post("/api/tts", json={"text": ""}).status_code == 422
    assert client.post("/api/tts", json={"text": "x" * 401}).status_code == 422
    stub_azure(monkeypatch, lambda request: httpx.Response(200, content=b"a"))
    monkeypatch.setenv("SOUNDPITCH_TTS_PER_MINUTE", "2")
    statuses = [client.post("/api/tts", json={"text": "Goal!"}).status_code for _ in range(3)]
    assert statuses == [200, 200, 429]
