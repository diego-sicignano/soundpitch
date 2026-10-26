"""S35: the recording of the live Analyst, with a fake agent and a temporary ledger (no model call)."""

import json

import pytest

from app import analysis
from app.analyst_run import Answer, question, record, to_markdown
from app.contracts import Profile
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, build_session
from app.usage import BudgetExceeded, UsageLedger

MATCH = generate_match(SEED)


def ledger(tmp_path, per_day=100):
    return UsageLedger(tmp_path / "usage.sqlite", per_minute=100, per_day=per_day, tokens_per_day=10_000_000, eur_per_month=4.0)


class FakeAgent:
    """Wrong names on the first attempt of the final whistle, right points otherwise."""

    def __init__(self):
        self.asked = []

    def __call__(self, req, attempt, feedback):
        self.asked.append((req.preset.id, req.lang, attempt, list(feedback)))
        points = analysis.CodeAnalyst().propose(req, attempt, feedback)
        if req.preset.id == "final_whistle" and attempt == 1:
            points = analysis.FlawedAnalyst(bad_attempts=1).propose(req, attempt, feedback)
        body = {"points": [{"text": p.text, "source": p.source} for p in points]}
        return Answer(json.dumps(body), ["get_recap", "get_stats"], 1000, 100)


def test_the_recorded_replies_are_the_ones_the_judges_sessions_ask_for(tmp_path):
    agent, replies = FakeAgent(), {}
    rows = record(agent, ledger(tmp_path), replies)
    assert len(rows) == 10 and len(agent.asked) == 12  # one retry for the final whistle, in each language
    replay = analysis.ReplayAnalyst(analysis.Store(replies))
    for preset in build_presets(MATCH):
        for lang in ("en", "it"):
            built = build_session(MATCH, preset, Profile(lang=lang, detail="essential"), _describer(), replay)
            assert (built.analysis.by, built.analysis.status) == ("model", "verified")
    final = next(r for r in rows if r.preset == "final_whistle" and r.lang == "en")
    assert final.attempts == 2 and final.rejected > 0 and final.tools == ["get_recap", "get_stats"] * 2
    assert "| final_whistle | en | 2 | 2 |" in to_markdown(rows, "fake", __import__("datetime").date(2026, 10, 26))


def test_stored_replies_are_not_asked_again(tmp_path):
    replies = {}
    record(FakeAgent(), ledger(tmp_path), replies)
    again = FakeAgent()
    record(again, ledger(tmp_path / "x"), replies)
    assert again.asked == []


def test_the_ledger_stops_the_run_before_the_agent_is_called(tmp_path):
    agent = FakeAgent()
    with pytest.raises(BudgetExceeded):
        record(agent, ledger(tmp_path, per_day=3), {})  # a run holds 3 rounds, then keeps 1: the second run cannot hold 3 more
    assert len(agent.asked) == 1


def test_the_question_names_the_window_and_carries_the_issues():
    session = build_session(MATCH, build_presets(MATCH)[1], Profile(), _describer(), analysis.CodeAnalyst())
    req = analysis.Request(MATCH, build_presets(MATCH)[1], "en", session.recap, session.cues)
    assert "preset='goal_1'" in question(req, []) and "lang='en'" in question(req, [])
    assert "point 1: Brandt is not in recap:2" in question(req, ["point 1: Brandt is not in recap:2"])


def _describer():
    from app.describer import TemplateDescriber

    return TemplateDescriber()
