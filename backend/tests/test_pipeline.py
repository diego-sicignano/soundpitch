"""S4 (retry and fallback), S6 (profiles) and the real-session guarantees of S5."""

import pytest

from app.contracts import Profile, Session
from app.describer import FlawedDescriber, TemplateDescriber
from app.match_gen import SEED, generate_match
from app.pipeline import MAX_ATTEMPTS, build_presets, build_session, describer_from_env
from app.render import webvtt
from app.timing import GAP_MS, MAX_LAG_MS

MATCH = generate_match(SEED)
PRESETS = {p.id: p for p in build_presets(MATCH)}
GOAL = PRESETS["goal_1"]


def session(detail="standard", describer=None, preset=GOAL, **profile):
    return build_session(MATCH, preset, Profile(detail=detail, **profile), describer or TemplateDescriber())


def test_presets_cover_the_key_moments():
    assert list(PRESETS) == ["kickoff", "goal_1", "goal_2", "goal_3", "final_whistle"]
    for n in (1, 2, 3):
        goal = [e for e in MATCH.events if e.kind == "goal"][n - 1]
        preset = PRESETS[f"goal_{n}"]
        assert preset.from_s < goal.t < preset.to_s
    assert PRESETS["goal_2"].title == "Goal 2: Harbour, minute 52"


def test_a_clean_run_verifies_everything_on_the_first_attempt():
    s = session()
    assert s.report.attempts == 1 and s.report.fallback == 0
    assert s.report.verified == s.report.moments
    assert [(t.step, t.status) for t in s.trace] == [
        ("moment_detector", "ok"),
        ("describer", "ok"),
        ("verifier", "ok"),
        ("timing", "ok"),
    ]
    assert {c.status for c in s.cues} == {"verified"}


def test_bad_then_good_is_verified_after_one_retry():
    clean = session()
    retried = session(describer=FlawedDescriber(bad_attempts=1))
    assert retried.report.attempts == 2 and retried.report.fallback == 0
    assert [(t.step, t.status, t.attempt) for t in retried.trace[1:5]] == [
        ("describer", "ok", 1),
        ("verifier", "failed", 1),
        ("describer", "ok", 2),
        ("verifier", "ok", 2),
    ]
    assert "rejected" in retried.trace[2].detail
    assert [c.text for c in retried.cues] == [c.text for c in clean.cues]
    assert {c.status for c in retried.cues} == {"verified"}


def test_always_bad_falls_back_to_templates_and_stays_complete():
    clean = session()
    fallback = session(describer=FlawedDescriber(bad_attempts=99))
    assert fallback.report.attempts == MAX_ATTEMPTS
    assert fallback.report.fallback == fallback.report.moments and fallback.report.verified == 0
    assert {c.status for c in fallback.cues} == {"fallback"}
    assert [c.text for c in fallback.cues] == [c.text for c in clean.cues]
    assert sum(1 for t in fallback.trace if t.step == "verifier" and t.status == "failed") == 3


def test_a_describer_that_crashes_costs_an_attempt_not_the_session():
    class Crashing:
        def describe(self, moments, ctx, feedback, attempt):
            raise RuntimeError("model unavailable")

    s = session(describer=Crashing())
    assert s.report.fallback == s.report.moments and s.cues
    assert [t.status for t in s.trace if t.step == "describer"][:3] == ["failed"] * 3


def test_real_sessions_never_overlap_and_always_say_the_must_say_moments():
    for preset in PRESETS.values():
        for detail in ("essential", "standard", "full"):
            s = session(detail, preset=preset)
            assert s.report.overlaps == 0
            assert all(b.start_ms >= a.end_ms + GAP_MS for a, b in zip(s.cues, s.cues[1:]))
            must = s.report.by_priority["3"]
            assert must.total == must.scheduled
            assert all(c.start_ms >= 0 for c in s.cues)


def test_cues_start_close_to_their_moment():
    s = session("full")
    for cue in (c for c in s.cues if c.priority < 3):
        moment_ms = min(e.t for e in MATCH.events if e.id == cue.event_ids[-1]) * 1000 - GOAL.from_s * 1000
        assert cue.start_ms <= moment_ms + MAX_LAG_MS[cue.priority]


def test_detail_levels_add_cues():
    counts = [len(session(d, preset=PRESETS["goal_2"]).cues) for d in ("essential", "standard", "full")]
    assert counts[0] < counts[1] < counts[2]


def test_italian_describes_the_same_events_as_english():
    en, it = session(lang="en"), session(lang="it")
    by_moment = {c.moment_id: c for c in en.cues}
    shared = [c for c in it.cues if c.moment_id in by_moment]
    assert len(shared) >= 0.8 * len(en.cues)
    assert all(c.event_ids == by_moment[c.moment_id].event_ids for c in shared)
    assert all(c.text != by_moment[c.moment_id].text for c in shared)
    assert it.lang == "it"


def test_earcons_follow_the_ball_and_calm_mode_keeps_only_goals_and_whistles():
    s = session()
    assert s.earcons and all(-1 <= e.pan <= 1 and 0 <= e.pitch <= 1 for e in s.earcons)
    window = [e for e in MATCH.events if GOAL.from_s <= e.t <= GOAL.to_s]
    assert len(s.earcons) == len(window)
    for earcon, event in zip(s.earcons, window):
        assert (earcon.pan > 0) == (event.x > 50) or earcon.pan == 0
    calm = session(calm=True)
    assert {e.kind for e in calm.earcons} <= {"goal", "whistle", "whistle_long"}
    assert {e.gain for e in calm.earcons} == {0.3}
    assert session(earcons=False).earcons == []


def test_calm_mode_slows_speech_down():
    normal, calm = session("full", rate=1.4), session("full", rate=1.4, calm=True)
    per_word = lambda s: sum(c.end_ms - c.start_ms for c in s.cues) / sum(len(c.text.split()) for c in s.cues)
    assert per_word(calm) > per_word(normal)


def test_the_session_carries_the_starting_score_and_a_ball_track():
    s = session(preset=PRESETS["goal_2"])
    assert (s.start_home_score, s.start_away_score) == (1, 0)
    assert s.track and s.track[0].t_ms >= 0 and s.track[-1].away_score == 1
    assert session(preset=PRESETS["kickoff"]).start_home_score == 0


def test_a_session_round_trips_through_json():
    s = session()
    assert Session.model_validate_json(s.model_dump_json()) == s


def test_webvtt_is_well_formed():
    vtt = webvtt(session().cues)
    lines = vtt.splitlines()
    assert lines[0] == "WEBVTT" and lines[1] == ""
    assert lines[3].count(" --> ") == 1 and lines[3][:2] == "00" and "." in lines[3]


@pytest.mark.parametrize(
    "mode,attempts", [("scripted", 1), ("bad_then_good", 2), ("always_bad", MAX_ATTEMPTS)]
)
def test_the_environment_selects_the_describer(monkeypatch, mode, attempts):
    monkeypatch.setenv("SOUNDPITCH_LLM", mode)
    assert session(describer=describer_from_env()).report.attempts == attempts
    monkeypatch.setenv("SOUNDPITCH_LLM", "nope")
    with pytest.raises(ValueError):
        describer_from_env()


def test_the_evaluation_harness_meets_s10():
    from app.evaluate import evaluate

    result = evaluate([SEED, 1, 2])
    totals = result["totals"]
    assert totals["overlaps"] == 0
    assert totals["priority"]["3"][0] == totals["priority"]["3"][1] > 0
    for applicable, caught in result["planted"].values():
        assert applicable > 0 and caught == applicable
    assert totals["retry_ok"] == totals["retry_runs"] and totals["fallback_ok"] == totals["fallback_runs"]


def test_foundry_mode_asks_for_its_settings_by_name(monkeypatch):
    from app import foundry

    for key in ("FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SOUNDPITCH_LLM", "foundry")
    foundry.reset_shared()
    with pytest.raises(foundry.FoundryNotConfigured, match="FOUNDRY_PROJECT_ENDPOINT"):
        describer_from_env()


def test_foundry_mode_hands_back_the_one_shared_describer(monkeypatch, tmp_path):
    from app import foundry
    from app.usage import UsageLedger

    ledger = UsageLedger(tmp_path / "u.sqlite", per_minute=1, per_day=1, tokens_per_day=1, eur_per_month=1.0)
    shared = foundry.FoundryDescriber(client=object(), ledger=ledger)
    monkeypatch.setenv("SOUNDPITCH_LLM", "foundry")
    monkeypatch.setattr(foundry, "_SHARED", shared)
    assert describer_from_env() is shared and describer_from_env() is shared
