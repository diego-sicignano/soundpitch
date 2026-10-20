"""Verify: every claim in a description must be supported by the moment's events (SPEC §5).

Two layers. The first compares the claimed refs, names and numbers with the events. The second,
*grounding*, takes the moment's own facts from `describer.facts` and allows a description to state
only those: relation-bearing facts as canonical phrases copied verbatim, everything else from a closed
vocabulary. It proves where the facts and words come from, not that the prose means what it should.
"""

import re
import unicodedata
from functools import cache

from app.contracts import Description, Lang, Moment
from app.describer import LEX, Context, Facts, facts

MAX_FULL_WORDS = 45
MAX_SHORT_WORDS = 15
MAX_CHARS = 400  # the most /api/tts will speak in one request (TtsRequest.text)

# Function words any sentence may use besides the words of its template key: articles and "and". Every
# word that relates two facts ("for", "by", "on", "per", "di") belongs to the templates of one kind of
# event, because "scores on Northgate" and "scores for Northgate" are different facts. A word may join
# this list only if it cannot name an entity, a number, a place, an outcome or a relation (SPEC §5, D9).
COMMON: dict[Lang, frozenset[str]] = {
    "en": frozenset({"the", "a", "an", "and"}),
    "it": frozenset({"il", "lo", "la", "i", "gli", "le", "un", "una", "e"}),
}
# Articles are transparent for the position rule: "for the Northgate" is "for Northgate".
ARTICLES: dict[Lang, frozenset[str]] = {
    "en": frozenset({"the", "a", "an"}),
    "it": frozenset({"il", "lo", "la", "i", "gli", "le", "un", "una"}),
}
FAMILY = {"goal": ("goal", "goal_assist"), "goal_assist": ("goal", "goal_assist")}
# Facts whose relation to other facts matters: written exactly as the code builds them, or not at all.
PHRASES = ("chain", "assist", "zone", "dir", "lane_from", "lane_down", "side", "minute", "score")

LANE_FIELDS = ("lane_from", "lane_down", "side")


def _marker(field: str) -> str:
    """The marker a canonical phrase leaves in a sentence when its position is checked."""
    return "qqlane" if field in LANE_FIELDS else f"qq{field}"


PHRASE_MARKERS = frozenset(_marker(f) for f in PHRASES)
TRACKED = PHRASE_MARKERS | {"qqp", "qqteam"}  # what the position rule watches: names and phrases

REQUIRED_FULL = {
    "goal": ("p", "team", "score"),
    "goal_assist": ("p", "team", "score"),
    "kickoff": ("team",),
    "halftime": ("score",),
    "fulltime": ("score",),
    "score_update": ("score",),
}
REQUIRED_SHORT = {"goal": ("p",), "goal_assist": ("p",)}
# Moments whose whole point is the score; for any other kind the score alone says nothing.
SCORE_IS_CONTENT = frozenset({"score_update"})
TOKEN = re.compile(r"\d+|[^\W\d_]+(?:['\-][^\W\d_]+)*")
HARMLESS = re.compile(r"[\s.,!:;'\-]")  # what may stand between words: no symbol, emoji or control


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower().replace("’", "'")


def _tokens(text: str) -> list[str]:
    return TOKEN.findall(_norm(text))


def _template_tokens(lang: Lang, keys: tuple[str, ...]) -> set[str]:
    found: set[str] = set()
    for k in keys:
        for templates in LEX[lang]["t"][k]:
            for template in templates:
                found.update(_tokens(re.sub(r"\{[^}]*\}", " ", template)))
    return found


@cache
def vocabulary(lang: Lang, key: str) -> frozenset[str]:
    """The words a sentence of this template key may use besides facts: those of its templates."""
    return frozenset(_template_tokens(lang, FAMILY.get(key, (key,))) | COMMON[lang])


@cache
def outcome_words(lang: Lang, key: str) -> frozenset[str]:
    """Words only this kind of event uses. A sentence must contain one (or the score): a word that
    other kinds share ("time", "Fine", "shoots") does not say what happened."""
    own = FAMILY.get(key, (key,))
    others = tuple(k for k in LEX[lang]["t"] if k not in own)
    return frozenset(_template_tokens(lang, own) - _template_tokens(lang, others) - COMMON[lang])


def _sequence(text: str, lang: Lang) -> list[str]:
    """Words and markers in order, without articles, between two edges ("·")."""
    words = [t for t in re.findall(r"qq\w+|" + TOKEN.pattern, _norm(text)) if t not in ARTICLES[lang]]
    return ["·", *words, "·"]


def _beside(neighbour: str, own: str) -> str:
    """Another canonical phrase beside a name or a phrase counts as an edge: phrases are optional."""
    return "·" if neighbour in PHRASE_MARKERS and neighbour != own else neighbour


@cache
def position_contexts(lang: Lang, key: str) -> tuple[dict[str, frozenset[str]], dict[str, frozenset[str]]]:
    """For a name (qqp, qqteam) or a canonical phrase: the words that stand before, and after, it in
    some template of the key; "·" is an edge. The same reading is applied to a sentence."""
    before: dict[str, set[str]] = {m: set() for m in TRACKED}
    after: dict[str, set[str]] = {m: set() for m in TRACKED}
    for k in FAMILY.get(key, (key,)):
        for templates in LEX[lang]["t"][k]:
            for template in templates:
                text = template.replace("{home} {hs}, {away} {as_}", " qqscore ")
                text = text.replace(f"{LEX[lang]['minute']} {{m}}", " qqminute ")
                text = text.replace("{p}", " qqp ").replace("{team}", " qqteam ")
                for field in PHRASES:
                    text = text.replace("{" + field + "}", f" {_marker(field)} ")
                tokens = _sequence(re.sub(r"\{[^}]*\}", " qqother ", text), lang)
                for i, token in enumerate(tokens):
                    if token in TRACKED:
                        before[token].add(_beside(tokens[i - 1], token))
                        after[token].add(_beside(tokens[i + 1], token))
    return (
        {k: frozenset(v) for k, v in before.items()},
        {k: frozenset(v) for k, v in after.items()},
    )


@cache
def _compounds(lang: Lang, key: str) -> tuple[str, ...]:
    return tuple(sorted(w for w in _template_tokens(lang, FAMILY.get(key, (key,))) if "-" in w))


def _words(text: str) -> int:
    return max(len(text.split()), len(_tokens(text)))


class Verifier:
    def __init__(self, ctx: Context):
        self.ctx = ctx

    def check(self, moment: Moment, description: Description) -> list[str]:
        """Issues found in a description; an empty list means it passed."""
        ctx = self.ctx
        issues: list[str] = []
        if description.moment_id != moment.id:
            issues.append(f"description is for moment {description.moment_id}, not {moment.id}")
        if description.lang != ctx.lang:
            issues.append(f"description language is {description.lang!r}, not {ctx.lang!r}")
        too_long = [
            f"{part} text has more than {MAX_CHARS} characters"
            for part in ("full", "short")
            if len(getattr(description, part)) > MAX_CHARS
        ]
        if too_long:
            return issues + too_long  # never run the pattern checks on huge input

        ref_issues: list[str] = []
        for ref in description.refs:
            if ref.event_id not in moment.event_ids:
                ref_issues.append(f"event {ref.event_id} is not part of moment {moment.id}")
                continue
            actual = getattr(ctx.by_id[ref.event_id], ref.field)
            if actual != ref.value:
                ref_issues.append(f"event {ref.event_id}: {ref.field} is {actual!r}, not {ref.value!r}")
        issues += ref_issues

        involved = ctx.involved(moment)
        text = f"{description.full} {description.short}"
        for name in ctx.all_names:
            if name not in involved and re.search(rf"\b{name}\b", text):
                issues.append(f"{name} is not in this moment")

        last = ctx.by_id[moment.event_ids[-1]]
        allowed = {last.home_score, last.away_score, moment.t // 60}
        allowed |= {ctx.by_id[i].minute for i in moment.event_ids}
        allowed_text = {str(n) for n in allowed}
        for number in sorted({n.lstrip("0") or "0" for n in re.findall(r"\d+", text)} - allowed_text):
            issues.append(f"number {number} is not supported by the events")

        if not description.short.strip() or not description.full.strip():
            issues.append("description is empty")
        if _words(description.full) > MAX_FULL_WORDS:
            issues.append(f"full text has more than {MAX_FULL_WORDS} words")
        if _words(description.short) > MAX_SHORT_WORDS:
            issues.append(f"short text has more than {MAX_SHORT_WORDS} words")
        if _words(description.short) > _words(description.full):
            issues.append("short text is longer than the full text")

        expected = facts(moment, ctx)
        if not ref_issues:
            claimed = {(r.event_id, r.field, r.value) for r in description.refs}
            wanted = {(r.event_id, r.field, r.value) for r in expected.refs}
            if claimed != wanted:
                issues.append(
                    f"refs must be exactly the facts of the moment: missing {sorted(wanted - claimed, key=str)}, "
                    f"unexpected {sorted(claimed - wanted, key=str)}"
                )
        issues += self._grounding("full", description.full, expected, REQUIRED_FULL)
        issues += self._grounding("short", description.short, expected, REQUIRED_SHORT)
        return issues

    def _position(self, part: str, marked: str, f: Facts, names: dict[str, str]) -> list[str]:
        """A name or a phrase stands only between the words some template of the key puts around it."""
        for entity, marker in (("p", "qqp"), ("team", "qqteam")):
            if entity in names:
                marked = re.sub(rf"(?<!\w){re.escape(names[entity])}(?!\w)", f" {marker} ", marked)
        tokens = _sequence(marked, self.ctx.lang)
        before, after = position_contexts(self.ctx.lang, f.key)
        for i, token in enumerate(tokens):
            if token in TRACKED and not (
                _beside(tokens[i - 1], token) in before[token] and _beside(tokens[i + 1], token) in after[token]
            ):
                return [f"{part} text: a name or a phrase is not where a {f.key} sentence puts it"]
        return []

    def _grounding(
        self, part: str, text: str, f: Facts, required: dict[str, tuple[str, ...]]
    ) -> list[str]:
        """Only canonical phrases, the moment's named player and team, and the key's vocabulary."""
        fields = f.fields
        rest, marked, found = _norm(text), _norm(text), set()
        for name in PHRASES:
            phrase = fields.get(name)
            if phrase:
                pattern = re.compile(rf"(?<!\w){re.escape(_norm(str(phrase)))}(?!\w)")
                if pattern.search(rest):
                    found.add(name)
                rest = pattern.sub(" ", rest)
                marked = pattern.sub(f" {_marker(name)} ", marked)
        for compound in _compounds(self.ctx.lang, f.key):  # "half time" is "half-time", not two words
            spaced = re.compile(rf"(?<!\w){re.escape(compound.replace('-', ' '))}(?!\w)")
            rest, marked = spaced.sub(compound, rest), spaced.sub(compound, marked)
        vocab = vocabulary(self.ctx.lang, f.key)
        names = {n: _norm(str(fields[n])) for n in ("p", "team") if n in fields}
        permitted = vocab | set(names.values())
        tokens = _tokens(rest)
        issues = [
            f"{part} text: '{token}' is not allowed in a {f.key} description"
            for token in dict.fromkeys(tokens)
            if token not in permitted
        ]
        stray = {ch for ch in TOKEN.sub(" ", rest) if not HARMLESS.fullmatch(ch)}
        if stray:
            shown = "".join(sorted(stray)[:5]).encode("unicode_escape").decode()
            issues.append(f"{part} text: symbols or control characters are not allowed ({shown})")
        says_something = any(token in outcome_words(self.ctx.lang, f.key) for token in tokens)
        if not (says_something or ("score" in found and f.key in SCORE_IS_CONTENT)):
            issues.append(f"{part} text does not say what happened ({f.key})")
        issues += self._position(part, marked, f, names)
        for name in required.get(f.key, ()):
            if (name in names and names[name] not in tokens) or (name == "score" and name not in found):
                issues.append(f"{part} text must state the {'score' if name == 'score' else name}")
        return issues
