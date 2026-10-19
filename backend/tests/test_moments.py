"""S2: events become prioritised moments; detail levels only filter, never reshape."""

import itertools

from app.match_gen import SEED, generate_match
from app.moments import MIN_PRIORITY, PASS_LIKE, detect_moments
from app.pitch import event_progress

MATCH = generate_match(SEED)
EVENTS = MATCH.events
BY_ID = {e.id: e for e in EVENTS}


def key(moment):
    return (moment.kind, tuple(moment.event_ids))


def test_priority_three_kinds_are_moments_at_every_detail_level():
    for detail in MIN_PRIORITY:
        moments = detect_moments(EVENTS, detail)
        kinds = [m.kind for m in moments if m.priority == 3]
        assert kinds.count("goal") == 3
        assert kinds.count("kickoff") == 5
        assert kinds.count("halftime") == 1 and kinds.count("fulltime") == 1


def test_detail_levels_are_nested():
    essential, standard, full = (
        {key(m) for m in detect_moments(EVENTS, d)} for d in ("essential", "standard", "full")
    )
    assert essential < standard < full


def test_detail_level_sets_the_minimum_priority_except_for_must_say():
    for detail, minimum in MIN_PRIORITY.items():
        assert all(m.priority >= minimum for m in detect_moments(EVENTS, detail))
    assert {m.priority for m in detect_moments(EVENTS, "full")} == {0, 1, 2, 3}


def test_buildups_are_runs_of_one_teams_pass_like_events():
    buildups = [m for m in detect_moments(EVENTS, "full") if m.kind == "buildup"]
    assert buildups
    for m in buildups:
        events = [BY_ID[i] for i in m.event_ids]
        assert {e.kind in PASS_LIKE for e in events} == {True}
        assert {e.team for e in events} == {m.team}
        assert m.event_ids == list(range(m.event_ids[0], m.event_ids[0] + len(m.event_ids)))
        assert m.t == events[-1].t
        reaches_final_third = max(event_progress(e) for e in events) >= 60
        assert m.priority == (1 if reaches_final_third else 0)


def test_a_goal_moment_carries_the_assist():
    for m in (m for m in detect_moments(EVENTS, "essential") if m.kind == "goal"):
        goal = BY_ID[m.event_ids[-1]]
        assert goal.kind == "goal"
        assist = BY_ID[m.event_ids[0]]
        assert assist.kind == "pass" and assist.target == goal.player and assist.team == goal.team


def test_moments_are_sorted_and_numbered_at_every_detail_level():
    for detail in MIN_PRIORITY:
        moments = detect_moments(EVENTS, detail)
        assert [m.id for m in moments] == list(range(1, len(moments) + 1))
        assert all(a.t <= b.t for a, b in itertools.pairwise(moments))


def test_a_window_only_yields_its_own_events():
    window = [e for e in EVENTS if 800 <= e.t <= 1000]
    moments = detect_moments(window, "standard")
    ids = {e.id for e in window}
    assert moments and all(set(m.event_ids) <= ids for m in moments)


def test_score_reminders_every_ten_minutes():
    reminders = [m for m in detect_moments(EVENTS, "essential") if m.kind == "score_update"]
    assert [m.t for m in reminders] == [600 * k for k in range(1, 9)]
    assert all(m.priority == 2 and m.team is None for m in reminders)
