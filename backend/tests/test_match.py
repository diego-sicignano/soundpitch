"""S1: the synthetic match is deterministic, has the pinned storyline and valid geometry."""

import itertools
from collections import Counter

from app.match_gen import GOALS, SEED, generate_match
from app.pitch import attacks_right, lane_of, progress

MATCH = generate_match(SEED)
EVENTS = MATCH.events


def test_same_seed_is_identical_and_other_seeds_differ():
    assert generate_match(SEED) == MATCH
    assert generate_match(1) != MATCH


def test_ids_are_sequential_and_time_never_goes_back():
    assert [e.id for e in EVENTS] == list(range(1, len(EVENTS) + 1))
    assert all(a.t <= b.t for a, b in itertools.pairwise(EVENTS))
    assert all(e.minute == e.t // 60 + 1 and 1 <= e.minute <= 90 for e in EVENTS)
    assert all((e.half == 1) == (e.t < 2700) for e in EVENTS)


def test_storyline_goals_and_final_score():
    goals = [(e.minute, e.team) for e in EVENTS if e.kind == "goal"]
    assert goals == list(GOALS) == [(16, "home"), (52, "away"), (78, "home")]
    last = EVENTS[-1]
    assert (last.kind, last.home_score, last.away_score) == ("fulltime", 2, 1)
    assert [(e.kind, e.minute) for e in EVENTS if e.kind in ("halftime", "fulltime")] == [
        ("halftime", 45),
        ("fulltime", 90),
    ]


def test_the_score_only_changes_on_goals():
    for before, after in itertools.pairwise(EVENTS):
        scored = after.kind == "goal"
        total = lambda e: e.home_score + e.away_score
        assert total(after) - total(before) == (1 if scored else 0)


def test_coordinates_and_lanes_follow_the_attacking_direction():
    for e in EVENTS:
        if e.team is None:
            assert e.lane is None
            continue
        assert e.lane == lane_of(e.y, e.team, e.half)
    home_first_half = [e for e in EVENTS if e.team == "home" and e.half == 1 and e.kind == "goal"]
    assert attacks_right("home", 1) and not attacks_right("home", 2)
    assert all(e.x > 80 for e in home_first_half)  # home scores at the right-hand goal
    assert progress("away", 2, 95) == 95 and progress("home", 2, 95) == 5


def test_every_actor_belongs_to_the_acting_team():
    shirts = {"home": {p.shirt for p in MATCH.home.players}, "away": {p.shirt for p in MATCH.away.players}}
    for e in EVENTS:
        if e.team:
            assert e.player in shirts[e.team]
            assert e.target is None or e.target in shirts[e.team]


def test_rosters_have_unique_shirts_and_surnames():
    for team in (MATCH.home, MATCH.away):
        assert len(team.players) == 11
        assert len({p.shirt for p in team.players}) == 11
    names = [p.name for p in MATCH.home.players + MATCH.away.players]
    assert len(set(names)) == 22


def test_the_match_looks_like_football():
    kinds = Counter(e.kind for e in EVENTS)
    passes = kinds["pass"] + kinds["long_ball"]
    shots = sum(kinds[k] for k in ("shot_on_target", "shot_off_target", "shot_blocked", "goal"))
    assert 400 <= len(EVENTS) <= 1400
    assert passes > 0.4 * len(EVENTS)
    assert 6 <= shots <= 40
    assert kinds["save"] >= 1 and kinds["corner"] >= 1 and kinds["foul"] >= 1
