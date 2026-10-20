"""S24: the replay mode speaks with recorded Foundry replies and needs no live model.

The "model" here is the fake of test_foundry: it answers with example sentences. Nothing contacts a network.
"""

import json
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from app import main, replay
from app.contracts import Detail, Lang, Profile
from app.foundry import FoundryDescriber
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, build_session
from app.replay import ReplayDescriber, ReplayStore, load_store
from app.replay_export import export
from app.replay_export import main as export_main
from app.usage import UsageLedger
from tests.test_foundry import Fake, run_isolated

MATCH = generate_match(SEED)
PRESETS = {p.id: p for p in build_presets(MATCH)}
client = TestClient(main.app)


def record(tmp_path, presets=("goal_1",), details=("full",), langs=("en",), fake=None):
    """Run the Foundry describer with a fake model, store its replies in a ledger and export them."""
    db = tmp_path / "usage.sqlite"
    ledger = UsageLedger(db, per_minute=10**6, per_day=10**6, tokens_per_day=10**9, eur_per_month=100.0)
    describer = FoundryDescriber(fake or Fake(), ledger)
    sessions = {
        (p, d, lang): build_session(MATCH, PRESETS[p], Profile(detail=d, lang=lang), describer)
        for p in presets
        for d in details
        for lang in langs
    }
    out = tmp_path / "replies.json"
    count = export(db, out, "fake-model", "2026-01-01")
    return load_store(out), sessions, count, out


def test_a_recorded_session_is_replayed_without_a_model(tmp_path):
    store, sessions, count, _ = record(tmp_path, langs=("en", "it"))
    assert count == len(store.replies) > 0 and store.model == "fake-model" and store.recorded == "2026-01-01"
    for (preset, detail, lang), original in sessions.items():
        replayed = build_session(MATCH, PRESETS[preset], Profile(detail=detail, lang=lang), ReplayDescriber(store))
        assert replayed.cues == original.cues  # the same words, spoken at the same times
        assert replayed.report.verified == replayed.report.moments and replayed.report.fallback == 0
        assert any(t.step == "describer" and replay.NOTE_REPLAYED in t.detail for t in replayed.trace)


def test_a_replayed_reply_goes_through_the_verifier_like_any_other(tmp_path):
    def liar(n, payload):
        return json.dumps(
            {
                "items": [
                    {"moment_id": m["moment_id"], "full": "Goal! Zorro scores for Nowhere.", "short": "Goal! Zorro."}
                    for m in payload["moments"]
                ]
            }
        )

    store, _, _, _ = record(tmp_path, fake=Fake(liar))
    assert store.replies  # the lies were recorded
    session = build_session(MATCH, PRESETS["goal_1"], Profile(detail="full"), ReplayDescriber(store))
    assert all("Zorro" not in c.text and "Nowhere" not in c.text for c in session.cues)
    assert session.report.moments == session.report.verified + session.report.fallback
    assert any(t.step == "verifier" and t.status == "failed" for t in session.trace)  # rejected, not trusted


def test_a_request_without_a_recorded_reply_is_described_by_the_templates_and_says_so(tmp_path):
    store, _, _, _ = record(tmp_path)
    other = build_session(MATCH, PRESETS["goal_2"], Profile(detail="full"), ReplayDescriber(store))
    assert other.report.verified == other.report.moments and other.report.fallback == 0
    assert any(replay.NOTE_MISSING in t.detail for t in other.trace if t.step == "describer")
    empty = build_session(MATCH, PRESETS["goal_1"], Profile(), ReplayDescriber(ReplayStore()))
    assert empty.cues and all(c.status == "verified" for c in empty.cues)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "[]",
        '{"version": 2, "replies": {}}',
        '{"version": 1, "replies": []}',
        '{"version": 1, "replies": {"short-key": "{}"}}',
        '{"version": 1, "replies": {"' + "a" * 64 + '": 5}}',
        '{"version": 1}',
    ],
)
def test_a_missing_or_invalid_file_is_an_empty_store_not_a_crash(tmp_path, content):
    assert load_store(tmp_path / "absent.json").replies == {}
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    assert load_store(path).replies == {}


def test_an_unparsable_recorded_reply_means_templates_not_an_error(tmp_path):
    store, _, _, _ = record(tmp_path)
    broken = ReplayStore({k: "this is not json" for k in store.replies})
    session = build_session(MATCH, PRESETS["goal_1"], Profile(detail="full"), ReplayDescriber(broken))
    assert session.cues and session.report.verified == session.report.moments


def test_the_export_reads_a_ledger_and_the_check_reports_coverage(tmp_path, capsys):
    store, _, _, out = record(tmp_path, presets=tuple(PRESETS), details=get_args(Detail), langs=get_args(Lang))
    hit, total = replay.coverage(store)
    assert hit == total > 0
    assert export_main(["--check", "--out", str(out)]) == 0
    assert f"{hit} of {total}" in capsys.readouterr().out
    partial_dir = tmp_path / "partial"
    partial_dir.mkdir()
    partial, _, _, partial_out = record(partial_dir)
    assert partial.replies and export_main(["--check", "--out", str(partial_out)]) == 1
    assert export_main(["--check", "--out", str(tmp_path / "absent.json")]) == 1


def test_the_api_in_replay_mode_serves_recorded_words_and_reports_what_it_holds(tmp_path, monkeypatch):
    store, sessions, _, out = record(tmp_path)
    monkeypatch.setattr(replay, "STORE_PATH", out)
    replay.reset_shared()
    main._session.cache_clear()
    monkeypatch.setenv("SOUNDPITCH_LLM", "replay")
    try:
        assert client.get("/api/health").json() == {"status": "ok", "llm": "replay", "replies": len(store.replies)}
        body = client.get("/api/session", params={"preset": "goal_1", "detail": "full"}).json()
        assert [c["text"] for c in body["cues"]] == [c.text for c in sessions[("goal_1", "full", "en")].cues]
        assert any(replay.NOTE_REPLAYED in t["detail"] for t in body["trace"])
        monkeypatch.setattr(replay, "STORE_PATH", tmp_path / "absent.json")
        replay.reset_shared()
        assert client.get("/api/health").json()["replies"] == 0
    finally:
        replay.reset_shared()
        main._session.cache_clear()


def test_replay_needs_neither_the_sdk_nor_a_network(tmp_path):
    _, _, _, out = record(tmp_path)
    run_isolated(
        f"""
import socket, sys
def no_network(*a, **k):
    raise AssertionError("the replay mode must not open a socket")
socket.socket.connect = no_network
from app.contracts import Profile
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, build_session
from app.replay import ReplayDescriber, load_store

match = generate_match(SEED)
store = load_store({str(out)!r})
assert store.replies
session = build_session(match, build_presets(match)[1], Profile(detail="full"), ReplayDescriber(store))
assert session.cues and any("recorded Foundry reply" in t.detail for t in session.trace)
assert "agent_framework" not in sys.modules and "azure.identity" not in sys.modules
"""
    )


def test_the_committed_replay_file_covers_every_window_once_it_has_content():
    store = load_store()
    if not store.replies:
        pytest.skip("no recorded replies are committed yet (they need an approved live run, see docs/DEPLOY.md)")
    hit, total = replay.coverage(store)
    assert hit == total, f"{total - hit} of {total} requests have no recorded reply: the prompt changed since the run"


def test_the_export_reads_a_ledger_in_a_folder_whose_name_has_url_characters(tmp_path):
    folder = tmp_path / "a#b c%41d"
    folder.mkdir()
    _, _, count, out = record(folder)
    assert count > 0 and load_store(out).replies
