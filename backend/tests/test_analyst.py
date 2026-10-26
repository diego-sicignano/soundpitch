"""S35: the Analyst agent's points are checked against the line each one cites (SPEC §20)."""

import json

import pytest

from app import analysis
from app.analysis import (
    CodeAnalyst,
    FlawedAnalyst,
    Proposed,
    ReplayAnalyst,
    Request,
    Sources,
    analyse,
    check_point,
)
from app.contracts import Profile
from app.describer import TemplateDescriber
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, build_session

MATCH = generate_match(SEED)
PRESETS = {p.id: p for p in build_presets(MATCH)}
FINAL = PRESETS["final_whistle"]


def request(preset=FINAL, lang="en"):
    session = build_session(MATCH, preset, Profile(lang=lang), TemplateDescriber(), CodeAnalyst())
    return Request(MATCH, preset, lang, session.recap, session.cues)


REQ = request()
SOURCES = Sources(REQ)


def issues(text, source):
    return check_point(Proposed(text, source), SOURCES)


def test_the_sources_are_the_recap_lines_and_the_stats_of_a_minute_not_the_cues():
    assert SOURCES.text("recap:1") == "Full-time: Northgate 2, Harbour 1."
    assert SOURCES.text("stats:45").startswith("Minute 45. Northgate: possession ")
    assert SOURCES.text("recap:99") is None and SOURCES.text("stats:91") is None
    assert SOURCES.text(f"cue:{REQ.cues[0].id}") is None  # cues change with the profile; the recorded analysis must not


def test_a_point_that_states_only_what_its_line_holds_passes():
    assert issues("Marsh opened the scoring in minute 16, set up by Adeyemi.", "recap:2") == []
    assert issues("Northgate pressed hard: 68% of the passes in the five minutes before the opener.", "recap:2") == []


@pytest.mark.parametrize(
    ("text", "source", "issue"),
    [
        ("Rossi opened the scoring in minute 16.", "recap:2", "Rossi"),  # a scorer swapped from another line
        ("Marsh scored in minute 52.", "recap:2", "52"),  # a minute swapped from another goal
        ("Marsh scored.", "recap:9", "no source"),
        ("Marsh scored #1.", "recap:2", "character"),
        ("A tense and open game in which both sides wanted to win.", "recap:2", "no name and no number"),
        ("Marsh " + "and Adeyemi " * 25, "recap:2", "too long"),
    ],
)
def test_a_point_is_rejected_for_what_its_line_does_not_hold(text, source, issue):
    found = issues(text, source)
    assert found and issue in " ".join(found)


def test_a_claim_of_pressure_needs_a_share_of_passes_in_its_line():
    assert issues("Northgate pressed hard before Marsh scored in minute 16.", "recap:2") == []  # recap:2 holds 68%
    found = issues("Marsh won it in minute 78 thanks to Northgate's pressing.", "recap:4")  # recap:4 holds no share
    assert any("pressure or dominance" in issue for issue in found)
    assert any("pressure or dominance" in issue for issue in issues("Northgate dominated: 2 goals.", "recap:1"))


def test_a_stats_point_speaks_of_one_team_with_that_teams_numbers():
    line = SOURCES.text("stats:45")
    home = line.split("Northgate: possession ")[1].split("%")[0]
    away = line.split("Harbour: possession ")[1].split("%")[0]
    assert issues(f"At minute 45 Northgate had {home}% of the passes.", "stats:45") == []
    assert issues("At half-time Northgate had 99% of the passes.", "stats:45")
    if away != home:
        assert "not Northgate's" in " ".join(issues(f"Northgate had {away}% of the passes.", "stats:45"))
    assert "exactly one team" in " ".join(issues(f"Both teams showed {home}% pass accuracy.", "stats:45"))
    assert "exactly one team" in " ".join(issues(f"Northgate {home}%, Harbour {away}%.", "stats:45"))


def test_code_points_pass_and_say_who_wrote_them():
    trace = []
    result = analyse(REQ, CodeAnalyst(), trace)
    assert (result.by, result.status, result.attempts, result.rejected) == ("code", "verified", 1, 0)
    assert [p.source for p in result.points] == ["recap:2", "recap:3", "recap:4", "recap:5"]
    assert [t.step for t in trace] == ["analyst", "analysis_check"]


def test_a_flawed_first_attempt_is_retried_with_its_issues():
    analyst = FlawedAnalyst(bad_attempts=1)
    result = analyse(REQ, analyst, [])
    assert (result.status, result.attempts) == ("verified", 2) and result.rejected > 0
    assert analyst.feedback_seen and all("not in" in issue for issue in analyst.feedback_seen)


def test_an_analyst_that_is_always_wrong_ends_in_the_code_points():
    result = analyse(REQ, FlawedAnalyst(bad_attempts=9), [])
    assert (result.by, result.status, result.attempts) == ("code", "fallback", 2)
    assert result.points == analyse(REQ, CodeAnalyst(), []).points


def test_points_are_kept_in_order_at_most_four_without_repeats():
    class Many:
        by = "model"

        def propose(self, req, attempt, feedback):
            good = CodeAnalyst().propose(req, attempt, feedback)
            return good + good + [Proposed("Rossi scored in minute 16.", "recap:2")]

    result = analyse(REQ, Many(), [])
    assert len(result.points) == 4 and len({p.text for p in result.points}) == 4
    assert result.status == "verified" and result.by == "model"


def test_a_recorded_reply_is_replayed_and_checked(tmp_path):
    good = [
        {"text": "Marsh struck first in minute 16, set up by Adeyemi.", "source": "recap:2"},
        {"text": "Rossi in minute 52 was the only reply.", "source": "recap:2"},  # cites the wrong line
    ]
    store = tmp_path / "analyst.json"
    replies = {analysis.reply_key(REQ, 1, []): json.dumps({"points": good})}
    store.write_text(json.dumps({"version": 1, "model": "fake", "recorded": "2026-10-26", "replies": replies}), encoding="utf-8")
    replay = ReplayAnalyst(analysis.load_store(store))
    result = analyse(REQ, replay, [])
    assert (result.by, result.status) == ("model", "verified")
    assert [p.text for p in result.points] == [good[0]["text"]] and result.rejected == 1
    assert analyse(request(PRESETS["goal_1"]), replay, []).status == "fallback"  # nothing recorded for that window


def test_the_reply_key_follows_the_window_language_and_recap_but_not_the_detail():
    assert analysis.reply_key(REQ, 1, []) != analysis.reply_key(request(lang="it"), 1, [])
    assert analysis.reply_key(REQ, 1, []) != analysis.reply_key(REQ, 2, ["x"])
    full = build_session(MATCH, FINAL, Profile(detail="full"), TemplateDescriber(), CodeAnalyst())
    assert analysis.reply_key(Request(MATCH, FINAL, "en", full.recap, full.cues), 1, []) == analysis.reply_key(REQ, 1, [])


def test_the_session_carries_the_analysis():
    session = build_session(MATCH, FINAL, Profile(), TemplateDescriber(), CodeAnalyst())
    assert session.analysis and session.analysis.status == "verified"
    assert [t.step for t in session.trace][-2:] == ["analyst", "analysis_check"]
