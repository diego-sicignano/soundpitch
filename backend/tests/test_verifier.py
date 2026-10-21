"""S3: the verifier accepts what the events support and rejects everything else."""

import re

import pytest

from app.contracts import Description, FactRef
from app.describer import Context, FlawedDescriber, TemplateDescriber
from app.match_gen import SEED, generate_match
from app.moments import detect_moments
from app.verifier import Verifier

MATCH = generate_match(SEED)
MOMENTS = detect_moments(MATCH.events, "full")
BY_KIND = {}
for _m in MOMENTS:
    BY_KIND.setdefault(_m.kind, _m)


def setup(lang="en"):
    ctx = Context(MATCH, lang)
    return ctx, Verifier(ctx), TemplateDescriber().describe(MOMENTS, ctx, {}, 1)


@pytest.mark.parametrize("lang", ["en", "it"])
def test_every_template_description_passes_verification(lang):
    _ctx, verifier, described = setup(lang)
    assert len(described) == len(MOMENTS)
    for moment in MOMENTS:
        assert verifier.check(moment, described[moment.id]) == [], (moment, described[moment.id])


def test_every_moment_kind_is_covered_by_the_templates():
    kinds = {m.kind for m in MOMENTS}
    assert kinds >= {"kickoff", "goal", "halftime", "fulltime", "shot", "save", "corner", "free_kick",
                     "turnover", "foul", "throw_in", "buildup", "score_update"}


def test_italian_and_english_describe_the_same_events():
    _, _, en = setup("en")
    _, _, it = setup("it")
    for moment in MOMENTS:
        assert en[moment.id].refs == it[moment.id].refs
        assert en[moment.id].full != it[moment.id].full


def test_a_goal_is_announced_with_scorer_team_and_score():
    ctx, _, described = setup()
    goal = BY_KIND["goal"]
    text = described[goal.id].full
    scorer = ctx.by_id[goal.event_ids[-1]]
    assert ctx.name(scorer.team, scorer.player) in text and "Northgate" in text and "1" in text


def test_a_wrong_ref_is_rejected():
    _, verifier, described = setup()
    moment = BY_KIND["shot"]
    good = described[moment.id]
    first = good.refs[0]
    wrong = FactRef(event_id=first.event_id, field=first.field, value="home" if first.value == "away" else "away")
    bad = good.model_copy(update={"refs": [wrong, *good.refs[1:]]})
    issues = verifier.check(moment, bad)
    assert len(issues) == 1 and f"event {first.event_id}" in issues[0]


def test_a_ref_outside_the_moment_is_rejected():
    _, verifier, described = setup()
    moment = BY_KIND["shot"]
    good = described[moment.id]
    stray = FactRef(event_id=1, field="kind", value="kickoff")
    assert verifier.check(moment, good.model_copy(update={"refs": [*good.refs, stray]}))


def test_a_player_who_is_not_in_the_moment_is_rejected():
    ctx, verifier, described = setup()
    moment = BY_KIND["shot"]
    good = described[moment.id]
    shooter = ctx.name(ctx.by_id[moment.event_ids[0]].team, ctx.by_id[moment.event_ids[0]].player)
    bad = good.model_copy(update={"full": good.full.replace(shooter, "Rossi" if shooter != "Rossi" else "Silva")})
    issues = verifier.check(moment, bad)
    assert any("not in this moment" in i for i in issues)


def test_a_stray_number_is_rejected_and_the_score_is_allowed():
    _, verifier, described = setup()
    moment = BY_KIND["goal"]
    good = described[moment.id]
    assert verifier.check(moment, good) == []
    bad = good.model_copy(update={"full": good.full + " That is his 5th of the season."})
    assert any("number 5" in i for i in verifier.check(moment, bad))


def test_over_long_or_inverted_text_is_rejected():
    _, verifier, described = setup()
    moment = BY_KIND["shot"]
    good = described[moment.id]
    long_full = " ".join(["word"] * 46)
    assert any("full" in i for i in verifier.check(moment, good.model_copy(update={"full": long_full})))
    long_short = " ".join(["word"] * 16)
    assert any("short" in i for i in verifier.check(moment, good.model_copy(update={"short": long_short})))
    inverted = good.model_copy(update={"short": good.full + " extra"})
    assert any("longer" in i for i in verifier.check(moment, inverted))
    assert verifier.check(moment, good.model_copy(update={"short": ""}))


def test_the_flawed_describer_is_always_caught_while_it_is_flawed():
    ctx = Context(MATCH, "en")
    verifier = Verifier(ctx)
    flawed = FlawedDescriber(bad_attempts=1)
    first = flawed.describe(MOMENTS, ctx, {}, 1)
    assert all(verifier.check(m, first[m.id]) for m in MOMENTS)
    second = flawed.describe(MOMENTS, ctx, {}, 2)
    assert all(verifier.check(m, second[m.id]) == [] for m in MOMENTS)


def test_templates_never_use_digits_except_scores_and_minutes():
    _, _, described = setup()
    for d in described.values():
        for number in re.findall(r"\d+", d.full + d.short):
            assert int(number) <= 90
    assert isinstance(next(iter(described.values())), Description)


def test_a_name_with_regex_characters_is_matched_literally_and_cannot_break_the_check():
    """The check for names of players who are not in the moment must not read a name as a pattern: an
    unescaped "(" raised re.error in `check`, which the fallback calls without a guard."""
    players = [MATCH.away.players[0].model_copy(update={"name": "Pet(rov"}), *MATCH.away.players[1:]]
    match = MATCH.model_copy(update={"away": MATCH.away.model_copy(update={"players": players})})
    outsider = players[0]
    ctx = Context(match, "en")
    verifier = Verifier(ctx)
    moment = BY_KIND["kickoff"]
    assert outsider.name in ctx.all_names and outsider.name not in ctx.involved(moment)
    described = TemplateDescriber().describe([moment], ctx, {}, 1)[moment.id]
    assert verifier.check(moment, described) == []
    said = described.model_copy(update={"full": described.full + " Pet(rov", "short": described.short})
    assert "Pet(rov is not in this moment" in verifier.check(moment, said)
