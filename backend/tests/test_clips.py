"""S26: stored voice clips and the tool that makes them (Speech is always a stub here: no network, no key)."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import clips, clips_build, main, tts
from app.main import app

client = TestClient(app)
ENV = (
    "AZURE_SPEECH_KEY",
    "AZURE_SPEECH_REGION",
    "SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE",
    "SOUNDPITCH_TTS_PER_MINUTE",
    "SOUNDPITCH_LLM",
)


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(clips, "CLIPS_DIR", tmp_path / "audio")
    clips.reset()
    tts.reset()
    main._session.cache_clear()
    yield
    clips.reset()
    tts.reset()
    main._session.cache_clear()


class Speech:
    """A stub of the Speech endpoint: answers with fake mp3 bytes, can fail on demand, counts what it receives."""

    def __init__(self, monkeypatch, statuses=()):
        self.calls, self.bodies, self.statuses = 0, [], list(statuses)
        monkeypatch.setenv("AZURE_SPEECH_KEY", "key-that-must-never-be-printed")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "swedencentral")
        monkeypatch.setattr(tts, "make_client", lambda: httpx.Client(transport=httpx.MockTransport(self.handle)))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        self.bodies.append(request.content.decode())
        status = self.statuses.pop(0) if self.statuses else 200
        return httpx.Response(status, content=b"ID3" + str(self.calls).encode() if status == 200 else b"")


def make_store(root, entries, *, lang_dir=True):
    """A clip store on disk: entries is {(lang, text): bytes}."""
    manifest = {"version": 1, "format": tts.OUTPUT_FORMAT, "voices": {"en": "e", "it": "i"}, "generated": "2026-10-21", "clips": {}}
    for (lang, text), data in entries.items():
        key = clips.clip_id(lang, text)
        manifest["clips"][key] = {"lang": lang, "text": text, "bytes": len(data)}
        (root / lang).mkdir(parents=True, exist_ok=True)
        (root / lang / f"{key}.mp3").write_bytes(data)
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def say(text, lang="en", rate=1.0, **kw):
    return client.post("/api/tts", json={"text": text, "lang": lang, "rate": rate}, **kw)


# ---- serving stored clips ---------------------------------------------------------------------------------


def test_a_stored_clip_is_served_without_any_speech_key(tmp_path):
    make_store(tmp_path / "audio", {("en", "Goal!"): b"MP3-DATA"})
    tts.issue("en", ["Goal!"])
    response = say("Goal!", rate=1.7)
    assert response.status_code == 200 and response.content == b"MP3-DATA"
    assert response.headers["content-type"] == "audio/mpeg" and response.headers["x-audio-rate"] == "1"


def test_a_stored_clip_never_calls_azure_even_when_azure_is_configured(monkeypatch, tmp_path):
    speech = Speech(monkeypatch)
    make_store(tmp_path / "audio", {("en", "Goal!"): b"MP3-DATA"})
    tts.issue("en", ["Goal!"])
    assert say("Goal!").content == b"MP3-DATA" and speech.calls == 0


def test_text_that_was_not_issued_is_refused_even_if_a_clip_exists(tmp_path):
    make_store(tmp_path / "audio", {("en", "Goal!"): b"MP3-DATA"})
    assert say("Goal!").status_code == 403


def test_a_clip_belongs_to_its_language(tmp_path):
    make_store(tmp_path / "audio", {("en", "Goal!"): b"MP3-DATA"})
    tts.issue("en", ["Goal!"])
    tts.issue("it", ["Goal!"])
    assert say("Goal!", "it").status_code == 501  # issued in Italian, but only an English clip exists


@pytest.mark.parametrize("damage", ["text", "lang", "missing file", "empty file", "huge file", "bad manifest", "no manifest"])
def test_a_clip_that_does_not_match_its_manifest_is_treated_as_absent(tmp_path, damage):
    root = tmp_path / "audio"
    make_store(root, {("en", "Goal!"): b"MP3-DATA"})
    key = clips.clip_id("en", "Goal!")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if damage == "text":
        manifest["clips"][key]["text"] = "Goal?"
    elif damage == "lang":
        manifest["clips"][key]["lang"] = "it"
    elif damage == "missing file":
        (root / "en" / f"{key}.mp3").unlink()
    elif damage == "empty file":
        (root / "en" / f"{key}.mp3").write_bytes(b"")
    elif damage == "huge file":
        (root / "en" / f"{key}.mp3").write_bytes(b"x" * (clips.MAX_CLIP_BYTES + 1))
    elif damage == "bad manifest":
        (root / "manifest.json").write_text("{not json", encoding="utf-8")
    elif damage == "no manifest":
        (root / "manifest.json").unlink()
    if damage not in ("bad manifest", "no manifest"):
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    clips.reset()
    tts.issue("en", ["Goal!"])
    assert say("Goal!").status_code == 501  # nothing stored, no Speech key


def test_the_per_client_limit_still_applies_to_stored_clips(monkeypatch, tmp_path):
    monkeypatch.setenv("SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE", "2")
    make_store(tmp_path / "audio", {("en", "One"): b"1", ("en", "Two"): b"2", ("en", "Three"): b"3"})
    tts.issue("en", ["One", "Two", "Three"])
    assert [say(t).status_code for t in ("One", "Two", "Three")] == [200, 200, 429]


def test_the_live_path_reports_the_rate_it_applied(monkeypatch):
    Speech(monkeypatch)
    tts.issue("en", ["Goal!"])
    response = say("Goal!", rate=1.4)
    assert response.status_code == 200 and response.headers["x-audio-rate"] == "1.4"
    assert say("Goal!").headers["x-audio-rate"] == "1"


def test_ssml_carries_no_prosody_tag_at_normal_speed():
    assert "prosody" not in tts.ssml("Goal!", "en", 1.0)
    assert "rate='+40%'" in tts.ssml("Goal!", "en", 1.4)


# ---- the sentences the demo can speak ---------------------------------------------------------------------


def test_every_sentence_a_session_can_speak_is_in_the_universe(monkeypatch):
    monkeypatch.setenv("SOUNDPITCH_LLM", "replay")  # the mode of the public deployment
    universe = set(clips_build.sentences())
    assert {lang for lang, _ in universe} == {"en", "it"} and all(0 < len(text) <= 400 for _, text in universe)
    for preset in ("kickoff", "goal_1", "goal_3", "final_whistle"):
        for detail in ("essential", "standard", "full"):
            for lang in ("en", "it"):
                for extra in ({"rate": 0.5}, {"rate": 2.0, "calm": "true"}, {"rate": 1.0}):
                    body = client.get("/api/session", params={"preset": preset, "detail": detail, "lang": lang, **extra}).json()
                    for cue in body["cues"]:
                        assert (lang, cue["text"]) in universe, (preset, detail, lang, cue["text"])


# ---- the tool: dry run -------------------------------------------------------------------------------------


def test_the_dry_run_counts_and_prices_but_sends_nothing(monkeypatch, capsys):
    def no_network():
        raise AssertionError("the dry run must not create an HTTP client")

    monkeypatch.setattr(tts, "make_client", no_network)
    assert clips_build.main([]) == 0
    out = capsys.readouterr().out
    universe = clips_build.sentences()
    chars = sum(len(t) for _, t in universe)
    assert f"{len(universe)} sentences" in out and f"{chars} characters" in out
    assert "dry run" in out and "USD" in out and "nothing was sent" in out
    assert f"{chars * clips_build.PRICE_USD_PER_MILLION / 1e6:.2f}" in out


def test_generate_without_a_key_stops_before_any_request(monkeypatch, capsys):
    monkeypatch.setattr(tts, "make_client", lambda: (_ for _ in ()).throw(AssertionError("no request without a key")))
    assert clips_build.main(["--generate"]) == 2
    assert "AZURE_SPEECH_KEY" in capsys.readouterr().err


def test_generate_refuses_to_send_more_than_the_character_cap(monkeypatch, capsys):
    speech = Speech(monkeypatch)
    assert clips_build.main(["--generate", "--max-chars", "100"]) == 2
    assert speech.calls == 0 and "--max-chars" in capsys.readouterr().err


# ---- the tool: generation ----------------------------------------------------------------------------------


def test_generation_writes_the_clips_and_the_manifest_then_the_api_serves_them(monkeypatch, tmp_path, capsys):
    speech = Speech(monkeypatch)
    monkeypatch.setattr(clips_build.time, "sleep", lambda s: None)
    universe = clips_build.sentences()
    assert clips_build.main(["--generate", "--date", "2026-10-21"]) == 0
    assert speech.calls == len(universe)
    manifest = json.loads((tmp_path / "audio" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == 1 and manifest["generated"] == "2026-10-21" and manifest["voices"] == {"en": "en-GB-RyanNeural", "it": "it-IT-DiegoNeural"}
    assert len(manifest["clips"]) == len(universe)
    assert all("prosody" not in body for body in speech.bodies)  # normal speed: no markup is billed
    assert "key-that-must-never-be-printed" not in capsys.readouterr().out
    # a second run finds everything stored and sends nothing
    assert clips_build.main(["--generate"]) == 0 and speech.calls == len(universe)
    # the page's request is now served from the store, with no key
    monkeypatch.delenv("AZURE_SPEECH_KEY")
    clips.reset()
    lang, text = min(universe)
    tts.issue(lang, [text])
    response = say(text, lang)
    assert response.status_code == 200 and response.content.startswith(b"ID3") and response.headers["x-audio-rate"] == "1"


def test_generation_honours_the_limit_and_resumes(monkeypatch, tmp_path):
    speech = Speech(monkeypatch)
    monkeypatch.setattr(clips_build.time, "sleep", lambda s: None)
    assert clips_build.main(["--generate", "--limit", "3"]) == 0 and speech.calls == 3
    assert len(json.loads((tmp_path / "audio" / "manifest.json").read_text(encoding="utf-8"))["clips"]) == 3
    assert clips_build.main(["--generate", "--limit", "2"]) == 0 and speech.calls == 5  # the first three are kept


def test_a_rate_limit_is_retried_with_a_growing_wait_and_then_succeeds(monkeypatch):
    speech = Speech(monkeypatch, statuses=[429, 503])
    waits: list[float] = []
    monkeypatch.setattr(clips_build.time, "sleep", waits.append)
    assert clips_build.main(["--generate", "--limit", "1"]) == 0
    assert speech.calls == 3 and len(waits) >= 2 and waits[0] < waits[1]


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_key_stops_the_run_after_one_request(monkeypatch, capsys, status):
    speech = Speech(monkeypatch, statuses=[status])
    monkeypatch.setattr(clips_build.time, "sleep", lambda s: None)
    assert clips_build.main(["--generate"]) == 1
    assert speech.calls == 1
    captured = capsys.readouterr()
    assert str(status) in captured.err and "key-that-must-never-be-printed" not in captured.out + captured.err


def test_repeated_failures_stop_the_run_and_keep_what_was_made(monkeypatch, tmp_path):
    speech = Speech(monkeypatch, statuses=[200, 200, 500, 500, 500, 500, 500, 500])
    monkeypatch.setattr(clips_build.time, "sleep", lambda s: None)
    assert clips_build.main(["--generate"]) == 1
    assert len(json.loads((tmp_path / "audio" / "manifest.json").read_text(encoding="utf-8"))["clips"]) == 2
    assert speech.calls <= 2 + clips_build.ATTEMPTS


# ---- the committed store ----------------------------------------------------------------------------------


def test_the_committed_store_covers_every_sentence_once_it_has_content(monkeypatch):
    monkeypatch.undo()  # the real directory, not the temporary one
    clips.reset()
    store = clips.store()
    if not store.clips:
        pytest.skip("no clips are committed yet (they need an approved Speech run, see docs/DEPLOY.md)")
    missing = [(lang, text) for lang, text in clips_build.sentences() if store.get(lang, text) is None]
    assert not missing, f"{len(missing)} sentences have no clip: {missing[:3]}"
