"""S22: /api/tts speaks only issued text and is limited per client, per minute and per day (Azure stubbed)."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main, tts
from app.main import app

client = TestClient(app)
ENV = (
    "AZURE_SPEECH_KEY",
    "AZURE_SPEECH_REGION",
    "SOUNDPITCH_TTS_PER_MINUTE",
    "SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE",
    "SOUNDPITCH_TTS_CHARS_PER_DAY",
    "SOUNDPITCH_TTS_CHARS_PER_MONTH",
    "SOUNDPITCH_TRUST_PROXY",
    "SOUNDPITCH_LLM",
)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    tts.reset()
    main._session.cache_clear()
    yield
    tts.reset()
    main._session.cache_clear()


class Azure:
    """A stub of the Speech endpoint that counts the requests it received."""

    def __init__(self, monkeypatch, status=200):
        self.calls, self.status = 0, status
        monkeypatch.setenv("AZURE_SPEECH_KEY", "secret")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "swedencentral")
        monkeypatch.setattr(tts, "make_client", lambda: httpx.Client(transport=httpx.MockTransport(self.handle)))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(self.status, content=b"mp3")


def say(text, lang="en", rate=1.0, **kw):
    return client.post("/api/tts", json={"text": text, "lang": lang, "rate": rate}, **kw)


def test_text_that_was_not_issued_is_refused_and_azure_is_not_called(monkeypatch):
    azure = Azure(monkeypatch)
    response = say("Read this out loud")
    assert response.status_code == 403 and response.json()["code"] == "tts_text_not_issued"
    assert azure.calls == 0


def test_the_cue_texts_of_a_session_can_be_spoken(monkeypatch):
    azure = Azure(monkeypatch)
    session = client.get("/api/session", params={"preset": "goal_1", "lang": "it"}).json()
    text = session["cues"][0]["text"]
    assert say(text, "it").status_code == 200 and azure.calls == 1
    assert say(text, "en").status_code == 403  # issued in Italian, not in English
    assert say(text + " extra", "it").status_code == 403  # a changed text is another text


def test_a_session_that_is_not_kept_still_issues_its_texts(monkeypatch):
    azure = Azure(monkeypatch)
    monkeypatch.setenv("SOUNDPITCH_LLM", "always_bad")
    text = client.get("/api/session", params={"preset": "goal_1"}).json()["cues"][0]["text"]
    assert say(text).status_code == 200 and azure.calls == 1


def test_not_configured_is_reported_before_the_text_check():
    assert say("anything").status_code == 501


def test_input_is_validated_first(monkeypatch):
    Azure(monkeypatch)
    assert say("").status_code == 422
    assert say("x" * 401).status_code == 422
    assert say("Goal!", rate=3).status_code == 422


def test_a_repeated_request_is_served_from_memory(monkeypatch):
    azure = Azure(monkeypatch)
    tts.issue("en", ["Goal! Marsh scores."])
    first, second = say("Goal! Marsh scores."), say("Goal! Marsh scores.")
    assert first.content == second.content == b"mp3" and azure.calls == 1
    assert say("Goal! Marsh scores.", rate=1.004).status_code == 200 and azure.calls == 1  # same percent
    assert say("Goal! Marsh scores.", rate=1.4).status_code == 200 and azure.calls == 2  # another speed


def test_one_client_cannot_use_more_than_its_share_of_a_minute(monkeypatch):
    azure = Azure(monkeypatch)
    monkeypatch.setenv("SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE", "3")
    tts.issue("en", [f"Text {n}" for n in range(10)])
    statuses = [say(f"Text {n}").status_code for n in range(5)]
    assert statuses == [200, 200, 200, 429, 429] and azure.calls == 3
    assert say("Text 9").json()["code"] == "rate_limited"


def test_clients_are_told_apart_only_behind_a_trusted_proxy(monkeypatch):
    Azure(monkeypatch)
    monkeypatch.setenv("SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE", "1")
    tts.issue("en", ["One", "Two", "Three"])

    def forwarded(ip):
        return {"headers": {"X-Forwarded-For": f"9.9.9.9, {ip}"}}

    assert say("One", **forwarded("1.1.1.1")).status_code == 200
    assert say("Two", **forwarded("2.2.2.2")).status_code == 429  # not trusted: the header changes nothing
    tts.reset(keep_issued=True)
    monkeypatch.setenv("SOUNDPITCH_TRUST_PROXY", "1")
    assert say("One", **forwarded("1.1.1.1")).status_code == 200
    assert say("Two", **forwarded("2.2.2.2")).status_code == 200  # the last address is the proxy's view of the caller
    assert say("Three", **forwarded("1.1.1.1")).status_code == 429


def test_the_whole_process_has_a_per_minute_limit(monkeypatch):
    azure = Azure(monkeypatch)
    monkeypatch.setenv("SOUNDPITCH_TTS_PER_MINUTE", "2")
    tts.issue("en", ["A", "B", "C"])
    assert [say(t).status_code for t in "ABC"] == [200, 200, 429] and azure.calls == 2


def test_the_minute_window_slides(monkeypatch):
    Azure(monkeypatch)
    now = [1_000_000.0]
    monkeypatch.setattr(tts, "CLOCK", lambda: now[0])
    monkeypatch.setenv("SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE", "1")
    tts.issue("en", ["A", "B"])
    assert say("A").status_code == 200 and say("B").status_code == 429
    now[0] += 61
    assert say("B").status_code == 200


def test_the_daily_character_cap_stops_requests_before_azure(monkeypatch):
    azure = Azure(monkeypatch)
    monkeypatch.setenv("SOUNDPITCH_TTS_CHARS_PER_DAY", "25")
    texts = ["a" * 10, "b" * 10, "c" * 10]
    tts.issue("en", texts)
    assert [say(t).status_code for t in texts] == [200, 200, 429] and azure.calls == 2
    refused = say(texts[2])
    assert "day" in refused.json()["message"] and azure.calls == 2
    assert say(texts[0]).status_code == 200  # already spoken: served from memory, no characters


def test_the_monthly_cap_and_the_rollover(monkeypatch):
    azure = Azure(monkeypatch)
    now = [1_700_000_000.0]  # 2023-11-14 UTC
    monkeypatch.setattr(tts, "CLOCK", lambda: now[0])
    monkeypatch.setenv("SOUNDPITCH_TTS_CHARS_PER_MONTH", "25")
    monkeypatch.setenv("SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE", "100")
    monkeypatch.setenv("SOUNDPITCH_TTS_PER_MINUTE", "100")
    texts = ["a" * 10, "b" * 10, "c" * 10, "d" * 10]
    tts.issue("en", texts)
    assert [say(t).status_code for t in texts[:3]] == [200, 200, 429]
    now[0] += 86_400  # next day, same month
    refused = say(texts[2])
    assert refused.status_code == 429 and "month" in refused.json()["message"]
    now[0] += 20 * 86_400  # December
    assert say(texts[2]).status_code == 200 and azure.calls == 3


def test_a_failed_azure_call_still_counts_its_characters(monkeypatch):
    azure = Azure(monkeypatch, status=500)
    monkeypatch.setenv("SOUNDPITCH_TTS_CHARS_PER_DAY", "15")
    tts.issue("en", ["a" * 10, "b" * 10])
    assert say("a" * 10).status_code == 502
    assert say("b" * 10).status_code == 429 and azure.calls == 1  # 10 counted already, 20 would pass 15


def test_a_failure_is_never_kept_in_memory(monkeypatch):
    azure = Azure(monkeypatch, status=500)
    tts.issue("en", ["a" * 10])
    assert say("a" * 10).status_code == 502 and say("a" * 10).status_code == 502
    assert azure.calls == 2


def test_bad_limit_settings_fall_back_to_the_defaults(monkeypatch):
    azure = Azure(monkeypatch)
    for name in ("SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE", "SOUNDPITCH_TTS_CHARS_PER_DAY", "SOUNDPITCH_TTS_PER_MINUTE"):
        monkeypatch.setenv(name, "lots")
    tts.issue("en", ["Fine"])
    assert say("Fine").status_code == 200 and azure.calls == 1
    monkeypatch.setenv("SOUNDPITCH_TTS_CHARS_PER_DAY", "0")
    assert say("Fine", rate=1.5).status_code == 200  # 0 is ignored too: the default of 60,000 applies


def test_the_issued_set_and_the_audio_cache_are_bounded(monkeypatch):
    Azure(monkeypatch)
    for name in ("SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE", "SOUNDPITCH_TTS_PER_MINUTE"):
        monkeypatch.setenv(name, "100000")
    for name in ("SOUNDPITCH_TTS_CHARS_PER_DAY", "SOUNDPITCH_TTS_CHARS_PER_MONTH"):
        monkeypatch.setenv(name, "10000000")
    tts.issue("en", [f"t{n}" for n in range(tts.ISSUED_MAX + 50)])
    assert tts.issued_count() == tts.ISSUED_MAX
    assert say("t0").status_code == 403  # the oldest was forgotten
    assert say(f"t{tts.ISSUED_MAX + 49}").status_code == 200
    tts.reset()
    tts.issue("en", [f"u{n}" for n in range(tts.AUDIO_MAX + 20)])
    for n in range(tts.AUDIO_MAX + 20):
        assert say(f"u{n}").status_code == 200
    assert tts.audio_count() == tts.AUDIO_MAX


def test_the_per_client_limit_is_exact_under_threads(monkeypatch):
    import threading

    Azure(monkeypatch)
    monkeypatch.setenv("SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE", "10")
    tts.issue("en", ["Goal!"])
    results = []

    def go():
        try:
            tts.synthesize("Goal!", "en", 1.0, "one-client")
            results.append(True)
        except tts.RateLimited:
            results.append(False)

    workers = [threading.Thread(target=go) for _ in range(60)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    assert sum(results) == 10
