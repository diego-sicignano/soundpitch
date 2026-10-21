"""S31: the context sentence of a goal, half-time and full-time comes from the score state, in code (SPEC §5, Stakes)."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.clips_build import sentences
from app.contracts import CueSheet, Description, Event, Match, Moment, Player, Profile, TeamInfo
from app.describer import Context, TemplateDescriber, render
from app.match_gen import SEED, generate_match
from app.moments import detect_moments
from app.pipeline import build_presets, build_session, window_of
from app.replay import ReplayDescriber, load_store
from app.stakes import context
from app.timing import Candidate, plan

client = TestClient(main.app)
MATCH = generate_match(SEED)
PRESETS = {p.id: p for p in build_presets(MATCH)}


def team(side, name, short):
    return TeamInfo(side=side, name=name, short=short, players=[Player(shirt=9, name="Marsh", role="fwd")])


def event(id, kind, side, home, away):
    return Event(
        id=id, t=id * 10, minute=id, half=1, team=side, player=9 if side else None, target=None, kind=kind,
        x=50, y=50, lane="centre" if side else None, home_score=home, away_score=away,
    )  # fmt: skip


def small_match(*events):
    home, away = team("home", "Northgate Red", "Northgate"), team("away", "Harbour Blue", "Harbour")
    return Match(seed=0, home=home, away=away, events=list(events))


def goal_context(before, scorer, lang="en"):
    """The context of a goal by `scorer` when the score before it is `before` = (home, away)."""
    home, away = before
    after = (home + (scorer == "home"), away + (scorer == "away"))
    match = small_match(event(1, "pass", scorer, *before), event(2, "goal", scorer, *after))
    moment = Moment(id=1, t=20, priority=3, kind="goal", team=scorer, event_ids=[2])
    return context(moment, Context(match, lang))


def whistle_context(kind, score, lang="en"):
    match = small_match(event(1, kind, None, *score))
    moment = Moment(id=1, t=10, priority=3, kind=kind, team=None, event_ids=[1])
    return context(moment, Context(match, lang))


GOALS = [  # score before, scorer, English, Italian
    ((0, 0), "home", "The opening goal of the match.", "È il primo gol della partita."),
    ((0, 0), "away", "The opening goal of the match.", "È il primo gol della partita."),
    ((0, 1), "home", "That makes it level.", "Il risultato torna in parità."),
    ((1, 0), "away", "That makes it level.", "Il risultato torna in parità."),
    ((1, 1), "home", "Northgate take the lead.", "Northgate passa in vantaggio."),
    ((1, 1), "away", "Harbour take the lead.", "Harbour passa in vantaggio."),
    ((1, 0), "home", "Northgate extend their lead.", "Northgate allunga."),
    ((0, 2), "away", "Harbour extend their lead.", "Harbour allunga."),
    ((0, 2), "home", "Northgate pull one back.", "Northgate accorcia le distanze."),
    ((3, 0), "away", "Harbour pull one back.", "Harbour accorcia le distanze."),
    ((2, 1), "home", "Northgate extend their lead.", "Northgate allunga."),
]


@pytest.mark.parametrize(("before", "scorer", "english", "italian"), GOALS)
def test_a_goal_says_what_it_does_to_the_score_for_both_teams_in_both_languages(before, scorer, english, italian):
    assert goal_context(before, scorer, "en") == english
    assert goal_context(before, scorer, "it") == italian


def test_no_goal_context_claims_a_win_or_a_result():
    for _before, _scorer, english, italian in GOALS:
        assert "win" not in english.lower() and "ends" not in english.lower()
        assert "vince" not in italian.lower() and "finisce" not in italian.lower()


@pytest.mark.parametrize(
    ("score", "english", "italian"),
    [
        ((0, 0), "All square at the break.", "Parità all'intervallo."),
        ((1, 1), "All square at the break.", "Parità all'intervallo."),
        ((1, 0), "Northgate lead at the break.", "Northgate avanti all'intervallo."),
        ((0, 3), "Harbour lead at the break.", "Harbour avanti all'intervallo."),
    ],
)
def test_half_time_says_who_leads_or_that_it_is_level(score, english, italian):
    assert whistle_context("halftime", score, "en") == english
    assert whistle_context("halftime", score, "it") == italian


@pytest.mark.parametrize(
    ("score", "english", "italian"),
    [
        ((2, 1), "Northgate win.", "Vince Northgate."),
        ((0, 1), "Harbour win.", "Vince Harbour."),
        ((2, 2), "The match ends level.", "Finisce in parità."),
        ((0, 0), "The match ends level.", "Finisce in parità."),
    ],
)
def test_full_time_says_who_won_or_that_it_ended_level(score, english, italian):
    assert whistle_context("fulltime", score, "en") == english
    assert whistle_context("fulltime", score, "it") == italian


def test_an_inconsistent_or_unknown_state_gives_no_context():
    moment = Moment(id=1, t=20, priority=3, kind="goal", team="home", event_ids=[2])
    ctx = lambda *events: Context(small_match(*events), "en")
    # the event before the goal does not hold the score before the goal
    assert context(moment, ctx(event(1, "pass", "home", 0, 0), event(2, "goal", "home", 3, 0))) is None
    # the goal does not add to the scorer's score (a score before the goal would be negative)
    assert context(moment, ctx(event(1, "pass", "home", 0, 0), event(2, "goal", "home", 0, 0))) is None
    # no scorer
    assert context(moment, ctx(event(1, "pass", "home", 0, 0), event(2, "goal", None, 1, 0))) is None
    # the goal is the first event we hold: nothing contradicts the arithmetic
    assert context(moment, ctx(event(2, "goal", "home", 1, 0))) == "The opening goal of the match."


def test_only_goals_and_whistles_get_context_in_the_whole_match():
    for lang in ("en", "it"):
        ctx = Context(MATCH, lang)
        for moment in detect_moments(MATCH.events, "full"):
            found = context(moment, ctx)
            assert (found is not None) == (moment.kind in ("goal", "halftime", "fulltime")), moment.kind
            assert found is None or len(found) < 60


def test_the_storyline_is_explained_from_the_events():
    ctx = Context(MATCH, "en")
    by_kind: dict[str, list[str]] = {}
    for moment in detect_moments(MATCH.events, "essential"):
        found = context(moment, ctx)
        if found:
            by_kind.setdefault(moment.kind, []).append(found)
    assert by_kind["goal"] == ["The opening goal of the match.", "That makes it level.", "Northgate take the lead."]
    assert by_kind["halftime"] == ["Northgate lead at the break."]
    assert by_kind["fulltime"] == ["Northgate win."]


def test_a_full_cue_ends_with_the_context_and_exposes_it_apart():
    for lang, expected in (("en", "The opening goal of the match."), ("it", "È il primo gol della partita.")):
        session = build_session(MATCH, PRESETS["goal_1"], Profile(lang=lang), TemplateDescriber())
        goal = next(c for c in session.cues if c.priority == 3 and c.context)
        assert goal.variant == "full" and goal.context == expected
        assert goal.text.endswith(" " + expected) and len(goal.text) <= 400
        assert goal.status == "verified"
        assert session.report.verified == session.report.moments and session.report.fallback == 0
    kickoff = build_session(MATCH, PRESETS["kickoff"], Profile(), TemplateDescriber())
    assert all(c.context is None for c in kickoff.cues)


def test_the_cue_text_is_the_verified_description_plus_the_context():
    preset = PRESETS["goal_3"]
    session = build_session(MATCH, preset, Profile(), TemplateDescriber())
    goal = next(c for c in session.cues if c.context)
    moment = next(m for m in detect_moments(window_of(MATCH, preset), "standard") if m.id == goal.moment_id)
    verified_full = render(moment, Context(MATCH, "en")).full
    assert goal.text == f"{verified_full} Northgate take the lead."


def test_a_short_cue_has_no_context():
    moment = Moment(id=1, t=10, priority=0, kind="shot", team="home", event_ids=[1])
    description = Description(
        moment_id=1, lang="en", full=" ".join(["word"] * 40) + " Ctx here.", short="word word", refs=[]
    )
    blocker = Moment(id=2, t=12, priority=3, kind="goal", team="home", event_ids=[2])
    long_description = Description(moment_id=2, lang="en", full=" ".join(["word"] * 40), short="word", refs=[])
    cues, _ = plan(
        [
            Candidate(blocker, long_description, "verified", 0.0),
            Candidate(moment, description, "verified", 0.0, "Ctx here."),
        ],
        0,
        1.0,
    )
    shot = next(c for c in cues if c.moment_id == 1)
    assert shot.variant == "short" and shot.context is None and shot.text == "word word"


def test_the_replayed_session_keeps_the_recorded_words_and_adds_only_the_context():
    store = load_store()
    assert store.replies, "the committed replay file must hold recorded replies"
    for preset in PRESETS.values():
        for lang in ("en", "it"):
            replayed = build_session(MATCH, preset, Profile(lang=lang), ReplayDescriber(store))
            assert replayed.report.fallback == 0, (preset.id, lang)
            assert any("recorded Foundry reply" in t.detail for t in replayed.trace)
            for cue in replayed.cues:
                if cue.context:
                    assert cue.variant == "full" and cue.text.endswith(" " + cue.context)


def test_the_cue_sheet_carries_the_context_and_stays_valid():
    sheet = CueSheet.model_validate(client.get("/api/cuesheet", params={"preset": "goal_2"}).json())
    contexts = [i.context for i in sheet.items if i.type != "ball_sound" and i.context]
    assert contexts == ["That makes it level."] * 2  # the description and its caption
    session = client.get("/api/session", params={"preset": "goal_2"}).json()
    assert [c["context"] for c in session["cues"] if c["context"]] == ["That makes it level."]


def test_text_with_context_is_issued_for_speech_but_the_context_alone_is_not(monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)  # never reach Azure from a test
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    session = client.get("/api/session", params={"preset": "goal_3", "lang": "it"}).json()
    with_context = next(c for c in session["cues"] if c["context"])
    assert with_context["context"] == "Northgate passa in vantaggio."
    issued = client.post("/api/tts", json={"text": with_context["text"], "lang": "it"})
    assert issued.status_code == 501  # allowed through the guard; Speech is not configured here
    alone = client.post("/api/tts", json={"text": with_context["context"], "lang": "it"})
    assert alone.status_code == 403


def test_the_clip_list_includes_the_texts_with_their_context():
    found = {text for lang, text in sentences() if lang == "en"}
    assert any(text.endswith(" Northgate take the lead.") for text in found)
    assert any(text.endswith(" Northgate win.") for text in found)


def test_the_italian_phrases_use_the_singular_with_a_club_name():
    """A club name is one subject in Italian sports prose ("Northgate passa in vantaggio"); the plural forms the
    first version used ("passano", "allungano") agree with the players, not with the name."""
    from app.stakes import PHRASES

    italian = " ".join(PHRASES["it"].values()).lower()
    for plural in ("passano", "allungano", "aumentano", "accorciano", "vincono"):
        assert plural not in italian
    assert "{team}" in PHRASES["it"]["lead"] and PHRASES["it"]["lead"].startswith("{team} passa ")


def test_the_page_does_not_say_the_score_context_is_checked_against_the_events():
    """The context sentence is appended after the verifier, so the page's own claim must not cover it (S31)."""
    page = (main.FRONTEND / "index.html").read_text(encoding="utf-8")
    claim = page.split('class="tagline"')[1].split("</p>")[0]
    assert "checked against the match events" in claim
    assert "worked out by code from the score" in claim  # the claim names what the verifier does not cover
