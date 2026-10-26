"""S33: match statistics counted by code from the events (SPEC §18)."""

import itertools

from app.contracts import Event, Profile
from app.describer import TemplateDescriber
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, build_session
from app.stats import count, points

MATCH = generate_match(SEED)
PRESETS = {p.id: p for p in build_presets(MATCH)}


def event(n, kind, team, x, y=50, half=1):
    return Event(
        id=n, t=n * 5, minute=1, half=half, team=team, player=7 if team else None, target=None,
        kind=kind, x=x, y=y, lane=None, home_score=0, away_score=0,
    )


SEQUENCE = [
    event(1, "kickoff", "home", 50),
    event(2, "pass", "home", 60),  # 10 of 100 along: 10.5 m; then a foul by the other side: completed
    event(3, "foul", "away", 40),
    event(4, "free_kick", "home", 64),
    event(5, "pass", "home", 70),  # 6.3 m; then an interception: not completed
    event(6, "interception", "away", 30),
    event(7, "shot_on_target", "away", 10),
    event(8, "save", "home", 4),
    event(9, "pass", "away", 60, y=20),  # open at half-time: never resolved
    event(10, "halftime", None, 50),
    event(11, "kickoff", "away", 50, half=2),
    event(12, "goal", "away", 96, half=2),
]


def test_counts_follow_the_rules_of_section_18():
    home, away = count(SEQUENCE)
    assert (home.passes, home.passes_completed, home.pass_accuracy) == (2, 1, 50)
    assert home.avg_pass_m == 8.4
    assert (away.passes, away.passes_completed, away.pass_accuracy) == (1, 0, 0)
    assert (home.possession, away.possession) == (67, 33)
    assert (away.shots, away.shots_on_target, home.shots) == (2, 2, 0)
    assert (away.ball_won, home.ball_won) == (1, 0)


def test_recent_possession_counts_only_the_last_five_minutes():
    passes = [event(1, "pass", "home", 50), event(2, "pass", "home", 60), event(3, "pass", "away", 40)]
    passes = [passes[0].model_copy(update={"t": 0}), passes[1].model_copy(update={"t": 10}), passes[2].model_copy(update={"t": 400})]
    home, away = count(passes)
    assert (home.possession, away.possession) == (67, 33)  # since kick-off
    assert (home.recent_possession, away.recent_possession) == (0, 100)  # 0 s and 10 s are more than 300 s before 400 s
    home, away = count(SEQUENCE)
    assert (home.recent_possession, away.recent_possession) == (67, 33)  # every pass is in the last five minutes


def test_before_any_pass_possession_is_shared():
    home, away = count(SEQUENCE[:1])
    assert (home.possession, away.possession) == (50, 50)
    assert home.avg_pass_m == 0 and home.pass_accuracy == 0


def test_the_points_of_a_window():
    for preset in PRESETS.values():
        window = [e for e in MATCH.events if preset.from_s <= e.t <= preset.to_s]
        result = points(MATCH.events, preset.from_s, preset.to_s)
        assert len(result) == len(window) + 1
        assert result[0].t_ms == 0
        assert (result[0].home, result[0].away) == count([e for e in MATCH.events if e.t < preset.from_s])
        assert (result[-1].home, result[-1].away) == count([e for e in MATCH.events if e.t <= preset.to_s])
        assert [p.t_ms for p in result[1:]] == [(e.t - preset.from_s) * 1000 for e in window]
        for a, b in itertools.pairwise(result):
            assert a.t_ms <= b.t_ms
            for side in ("home", "away"):
                before, after = getattr(a, side), getattr(b, side)
                for field in ("passes", "passes_completed", "shots", "shots_on_target", "ball_won"):
                    assert getattr(after, field) >= getattr(before, field)
        for p in result:
            assert p.home.possession + p.away.possession == 100
            assert p.home.recent_possession + p.away.recent_possession == 100


def test_a_session_carries_its_statistics():
    preset = PRESETS["goal_1"]
    session = build_session(MATCH, preset, Profile(), TemplateDescriber())
    assert session.stats == points(MATCH.events, preset.from_s, preset.to_s)
    assert session.stats[-1].home.passes > 0
