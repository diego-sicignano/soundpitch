"""S18: a player or club focus raises its moments and its ball sounds, and changes nothing without a focus."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.contracts import Profile, Session
from app.describer import TemplateDescriber
from app.main import app
from app.match_gen import SEED, generate_match
from app.moments import detect_moments
from app.pipeline import build_presets, build_session

MATCH = generate_match(SEED)
EVENTS = MATCH.events
BY_ID = {e.id: e for e in EVENTS}
GOAL = {p.id: p for p in build_presets(MATCH)}["goal_1"]
client = TestClient(app)


def involves(moment, team, shirt=None):
    if moment.kind == "score_update":
        return False
    return any(
        BY_ID[i].team == team and (shirt is None or shirt in (BY_ID[i].player, BY_ID[i].target)) for i in moment.event_ids
    )


def busiest_player():
    """The player with the most low-priority moments, so the test raises something real."""
    counts = {}
    for moment in detect_moments(EVENTS, "full"):
        if moment.priority < 2:
            for i in moment.event_ids:
                event = BY_ID[i]
                if event.team and event.player:
                    counts[(event.team, event.player)] = counts.get((event.team, event.player), 0) + 1
    return max(counts, key=counts.get)


TEAM, SHIRT = busiest_player()


def test_focus_raises_the_players_moments_by_one_up_to_two_and_leaves_the_rest():
    plain = detect_moments(EVENTS, "full")
    focused = detect_moments(EVENTS, "full", (TEAM, SHIRT))
    assert [(m.kind, m.event_ids) for m in focused] == [(m.kind, m.event_ids) for m in plain]
    raised = 0
    for before, after in zip(plain, focused, strict=True):
        if before.priority < 3 and involves(before, TEAM, SHIRT):
            assert after.priority == min(before.priority + 1, 2)
            raised += after.priority != before.priority
        else:
            assert after.priority == before.priority
    assert raised > 0


def key(moment):
    return (moment.kind, tuple(moment.event_ids))


def test_focus_is_applied_before_the_detail_filter():
    plain = {key(m) for m in detect_moments(EVENTS, "standard")}
    focused = {key(m) for m in detect_moments(EVENTS, "standard", (TEAM, SHIRT))}
    assert plain < focused


def test_without_a_focus_nothing_changes():
    assert detect_moments(EVENTS, "standard", None) == detect_moments(EVENTS, "standard")
    plain = build_session(MATCH, GOAL, Profile(), TemplateDescriber())
    assert plain.profile.focus is None and plain.profile.focus_team is None


@pytest.mark.parametrize("calm", [False, True])
def test_the_players_ball_sounds_are_louder_capped_at_one(calm):
    window = [e for e in EVENTS if GOAL.from_s <= e.t <= GOAL.to_s]
    plain = build_session(MATCH, GOAL, Profile(calm=calm), TemplateDescriber())
    focused = build_session(MATCH, GOAL, Profile(calm=calm, focus=SHIRT, focus_team=TEAM), TemplateDescriber())
    kept = [e for e in window if not calm or e.kind in ("goal", "kickoff", "foul", "halftime", "fulltime")]
    assert len(plain.earcons) == len(focused.earcons) == len(kept)
    for event, before, after in zip(kept, plain.earcons, focused.earcons, strict=True):
        mine = event.team == TEAM and SHIRT in (event.player, event.target)
        assert after.gain == (min(1.0, round(before.gain * 1.5, 3)) if mine else before.gain)
        assert after.gain <= 1.0


def test_a_club_focus_raises_every_moment_of_that_club():
    plain = detect_moments(EVENTS, "full")
    focused = detect_moments(EVENTS, "full", ("away", None))
    for before, after in zip(plain, focused, strict=True):
        expected = min(before.priority + 1, 2) if before.priority < 3 and involves(before, "away") else before.priority
        assert after.priority == expected
    assert sum(a.priority != b.priority for a, b in zip(plain, focused, strict=True)) > 10


def test_the_clubs_ball_sounds_are_louder():
    plain = build_session(MATCH, GOAL, Profile(), TemplateDescriber())
    club = build_session(MATCH, GOAL, Profile(focus_team="home"), TemplateDescriber())
    window = [e for e in EVENTS if GOAL.from_s <= e.t <= GOAL.to_s]
    for event, before, after in zip(window, plain.earcons, club.earcons, strict=True):
        assert after.gain == (min(1.0, round(before.gain * 1.5, 3)) if event.team == "home" else before.gain)


def test_a_shirt_needs_its_side():
    with pytest.raises(ValidationError):
        Profile(focus=9)
    assert Profile(focus_team="home").focus is None  # a club alone is a valid focus


def test_the_api_takes_a_focus_and_refuses_an_invalid_one():
    response = client.get("/api/session", params={"preset": "goal_1", "focus": SHIRT, "focus_team": TEAM})
    assert response.status_code == 200
    session = Session.model_validate(response.json())
    assert (session.profile.focus, session.profile.focus_team) == (SHIRT, TEAM)
    assert client.get("/api/session", params={"focus": 99, "focus_team": "home"}).status_code == 422
    assert client.get("/api/session", params={"focus": SHIRT}).status_code == 422
    club = Session.model_validate(client.get("/api/session", params={"focus_team": "away"}).json())
    assert (club.profile.focus, club.profile.focus_team) == (None, "away")
    assert client.get("/api/cuesheet", params={"focus": 99, "focus_team": "away"}).status_code == 422
