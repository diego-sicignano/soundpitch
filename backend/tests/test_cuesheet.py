"""S15: the cue sheet is the session in a flat, versioned, schema-checked shape (SPEC §13)."""

import itertools
import json
from pathlib import Path
from typing import get_args

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import cuesheet
from app.contracts import CueSheet, Detail, Lang, Session
from app.main import PRESETS, app

client = TestClient(app)
SCHEMA_FILE = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "cuesheet.v1.schema.json"
ORDER = {"audio_description": 0, "caption": 1, "ball_sound": 2}


def params(preset, detail="standard", lang="en", **extra):
    return {"preset": preset, "detail": detail, "lang": lang, **extra}


@pytest.mark.parametrize("preset", list(PRESETS))
@pytest.mark.parametrize("detail", get_args(Detail))
@pytest.mark.parametrize("lang", get_args(Lang))
def test_every_cue_sheet_is_valid_sorted_and_equal_to_its_session(preset, detail, lang):
    sheet = CueSheet.model_validate(client.get("/api/cuesheet", params=params(preset, detail, lang)).json())
    session = Session.model_validate(client.get("/api/session", params=params(preset, detail, lang)).json())
    assert sheet.schema_version == 1 and sheet.preset == preset and sheet.lang == lang
    assert sheet.duration_ms == session.duration_ms
    from_s = PRESETS[preset].from_s
    assert sheet.match_clock_from == f"{from_s // 60:02d}:{from_s % 60:02d}"

    keys = [(i.at_ms, ORDER[i.type], i.id) for i in sheet.items]
    assert keys == sorted(keys) and len({i.id for i in sheet.items}) == len(sheet.items)

    spoken = {i.id: i for i in sheet.items if i.type == "audio_description"}
    captions = {i.id: i for i in sheet.items if i.type == "caption"}
    assert [(i.at_ms, i.text) for i in sorted(spoken.values(), key=lambda i: i.at_ms)] == [
        (c.start_ms, c.text) for c in session.cues
    ]
    for cue in session.cues:
        speech, caption = spoken[f"ad-{cue.id}"], captions[f"cap-{cue.id}"]
        assert (speech.at_ms, speech.duration_ms) == (cue.start_ms, cue.end_ms - cue.start_ms)
        assert (caption.at_ms, caption.duration_ms, caption.text) == (speech.at_ms, speech.duration_ms, speech.text)
        assert (speech.priority, speech.status, speech.event_ids) == (cue.priority, cue.status, cue.event_ids)
    ordered = sorted(spoken.values(), key=lambda i: i.at_ms)
    assert all(a.at_ms + a.duration_ms <= b.at_ms for a, b in itertools.pairwise(ordered))

    sounds = [i for i in sheet.items if i.type == "ball_sound"]
    assert [(s.at_ms, s.sound, s.pan, s.pitch, s.gain) for s in sounds] == [
        (e.t_ms, e.kind, e.pan, e.pitch, e.gain) for e in session.earcons
    ]


def test_ball_sounds_follow_the_profile():
    off = CueSheet.model_validate(client.get("/api/cuesheet", params=params("goal_1", earcons="false")).json())
    assert not [i for i in off.items if i.type == "ball_sound"]
    calm = CueSheet.model_validate(client.get("/api/cuesheet", params=params("goal_1", calm="true")).json())
    assert {i.sound for i in calm.items if i.type == "ball_sound"} <= {"goal", "whistle", "whistle_long"}


def test_errors_are_the_ones_of_the_session():
    missing = client.get("/api/cuesheet", params={"preset": "nope"})
    assert missing.status_code == 404 and missing.json()["code"] == "preset_not_found"
    assert client.get("/api/cuesheet", params={"rate": 3}).status_code == 422


def test_the_schema_is_served_and_equals_the_committed_file_and_the_contract():
    served = client.get("/api/cuesheet.schema.json")
    assert served.status_code == 200 and served.headers["content-type"].startswith("application/json")
    assert served.json() == CueSheet.model_json_schema() == cuesheet.schema()
    assert SCHEMA_FILE.is_file(), "run: python -m app.cuesheet --write ../docs/contracts/cuesheet.v1.schema.json"
    assert json.loads(SCHEMA_FILE.read_text(encoding="utf-8")) == served.json()
    assert SCHEMA_FILE.read_text(encoding="utf-8").replace("\r\n", "\n") == cuesheet.schema_text()


def test_the_contract_refuses_unknown_fields_types_and_values():
    good = client.get("/api/cuesheet", params=params("goal_1")).json()
    CueSheet.model_validate(good)
    first = good["items"][0]
    sound = {"id": "b", "type": "ball_sound", "at_ms": 0, "sound": "tick", "pan": 2, "pitch": 0, "gain": 0}
    for broken in (
        {**good, "extra": 1},
        {**good, "schema_version": 2},
        {**good, "match_clock_from": "1:5"},
        {**good, "items": [{**first, "type": "video"}]},
        {**good, "items": [{**first, "surprise": True}]},
        {**good, "items": [sound]},
    ):
        with pytest.raises(ValidationError):
            CueSheet.model_validate(broken)


def test_the_schema_command_writes_the_committed_text(tmp_path):
    out = tmp_path / "schema.json"
    assert cuesheet.main(["--write", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == cuesheet.schema_text()


def test_the_schema_version_is_required_so_a_consumer_can_enforce_it():
    assert "schema_version" in CueSheet.model_json_schema()["required"]
    good = client.get("/api/cuesheet", params=params("goal_1")).json()
    assert good["schema_version"] == 1
    without = {k: v for k, v in good.items() if k != "schema_version"}
    with pytest.raises(ValidationError):
        CueSheet.model_validate(without)
