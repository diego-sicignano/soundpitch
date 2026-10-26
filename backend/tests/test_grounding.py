"""S19 and S20: the verifier accepts what a moment's own facts support and nothing else (SPEC §5).

The mutations below are generated from the match data and the template lexicon, not from the
verifier's internals: they alter a *valid* description in ways that change a fact, and each one must
be rejected. A second family of tests checks the opposite risk, valid wording that is rejected.
"""

import random
import re
from dataclasses import dataclass

import pytest

from app.contracts import Description, FactRef, Moment, Profile
from app.corpora import NATURAL, VOCAB_AWARE, patterns_for
from app.describer import LEX, Context, TemplateDescriber, facts
from app.match_gen import SEED, generate_match
from app.moments import detect_moments
from app.pipeline import build_presets, build_session
from app.verifier import Verifier

SEEDS = [SEED, 7, 11]
LANGS = ("en", "it")
DETAILS = ("essential", "standard", "full")
# The only function words SPEC section 5 allows in every sentence: articles and "and". Every other
# relation word ("for", "on", "by", "per") belongs to the templates of one kind of event.
COMMON = {
    "en": {"the", "a", "an", "and"},
    "it": {"il", "lo", "la", "i", "gli", "le", "un", "una", "e"},
}
FAMILY = {"goal": ("goal", "goal_assist"), "goal_assist": ("goal", "goal_assist")}


def words(text: str) -> set[str]:
    text = re.sub(r"\{[^}]*\}", " ", text).lower().replace("’", "'")
    found = set(re.findall(r"\d+|[^\W\d_]+(?:['\-][^\W\d_]+)*", text))
    return found


def key_words(lang: str, key: str) -> set[str]:
    found: set[str] = set()
    for k in FAMILY.get(key, (key,)):
        for full, short in LEX[lang]["t"][k]:
            found |= words(full) | words(short)
    return found


def all_words(lang: str) -> set[str]:
    return set().union(*(key_words(lang, k) for k in LEX[lang]["t"]))


def sub(text: str, old: str, new: str) -> str:
    return re.sub(rf"(?<!\w){re.escape(old)}(?!\w)", lambda _m: new, text)


def has(text: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) is not None


def variants(moment: Moment, ctx: Context) -> tuple[set[str], set[str]]:
    """Every template rendering of a moment: the texts that are plainly true for it."""
    f = facts(moment, ctx)
    full, short = set(), set()
    for key in FAMILY.get(f.key, (f.key,)):
        for a, b in LEX[ctx.lang]["t"][key]:
            try:
                full.add(a.format(**f.fields))
                short.add(b.format(**f.fields))
            except KeyError:  # a goal_assist template for a goal without an assist
                pass
    return full, short


@dataclass
class Case:
    seed: int
    ctx: Context
    verifier: Verifier
    moment: Moment
    desc: Description

    @property
    def facts(self):
        return facts(self.moment, self.ctx)


def _cases() -> list[Case]:
    cases = []
    for seed in SEEDS:
        match = generate_match(seed)
        for lang in LANGS:
            ctx = Context(match, lang)
            verifier = Verifier(ctx)
            for detail in DETAILS:
                moments = detect_moments(match.events, detail)
                described = TemplateDescriber().describe(moments, ctx, {}, 1)
                cases += [Case(seed, ctx, verifier, m, described[m.id]) for m in moments]
    return cases


CASES = _cases()


def pairs(case: Case, *texts: tuple[str, str]) -> list[Description]:
    return [case.desc.model_copy(update={"full": f, "short": s}) for f, s in texts]


def replaced(case: Case, old: str, new: str) -> list[Description]:
    d = case.desc
    if old not in d.full + d.short:
        return []
    return pairs(case, (d.full.replace(old, new), d.short.replace(old, new)))


# ---- mutations: each returns descriptions that state something false about the moment -----------


def team_swap(c: Case):
    a, b = c.ctx.short("home"), c.ctx.short("away")
    f = c.facts.fields
    if c.moment.kind in ("halftime", "fulltime", "score_update") and f["hs"] == f["as_"]:
        return []  # "Away 1, Home 1" is still true
    swap = lambda t: re.sub(
        rf"(?<!\w)({a}|{b})(?!\w)", lambda m: b if m.group(1) == a else a, t
    )
    new = (swap(c.desc.full), swap(c.desc.short))
    return pairs(c, new) if new != (c.desc.full, c.desc.short) else []


def actor_swap(c: Case):
    pool, out = c.ctx.all_names, []
    text = c.desc.full + " " + c.desc.short
    for name in sorted(c.ctx.involved(c.moment)):
        if has(text, name):
            for step in (1, 11):
                other = pool[(pool.index(name) + step) % len(pool)]
                out += pairs(c, (sub(c.desc.full, name, other), sub(c.desc.short, name, other)))
    return out


def role_swap(c: Case):
    f = c.facts.fields
    if c.facts.key != "goal_assist":
        return []
    p, a = f["p"], f["a"]
    mark = "\x00"
    swap = lambda t: sub(sub(sub(t, p, mark), a, p), mark, a)
    return pairs(c, (swap(c.desc.full), swap(c.desc.short)))


def digits(c: Case):
    bump = lambda t: re.sub(r"\d+", lambda m: str(int(m.group()) + 1), t)
    new = (bump(c.desc.full), bump(c.desc.short))
    return pairs(c, new) if new != (c.desc.full, c.desc.short) else []


def score_numbers_swapped(c: Case):
    f = c.facts.fields
    if f["hs"] == f["as_"]:
        return []
    good = f"{f['home']} {f['hs']}, {f['away']} {f['as_']}"
    return replaced(c, good, f"{f['home']} {f['as_']}, {f['away']} {f['hs']}")


def lane_swap(c: Case):
    lex, out = LEX[c.ctx.lang], []
    for field in ("lane_from", "lane_down", "side"):
        phrase = c.facts.fields.get(field)
        if phrase:
            for other in lex[field].values():
                if other != phrase:
                    out += replaced(c, phrase, other)
    return out


def zone_swap(c: Case):
    zone = c.facts.fields.get("zone")
    if not zone:
        return []
    options = LEX[c.ctx.lang]["zone_at" if c.facts.key == "turnover" else "zone_to"]
    return [p for other in options if other != zone for p in replaced(c, zone, other)]


def direction_swap(c: Case):
    phrase = c.facts.fields.get("dir")
    if not phrase:
        return []
    return replaced(c, phrase, next(v for v in LEX[c.ctx.lang]["dir"].values() if v != phrase))


FOREIGN = {
    "en": ["penalty", "VAR", "offside", "injured", "controversial", "brilliant", "against", "lead",
           "ahead", "behind", "equaliser", "winner", "third", "three", "hat-trick", "header", "Smith"],
    "it": ["rigore", "VAR", "fuorigioco", "infortunato", "polemica", "bellissimo", "contro",
           "vantaggio", "pareggio", "terzo", "tre", "tripletta", "colpo di testa", "Smith"],
}


def foreign_words(c: Case):
    """Words of other event kinds (from the lexicon) and words no template has ever used."""
    lang, key = c.ctx.lang, c.facts.key
    outside = sorted(all_words(lang) - key_words(lang, key) - COMMON[lang] - {"1", "2"})
    rng = random.Random(c.moment.id * 31 + c.seed)
    picks = rng.sample(outside, 4) + rng.sample(FOREIGN[lang], 3)
    return [p for w in picks for p in pairs(c, (c.desc.full + " " + w, c.desc.short + " " + w))]


def invented_actor(c: Case):
    name = c.facts.fields.get("p")
    if not name:
        return []
    return pairs(c, (sub(c.desc.full, name, "Smith"), sub(c.desc.short, name, "Smith")))


def bad_references(c: Case):
    d = c.desc
    stray = FactRef(event_id=c.moment.event_ids[0], field="kind", value="goal")
    out = [
        d.model_copy(update={"refs": []}),
        d.model_copy(update={"moment_id": d.moment_id + 1000}),
        d.model_copy(update={"lang": "it" if d.lang == "en" else "en"}),
        d.model_copy(update={"refs": [*d.refs, stray]}),
    ]
    if len(d.refs) > 1:
        out.append(d.model_copy(update={"refs": d.refs[1:]}))
    first = d.refs[0]
    value = first.value + 1 if isinstance(first.value, int) else f"{first.value}x"
    wrong = FactRef(event_id=first.event_id, field=first.field, value=value)
    out.append(d.model_copy(update={"refs": [wrong, *d.refs[1:]]}))
    return out


def missing_required_fact(c: Case):
    f = c.facts.fields
    key, out = c.facts.key, []
    score = f"{f['home']} {f['hs']}, {f['away']} {f['as_']}"
    if key in ("goal", "goal_assist"):
        out += pairs(c, (sub(c.desc.full, f["p"], ""), c.desc.short))
        out += pairs(c, (c.desc.full, sub(c.desc.short, f["p"], "")))
        out += pairs(c, (sub(c.desc.full, f["team"], ""), c.desc.short))
    if key in ("goal", "goal_assist", "halftime", "fulltime", "score_update") and score in c.desc.full:
        out += pairs(c, (c.desc.full.replace(score, ""), c.desc.short))
    if key == "kickoff":
        out += pairs(c, (sub(c.desc.full, f["team"], ""), c.desc.short))
    return out


def assist_forged(c: Case):
    f = c.facts.fields
    if c.facts.key != "goal_assist":
        return []
    return replaced(c, f["assist"], f["assist"].replace(f["a"], f["p"]))


def chain_reordered(c: Case):
    chain = c.facts.fields.get("chain")
    if not chain or ", " not in chain:
        return []
    other = ", ".join(reversed(chain.split(", ")))
    return replaced(c, chain, other) if other != chain else []


def loose_entity_in_match_level_moment(c: Case):
    """Half-time, full-time and score reminders are about the score only."""
    if c.moment.kind not in ("halftime", "fulltime", "score_update"):
        return []
    f = c.facts.fields
    out = [p for team in (f["home"], f["away"]) for p in pairs(c, (c.desc.full + " " + team, c.desc.short))]
    if "m" in f:
        out += pairs(c, (c.desc.full + f" {f['home']} {f['m']}", c.desc.short))
        out += pairs(c, (c.desc.full + f" {f['m']}", c.desc.short))
    return out


SYMBOLS = [
    "?", "(", ")", "=", "\u2192", "\u00d7", "/", "\u274c", "\U0001f7e5",
    "\U0001f51f", "\U0001f4af", "\u202e", "\x00", "\u200b", "\u00a7", "<", "+",
]


def stray_symbols(c: Case):
    """Emoji, symbols and control characters reach captions and speech although they are no word."""
    rng = random.Random(c.moment.id + c.seed)
    return [
        p for s in rng.sample(SYMBOLS, 5)
        for p in pairs(c, (c.desc.full + " " + s, c.desc.short + " " + s))
    ]


def content_free(c: Case):
    """Text that says nothing must not replace a real description."""
    filler = "the" if c.ctx.lang == "en" else "il"
    return [p for t in ("!", ".", ",", "\U0001f51f", "\u200b", filler) for p in pairs(c, (t, t))]


def lane_of_an_event_the_moment_does_not_state(c: Case):
    """The lane of the last event is not a fact of a save, a foul, a goal or a score reminder."""
    if any(r.field == "lane" for r in c.facts.refs):
        return []
    lane = c.ctx.by_id[c.moment.event_ids[-1]].lane
    if lane is None:
        return []
    phrases = [LEX[c.ctx.lang][g][lane] for g in ("lane_from", "lane_down", "side")]
    return [p for ph in phrases for p in pairs(c, (c.desc.full + " " + ph, c.desc.short))]


def oversized(c: Case):
    """Huge inputs must be rejected quickly, never crash the check or slip past the length limit."""
    if c.moment.id % 25:
        return []
    big = ["the " * 3000, "saves," * 5000, "1" * 5000, "x" * 100_000]
    return [p for b in big for p in pairs(c, (b, c.desc.short), (c.desc.full, b))]


MUTATIONS = {
    "symbols, emoji and control characters": stray_symbols,
    "content-free text": content_free,
    "lane of an event the moment does not state": lane_of_an_event_the_moment_does_not_state,
    "oversized text": oversized,
    "team or number loose in a match-level moment": loose_entity_in_match_level_moment,
    "wrong team": team_swap,
    "wrong or foreign player": actor_swap,
    "scorer and assister exchanged": role_swap,
    "changed digit": digits,
    "score numbers swapped": score_numbers_swapped,
    "another lane": lane_swap,
    "another zone": zone_swap,
    "another direction": direction_swap,
    "word of another kind or never used": foreign_words,
    "invented player": invented_actor,
    "refs, moment id or language": bad_references,
    "required fact missing": missing_required_fact,
    "assist clause forged": assist_forged,
    "build-up chain reordered": chain_reordered,
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_s19_every_mutation_is_rejected(name):
    applied, accepted = 0, []
    for case in CASES:
        for bad in MUTATIONS[name](case):
            if bad == case.desc:  # the mutation had nothing to change in this text
                continue
            applied += 1
            if not case.verifier.check(case.moment, bad):
                accepted.append((case.ctx.lang, case.moment.kind, bad.full, bad.short))
    assert applied >= 30, f"the generator barely ran ({applied})"
    assert not accepted, f"{len(accepted)} of {applied} accepted, e.g. {accepted[:3]}"


@pytest.mark.parametrize("lang", LANGS)
def test_s19_text_of_another_moment_is_rejected_unless_it_is_true_for_this_one(lang):
    for seed in (SEED, 7):
        match = generate_match(seed)
        ctx = Context(match, lang)
        verifier = Verifier(ctx)
        moments = detect_moments(match.events, "full")
        described = TemplateDescriber().describe(moments, ctx, {}, 1)
        rng, checked = random.Random(seed), 0
        for target in moments:
            full_ok, short_ok = variants(target, ctx)
            for other in rng.sample(moments, 40):
                borrowed = described[other.id]
                lie = described[target.id].model_copy(
                    update={"full": borrowed.full, "short": borrowed.short}
                )
                checked += 1
                if not verifier.check(target, lie):
                    assert borrowed.full in full_ok and borrowed.short in short_ok, (
                        target, other, borrowed.full,
                    )
        assert checked > 10_000


def _probe(kind):
    match = generate_match(SEED)
    ctx = Context(match, "en")
    moment = next(m for m in detect_moments(match.events, "full") if m.kind == kind)
    return Verifier(ctx), moment, facts(moment, ctx)


def test_the_probes_of_the_design_review_are_rejected():
    verifier, goal, f = _probe("goal")
    fl = f.fields
    p, team, home, away = fl["p"], fl["team"], fl["home"], fl["away"]
    other = away if team == home else home
    score = f"{home} {fl['hs']}, {away} {fl['as_']}"
    lies = [
        f"Goal! {p} scores for {other}. {score}.",
        f"Goal! Smith scores for {team}. {score}.",
        f"Goal! {p} scores for {team}. {home} {fl['as_']}, {away} {fl['hs']}.",
        f"Goal! {p} scores for {team}. {other} lead.",
        f"Goal! {p} scores for {team}, his third of the season. {score}.",
        f"Goal! {p} scores for {team}, a controversial penalty after VAR. {score}.",
    ]
    for text in lies:
        d = Description(moment_id=goal.id, lang="en", full=text, short="Goal!", refs=f.refs)
        assert verifier.check(goal, d), text
    ok = Description(
        moment_id=goal.id, lang="en", full=f"Goal! {p} scores for {team}. {score}.",
        short=f"Goal! {p} scores.", refs=f.refs,
    )
    assert verifier.check(goal, ok) == []
    verifier, foul, ff = _probe("foul")
    d = Description(
        moment_id=foul.id, lang="en", full=f"Goal! {ff.fields['p']} scores.", short="Goal!", refs=ff.refs
    )
    assert verifier.check(foul, d)


# ---- S20: false rejection ------------------------------------------------------------------------


def test_s20_every_template_variant_is_accepted():
    checked = 0
    for case in CASES:
        f = case.facts
        for key in FAMILY.get(f.key, (f.key,)):
            for full, short in LEX[case.ctx.lang]["t"][key]:
                try:
                    d = case.desc.model_copy(
                        update={"full": full.format(**f.fields), "short": short.format(**f.fields)}
                    )
                except KeyError:
                    continue
                checked += 1
                assert case.verifier.check(case.moment, d) == [], (case.moment, d)
    assert checked > 5000


PARAPHRASES = {
    "en": {
        "goal": "It's in! {p} scores for {team}. {score}.",
        "goal_assist": "Goal! {p} finds the net for {team}, {assist}. {score}.",
        "shot_on_target": "{p} shoots, on target.",
        "shot_off_target": "{p} shoots {lane_from} but it goes wide.",
        "shot_blocked": "{p} shoots, blocked.",
        "save": "The keeper {p} makes the save.",
        "corner": "A corner to {team}, taken by {p}.",
        "free_kick": "Free kick, {team}, {p} to take it.",
        "foul": "A foul by {p} of {team}.",
        "throw_in": "Throw-in, {team} {side}.",
        "turnover": "{team} regain possession, through {p}.",
        "buildup": "{team} move forward {lane_down}: {chain}, {zone}.",
        "kickoff": "Kick-off. {team} get us under way, attacking {dir}.",
        "halftime": "Half-time. {score}.",
        "fulltime": "Full-time. {score}.",
        "score_update": "Minute {m}. {score}.",
    },
    "it": {
        "goal": "Rete! {p} segna per {team}. {score}.",
        "goal_assist": "Gol! {p} finalizza per {team}, {assist}. {score}.",
        "shot_on_target": "{p} tira {lane_from} e inquadra la porta.",
        "shot_off_target": "{p} calcia {lane_from}, fuori.",
        "shot_blocked": "{p} tira, respinto.",
        "save": "Il portiere {p} blocca.",
        "corner": "Angolo per {team}, batte {p} {lane_from}.",
        "free_kick": "Punizione, {team}, batte {p}.",
        "foul": "Un fallo di {p}, {team}.",
        "throw_in": "Rimessa, {team} {side}.",
        "turnover": "{team} riconquista il possesso, con {p}.",
        "buildup": "{team} avanza {lane_down}: {chain}, {zone}.",
        "kickoff": "Calcio d'inizio. {team} dà il via, attacca {dir}.",
        "halftime": "Fine primo tempo. {score}.",
        "fulltime": "Fine partita. {score}.",
        "score_update": "Minuto {m}. {score}.",
    },
}


def test_s20_paraphrases_built_from_the_vocabulary_are_accepted():
    checked = 0
    for case in CASES:
        f = case.facts
        pattern = PARAPHRASES[case.ctx.lang].get(f.key)
        if pattern is None:
            continue
        try:
            full = pattern.format(**f.fields)
        except KeyError:
            continue
        d = case.desc.model_copy(update={"full": full})
        checked += 1
        assert case.verifier.check(case.moment, d) == [], (case.moment, full)
    assert checked > 3000


# ---- the lexicon keeps outcome words apart ------------------------------------------------------

GOALS = {"goal", "goal_assist"}
OUTCOME_OWNERS = {
    "en": {
        "goal": GOALS, "scores": GOALS, "net": GOALS,
        "wide": {"shot_off_target"}, "blocked": {"shot_blocked"}, "target": {"shot_on_target"},
        "save": {"save"}, "gathers": {"save"}, "corner": {"corner"}, "foul": {"foul"},
        "throw-in": {"throw_in"}, "half-time": {"halftime"}, "full-time": {"fulltime"},
        "kick-off": {"kickoff"}, "minute": {"score_update"},
    },
    "it": {
        "gol": GOALS, "segna": GOALS, "rete": GOALS,
        "fuori": {"shot_off_target"}, "respinto": {"shot_blocked"}, "specchio": {"shot_on_target"},
        "parata": {"save"}, "para": {"save"}, "angolo": {"corner"}, "fallo": {"foul"},
        "rimessa": {"throw_in"}, "punizione": {"free_kick"}, "minuto": {"score_update"},
    },
}


@pytest.mark.parametrize("lang", LANGS)
def test_outcome_words_belong_to_one_kind_of_event(lang):
    for word, owners in OUTCOME_OWNERS[lang].items():
        found = {k for k in LEX[lang]["t"] if word in key_words(lang, k)}
        found = {"goal", "goal_assist"} if found & GOALS else found
        assert found == owners, (word, found)


# ---- a describer that lies never gets a verified cue with a false text --------------------------


class Liar:
    """Returns correct-looking descriptions of the wrong thing."""

    def __init__(self, mode: str):
        self.mode = mode

    def describe(self, moments, ctx, feedback, attempt):
        base = TemplateDescriber().describe(moments, ctx, feedback, attempt)
        out = {}
        home, away = ctx.short("home"), ctx.short("away")
        for i, m in enumerate(moments):
            d = base[m.id]
            if self.mode == "teams":
                swap = lambda t: re.sub(
                    rf"(?<!\w)({home}|{away})(?!\w)", lambda x: away if x.group(1) == home else home, t
                )
                d = d.model_copy(update={"full": swap(d.full), "short": swap(d.short), "refs": []})
            else:
                n = base[moments[(i + 1) % len(moments)].id]
                d = d.model_copy(update={"full": n.full, "short": n.short})
            out[m.id] = d
        return out


@pytest.mark.parametrize("mode", ["teams", "shifted"])
@pytest.mark.parametrize("lang", LANGS)
def test_s19_a_lying_describer_ends_in_the_template_fallback(mode, lang):
    match = generate_match(SEED)
    for preset in build_presets(match):
        profile = Profile(detail="full", lang=lang)
        session = build_session(match, preset, profile, Liar(mode))
        clean = build_session(match, preset, profile, TemplateDescriber())
        ctx = Context(match, lang)
        window = [e for e in match.events if preset.from_s <= e.t <= preset.to_s]
        by_id = {m.id: m for m in detect_moments(window, "full")}
        assert session.report.fallback > 0
        assert session.report.verified + session.report.fallback == session.report.moments
        for cue in session.cues:
            if cue.status == "verified":
                full_ok, short_ok = variants(by_id[cue.moment_id], ctx)
                assert (cue.text.removesuffix(" " + cue.context) if cue.context else cue.text) in (full_ok if cue.variant == "full" else short_ok), cue
        assert [c.moment_id for c in session.cues if c.priority == 3] == [
            c.moment_id for c in clean.cues if c.priority == 3
        ]


# ---- the playback boundary: a check that fails closed, a fallback that must verify ---------------


def test_s19_a_verifier_that_crashes_rejects_instead_of_letting_the_text_through(monkeypatch):
    original = Verifier._grounding

    def crashing(self, part, text, *args, **kwargs):
        if "boom" in text.lower():
            raise ValueError("unexpected input")
        return original(self, part, text, *args, **kwargs)

    monkeypatch.setattr(Verifier, "_grounding", crashing)
    match = generate_match(SEED)
    preset = next(p for p in build_presets(match) if p.id == "goal_1")

    class Boom:
        def describe(self, moments, ctx, feedback, attempt):
            base = TemplateDescriber().describe(moments, ctx, feedback, attempt)
            return {i: d.model_copy(update={"full": d.full + " boom"}) for i, d in base.items()}

    session = build_session(match, preset, Profile(detail="full"), Boom())
    assert session.report.verified == 0 and session.report.fallback == session.report.moments
    assert all(c.status == "fallback" for c in session.cues)


def test_a_template_fallback_that_does_not_verify_stops_the_session(monkeypatch):
    original = TemplateDescriber.describe

    def broken(self, moments, ctx, feedback, attempt):
        base = original(self, moments, ctx, feedback, attempt)
        return {i: d.model_copy(update={"full": d.full + " penalty"}) for i, d in base.items()}

    monkeypatch.setattr(TemplateDescriber, "describe", broken)
    match = generate_match(SEED)
    preset = next(p for p in build_presets(match) if p.id == "goal_1")
    with pytest.raises(RuntimeError, match="fallback"):
        build_session(match, preset, Profile(), TemplateDescriber())


# ---- the function words stay neutral ---------------------------------------------------------------

BANNED_FUNCTION_WORDS = {
    "en": {"not", "no", "never", "against", "versus", "vs", "after", "before", "again", "first", "last",
           "own", "more", "most", "all", "only", "just", "still", "already", "than", "but", "if",
           "because", "while", "although", "from", "over", "past", "beyond", "now", "then", "twice"},
    "it": {"non", "mai", "contro", "dopo", "prima", "ancora", "già", "solo", "più", "ma", "se",
           "perché", "mentre", "anche", "oltre", "tra", "fra", "senza", "ora", "poi"},
}


@pytest.mark.parametrize("lang", LANGS)
def test_function_words_cannot_name_an_entity_a_number_a_place_or_an_outcome(lang):
    from app.verifier import COMMON as common

    spatial = {
        "en": {"left", "right", "centre", "center", "middle", "midfield", "half", "third", "side", "wide"},
        "it": {"sinistra", "destra", "centro", "centrale", "centrali", "centrocampo", "meta", "campo", "terzo"},
    }
    words_ = set(common[lang])
    assert not words_ & BANNED_FUNCTION_WORDS[lang]
    roster = generate_match(SEED)
    names = {p.name.lower() for t in (roster.home, roster.away) for p in t.players}
    names |= {roster.home.short.lower(), roster.away.short.lower()}
    assert not words_ & names
    assert not words_ & set(OUTCOME_OWNERS[lang])
    assert not words_ & spatial[lang]
    assert all(not any(ch.isdigit() for ch in w) for w in words_)


# ---- conforming output is accepted: variants a model or a speech engine may legitimately produce -


def _variants_of_form(text: str) -> list[str]:
    import unicodedata

    return [
        text.upper(),
        unicodedata.normalize("NFD", text),
        text.replace("'", "’"),
        text.replace("-", " "),
    ]


def test_s20_case_unicode_form_apostrophe_and_hyphen_variants_are_accepted():
    checked = 0
    for case in CASES:
        d = case.desc
        for full, short in zip(_variants_of_form(d.full), _variants_of_form(d.short), strict=True):
            checked += 1
            bad = d.model_copy(update={"full": full, "short": short})
            assert case.verifier.check(case.moment, bad) == [], (case.moment.kind, full)
    assert checked > 10_000


WORD_RE = r"[^\W\d_]+(?:['\-][^\W\d_]+)*"


def conforms(case: Case, text: str) -> bool:
    """The contract of SPEC section 5, written out again here and independent of the verifier."""
    lang, fl = case.ctx.lang, case.facts.fields
    rest = text.lower().replace(APOSTROPHE, "'")
    for name in ("chain", "assist", "zone", "dir", "lane_from", "lane_down", "side", "minute", "score"):
        if fl.get(name):
            rest = re.sub(rf"(?<!\w){re.escape(str(fl[name]).lower())}(?!\w)", " ", rest)
    allowed = key_words(lang, case.facts.key) | COMMON[lang]
    allowed |= {str(fl[n]).lower() for n in ("p", "team") if n in fl}
    if not set(re.findall(WORD_RE + r"|\d+", rest)) <= allowed:
        return False
    others = set().union(*(key_words(lang, k) for k in LEX[lang]["t"] if k not in FAMILY.get(case.facts.key, (case.facts.key,))))
    own = key_words(lang, case.facts.key) - others - COMMON[lang]
    if not (set(re.findall(WORD_RE, rest)) & own or case.facts.key == "score_update"):
        return False
    return names_stand_in_place(case, text)


def _conforming(case: Case, rng: random.Random) -> str | None:
    """A template with random word substitutions; None if this draw leaves the contract."""
    f, lang = case.facts, case.ctx.lang
    templates = [a for k in FAMILY.get(f.key, (f.key,)) for a, _ in LEX[lang]["t"][k]]
    template = rng.choice(templates)
    vocab = sorted(key_words(lang, f.key) | COMMON[lang])
    pieces = re.split(r"(\{[^}]*\})", template)
    swapped = "".join(
        p if p.startswith("{") else re.sub(WORD_RE, lambda m: rng.choice(vocab) if rng.random() < 0.35 else m.group(), p)
        for p in pieces
    )
    try:
        text = swapped.format(**f.fields)
    except KeyError:
        return None
    if rng.random() < 0.3:
        text = text.replace(" ", " the ", 1)
    short_words = len(case.desc.short.split())
    return text if len(text.split()) >= short_words and conforms(case, text) else None


def test_s20_random_sentences_made_of_allowed_pieces_are_accepted():
    checked, rejected = 0, []
    for case in CASES:
        rng = random.Random(case.moment.id * 7 + case.seed)
        drawn = 0
        for _ in range(40):
            text = _conforming(case, rng)
            if text is None:
                continue
            drawn += 1
            checked += 1
            issues = case.verifier.check(case.moment, case.desc.model_copy(update={"full": text}))
            if issues:
                rejected.append((case.ctx.lang, case.facts.key, text, issues[:2]))
            if drawn == 2:
                break
    assert checked > 4000
    assert not rejected, f"{len(rejected)} of {checked} rejected, e.g. {rejected[:3]}"


class CorpusDescriber:
    """Says a hand-written sentence for every moment that has one; the template for the rest."""

    def __init__(self, corpus):
        self.corpus = corpus

    def describe(self, moments, ctx, feedback, attempt):
        base = TemplateDescriber().describe(moments, ctx, feedback, attempt)
        for m in moments:
            f = facts(m, ctx)
            usable = []
            for pattern in patterns_for(self.corpus, ctx.lang, f.key):
                try:
                    usable.append(pattern.format(**f.fields))
                except KeyError:
                    continue
            if usable:
                base[m.id] = base[m.id].model_copy(update={"full": usable[m.id % len(usable)]})
        return base


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("corpus", [NATURAL, VOCAB_AWARE], ids=["natural", "aware"])
def test_a_sentence_is_either_verified_as_written_or_replaced_by_the_template(corpus, lang):
    match = generate_match(SEED)
    ctx = Context(match, lang)
    verifier = Verifier(ctx)
    for preset in build_presets(match):
        profile = Profile(detail="full", lang=lang)
        describer = CorpusDescriber(corpus)
        session = build_session(match, preset, profile, describer)
        window = [e for e in match.events if preset.from_s <= e.t <= preset.to_s]
        moments = {m.id: m for m in detect_moments(window, "full")}
        said = describer.describe(list(moments.values()), ctx, {}, 1)
        assert session.report.verified + session.report.fallback == session.report.moments
        for cue in session.cues:
            moment = moments[cue.moment_id]
            if cue.status == "verified":
                assert verifier.check(moment, said[moment.id]) == []
                assert (cue.text.removesuffix(" " + cue.context) if cue.context else cue.text) in (said[moment.id].full, said[moment.id].short)
            else:
                assert verifier.check(moment, said[moment.id]) != []
                full_ok, short_ok = variants(moment, ctx)
                assert (cue.text.removesuffix(" " + cue.context) if cue.context else cue.text) in (full_ok if cue.variant == "full" else short_ok)


# ---- adversarial inputs: relation words and moved phrases ----------------------------------------

RELATION_WORDS = {"en": {"for", "by", "of", "to", "in", "with"}, "it": {"per", "di", "del", "da", "con", "al"}}
FLIPPING = {"en": ["on", "at", "against"], "it": ["su", "al", "contro"]}


def relation_word_swapped(c: Case):
    """The word before a player or team is changed to one that turns the relation round
    ("scores on Northgate", "Foul on Costa", "segna al Northgate")."""
    names = [n for n in (c.facts.fields.get("p"), c.facts.fields.get("team")) if n]
    out = []
    for name in names:
        for new in FLIPPING[c.ctx.lang]:
            for part in ("full", "short"):
                text = getattr(c.desc, part)
                swapped = re.sub(
                    rf"\b({'|'.join(RELATION_WORDS[c.ctx.lang])})(\s+(?:{'|'.join(COMMON[c.ctx.lang])}\s+)?{name}\b)",
                    lambda m, new=new: new + m.group(2),
                    text,
                )
                if swapped != text:
                    out += [c.desc.model_copy(update={part: swapped})]
    return out


def only_words_other_kinds_share(c: Case):
    """A word that other kinds of event use too ("time", "off", "Fine") does not say what happened."""
    lang, key = c.ctx.lang, c.facts.key
    others = set().union(*(key_words(lang, k) for k in LEX[lang]["t"] if k not in FAMILY.get(key, (key,))))
    shared = sorted((key_words(lang, key) & others) - COMMON[lang])
    fl = c.facts.fields
    required = [str(fl[k]) for k in ("p", "team", "score") if k in fl]
    out = []
    for word in shared[:6]:
        out += pairs(c, (word.capitalize() + ". " + " ".join(required), c.desc.short))
    return out


def a_lone_part_of_a_compound_word(c: Case):
    parts = {p for w in key_words(c.ctx.lang, c.facts.key) if "-" in w for p in w.split("-")}
    parts -= key_words(c.ctx.lang, c.facts.key)  # only parts that are not words of their own
    fl = c.facts.fields
    required = [str(fl[k]) for k in ("team", "score") if k in fl]
    return [p for part in sorted(parts) for p in pairs(c, (part.capitalize() + ". " + " ".join(required), c.desc.short))]


MUTATIONS["relation word turned round (on, at, against)"] = relation_word_swapped
MUTATIONS["only words other kinds of event share"] = only_words_other_kinds_share
MUTATIONS["a lone part of a compound word"] = a_lone_part_of_a_compound_word


def test_a_description_that_is_not_a_plain_description_is_not_trusted():
    """An object that answers differently each time it is read must not reach a cue as verified."""
    match = generate_match(SEED)
    preset = next(p for p in build_presets(match) if p.id == "goal_1")

    def make_duck(d):
        state = {"n": 0}

        class Duck:
            moment_id, lang, refs, short = d.moment_id, d.lang, d.refs, d.short

            @property
            def full(self):
                state["n"] += 1
                return d.full if state["n"] <= 6 else "Goal! Smith scores for Nowhere FC. Rovers 9, Town 0"

            def model_dump(self):
                return {"moment_id": self.moment_id, "lang": self.lang, "refs": self.refs,
                        "short": self.short, "full": self.full}

        return Duck()

    class Chameleon:
        def describe(self, moments, ctx, feedback, attempt):
            base = TemplateDescriber().describe(moments, ctx, feedback, attempt)
            return {i: make_duck(d) for i, d in base.items()}

    session = build_session(match, preset, Profile(detail="full"), Chameleon())
    assert session.report.verified == 0 and session.report.fallback == session.report.moments
    assert not any("Smith" in c.text for c in session.cues)


# ---- S19: a name stays where the templates put it (SPEC §5 rule 6) --------------------------------

ARTICLES = {
    "en": {"the", "a", "an"},
    "it": {"il", "lo", "la", "i", "gli", "le", "un", "una"},
}
APOSTROPHE = chr(0x2019)
WORD = r"qq\w+|\d+|[^\W\d_]+(?:['\-][^\W\d_]+)*"


PHRASE_MARKER = {
    "chain": "qqchain", "assist": "qqassist", "zone": "qqzone", "dir": "qqdir", "lane_from": "qqlane",
    "lane_down": "qqlane", "side": "qqlane", "minute": "qqminute", "score": "qqscore",
}
PHRASE_MARKERS = set(PHRASE_MARKER.values())
TRACKED = PHRASE_MARKERS | {"qqp", "qqteam"}


def _neighbour_words(text: str, lang: str) -> list[str]:
    """Words without articles, between edges (the start and the end of the text)."""
    found = re.findall(WORD, text.lower().replace(APOSTROPHE, "'"))
    return ["EDGE", *[w for w in found if w not in ARTICLES[lang]], "EDGE"]


def _next_to(neighbour: str, own: str) -> str:
    """Another canonical phrase beside a token counts as an edge: phrases are optional."""
    return "EDGE" if neighbour in PHRASE_MARKERS and neighbour != own else neighbour


def attested(lang: str, key: str):
    """Independent reading of SPEC rule 6: for a name or a phrase, the words some template of the key
    puts before and after it."""
    before = {m: set() for m in TRACKED}
    after = {m: set() for m in TRACKED}
    for k in FAMILY.get(key, (key,)):
        for pair in LEX[lang]["t"][k]:
            for template in pair:
                text = template.replace("{home} {hs}, {away} {as_}", " qqscore ")
                text = text.replace(LEX[lang]["minute"] + " {m}", " qqminute ")
                text = text.replace("{p}", " qqp ").replace("{team}", " qqteam ")
                for field, marker in PHRASE_MARKER.items():
                    text = text.replace("{" + field + "}", f" {marker} ")
                tokens = _neighbour_words(re.sub(r"\{[^}]*\}", " qqother ", text), lang)
                for i, token in enumerate(tokens):
                    if token in TRACKED:
                        before[token].add(_next_to(tokens[i - 1], token))
                        after[token].add(_next_to(tokens[i + 1], token))
    return before, after


def names_stand_in_place(case: Case, text: str) -> bool:
    fields = case.facts.fields
    marked = text.lower().replace(APOSTROPHE, "'")
    for field, marker in PHRASE_MARKER.items():
        if fields.get(field):
            marked = re.sub(rf"(?<!\w){re.escape(str(fields[field]).lower())}(?!\w)", f" {marker} ", marked)
    for name, marker in (("p", "qqp"), ("team", "qqteam")):
        if fields.get(name):
            marked = re.sub(rf"(?<!\w){re.escape(str(fields[name]).lower())}(?!\w)", f" {marker} ", marked)
    tokens = _neighbour_words(marked, case.ctx.lang)
    before, after = attested(case.ctx.lang, case.facts.key)
    return all(
        _next_to(tokens[i - 1], t) in before[t] and _next_to(tokens[i + 1], t) in after[t]
        for i, t in enumerate(tokens)
        if t in TRACKED
    )


def phrase_in_a_name_place(c: Case):
    """The score, the assist clause or another phrase standing where a team or player belongs."""
    fl = c.facts.fields
    phrases = [str(fl[k]) for k in ("score", "assist", "chain", "zone", "dir") if k in fl]
    out = []
    for name in (fl.get("p"), fl.get("team")):
        if name and has(c.desc.full, name):
            out += [p for ph in phrases for p in pairs(c, (sub(c.desc.full, name, ph), c.desc.short))]
    return out


MUTATIONS["a phrase where a name belongs"] = phrase_in_a_name_place


def players_and_teams_exchanged(c: Case):
    """The player's name where the team's belongs and the other way round."""
    fl = c.facts.fields
    p, team = fl.get("p"), fl.get("team")
    if not p or not team:
        return []
    mark = "\x00"
    swap = lambda t: sub(sub(sub(t, p, mark), team, p), mark, team)
    new = (swap(c.desc.full), swap(c.desc.short))
    return pairs(c, new) if new != (c.desc.full, c.desc.short) else []


def one_name_in_the_place_of_the_other(c: Case):
    fl = c.facts.fields
    p, team = fl.get("p"), fl.get("team")
    if not p or not team:
        return []
    out = []
    if has(c.desc.full + c.desc.short, p) and c.facts.key not in ("goal", "goal_assist"):
        out += pairs(c, (sub(c.desc.full, p, team), sub(c.desc.short, p, team)))
    if has(c.desc.full + c.desc.short, team) and c.facts.key not in ("goal", "goal_assist"):
        out += pairs(c, (sub(c.desc.full, team, p), sub(c.desc.short, team, p)))
    return out


MUTATIONS["player and team exchanged"] = players_and_teams_exchanged
MUTATIONS["one name where the other belongs"] = one_name_in_the_place_of_the_other


ROLE_CONFUSIONS = [
    ("foul", "en", "Foul of {p} by {team}."),
    ("foul", "en", "Foul on {p}."),
    ("shot_blocked", "en", "{p} blocked."),
    ("corner", "en", "Corner to {p}, taken by {team}."),
    ("goal_assist", "en", "Goal! {team} finds {p}. {score}."),
    ("goal_assist", "en", "Goal! {assist} scores for {team}. {p}. {score}."),
    ("goal_assist", "en", "Goal! {p}. {assist} scores for {team}. {score}."),
    ("turnover", "en", "{team} win the ball back {zone}, through {p}, {p}."),
    ("foul", "it", "Fallo di {team}, {p}."),
    ("corner", "it", "Calcio d'angolo per {p}, batte {team}."),
    ("shot_on_target", "en", "{team} shoots {lane_from}, {p}."),
    # round 3: the score phrase starts with the home team, so it must not stand where a team belongs
    ("throw_in", "en", "Throw-in to {score}."),
    ("corner", "en", "Corner to {score}, taken by {p}."),
    ("foul", "en", "Foul by {p} of {score}."),
    ("turnover", "en", "{p} of {score} wins the ball {zone}."),
    ("turnover", "en", "{score} regain possession {zone}, through {p}."),
    ("buildup", "en", "{score} build {lane_down}: {chain}, {zone}."),
    ("throw_in", "it", "Rimessa laterale per {score}."),
    ("corner", "it", "Calcio d'angolo per {score}, batte {p}."),
    ("goal_assist", "en", "Goal! {p} scores. {assist} scores for {team}. {score}."),
    ("goal_assist", "it", "Gol! {p} segna. {assist} segna per {team}. {score}."),
    ("shot_on_target", "en", "{p} has a go {lane_from} and it's on target. {score}."),
]


@pytest.mark.parametrize("key,lang,pattern", ROLE_CONFUSIONS)
def test_s19_role_confusions_reported_by_the_reviewer_are_rejected(key, lang, pattern):
    match = generate_match(SEED)
    ctx = Context(match, lang)
    verifier = Verifier(ctx)
    tried = 0
    for moment in detect_moments(match.events, "full"):
        f = facts(moment, ctx)
        if f.key != key:
            continue
        try:
            text = pattern.format(**f.fields)
        except KeyError:
            continue
        d = TemplateDescriber().describe([moment], ctx, {}, 1)[moment.id].model_copy(update={"full": text})
        tried += 1
        assert verifier.check(moment, d), text
    assert tried


def test_the_rule_does_not_reject_the_templates_themselves():
    assert all(names_stand_in_place(c, c.desc.full) and names_stand_in_place(c, c.desc.short) for c in CASES)
