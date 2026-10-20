"""S29: GET /api/voice says what the Azure voice can do on this server, so the page never offers a voice that is not there."""

import pytest
from fastapi.testclient import TestClient

from app import clips, tts
from app.contracts import VoiceSupport
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    for name in ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(clips, "CLIPS_DIR", tmp_path / "audio")
    clips.reset()
    tts.reset()
    yield
    clips.reset()
    tts.reset()


def store(tmp_path, entries: dict[tuple[str, str], bytes | None]) -> None:
    """Write a manifest with these (lang, text) entries; None means the manifest lists it but the file is missing."""
    root = tmp_path / "audio"
    manifest = {"version": clips.VERSION, "clips": {}}
    for (lang, text), data in entries.items():
        key = clips.clip_id(lang, text)
        manifest["clips"][key] = {"lang": lang, "text": text, "bytes": len(data or b"")}
        if data is not None:
            (root / lang).mkdir(parents=True, exist_ok=True)
            (root / lang / f"{key}.mp3").write_bytes(data)
    clips.write_manifest(root, manifest)
    clips.reset()


def test_a_server_without_clips_and_without_a_key_has_no_azure_voice():
    response = client.get("/api/voice")
    assert response.status_code == 200
    assert response.json() == {"stored_clips": {"en": 0, "it": 0}, "live": False}
    assert VoiceSupport.model_validate(response.json()).live is False


def test_only_clips_that_would_be_served_are_counted_per_language(tmp_path):
    store(
        tmp_path,
        {("en", "One."): b"ID3a", ("en", "Two."): b"ID3b", ("it", "Uno."): b"ID3c", ("it", "Due."): None, ("en", "Void."): b""},
    )
    assert client.get("/api/voice").json()["stored_clips"] == {"en": 2, "it": 1}  # missing and empty files do not count


def test_a_manifest_entry_that_names_another_text_does_not_count(tmp_path):
    store(tmp_path, {("en", "One."): b"ID3a"})
    root = tmp_path / "audio"
    manifest = clips.read_manifest(root)
    manifest["clips"][clips.clip_id("en", "One.")]["text"] = "Edited."
    clips.write_manifest(root, manifest)
    clips.reset()
    assert client.get("/api/voice").json()["stored_clips"] == {"en": 0, "it": 0}


def test_a_key_and_a_region_make_the_live_voice_available_and_the_key_is_not_shown(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "not-a-real-key-123")
    assert client.get("/api/voice").json()["live"] is False  # a region is needed too
    monkeypatch.setenv("AZURE_SPEECH_REGION", "italynorth")
    response = client.get("/api/voice")
    assert response.json()["live"] is True
    assert "not-a-real-key-123" not in response.text and "italynorth" not in response.text


def test_the_answer_sends_nothing_to_azure_and_carries_the_security_headers(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the availability check must not call Azure")

    monkeypatch.setattr(tts, "call_azure", refuse)
    monkeypatch.setenv("AZURE_SPEECH_KEY", "k")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "r")
    response = client.get("/api/voice")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in response.headers["content-security-policy"]
