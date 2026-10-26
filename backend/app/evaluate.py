"""Evaluation harness: counts, not models. `python -m app.evaluate --seeds 20 --write ../docs/evaluation.md`.

Every figure is a plain count over generated matches, so a reader can check it by hand. Three things
are kept apart: false acceptance (false text the verifier lets through), false rejection (valid text
it turns away) and fallback (what the listener hears instead).
"""

import argparse
import random
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from app.contracts import Description, FactRef, Moment, Profile
from app.corpora import NATURAL, VOCAB_AWARE, patterns_for
from app.describer import LEX, Context, Facts, FlawedDescriber, TemplateDescriber, facts
from app.match_gen import SEED, generate_match
from app.moments import detect_moments
from app.pipeline import MAX_ATTEMPTS, build_presets, build_session
from app.verifier import ARTICLES, FAMILY, Verifier, outcome_words, position_contexts, vocabulary

DETAILS = ("essential", "standard", "full")
LANGS = ("en", "it")
CORPORA = {"written without the word list": NATURAL, "written with the word list in hand": VOCAB_AWARE}


def _wrong_name(m: Moment, d: Description, ctx: Context) -> Description | None:
    involved = ctx.involved(m)
    present = [n for n in involved if n in d.full]
    if not present:
        return None
    foreign = next(n for n in ctx.all_names if n not in involved)
    return d.model_copy(update={"full": d.full.replace(present[0], foreign)})


def _wrong_number(m: Moment, d: Description, ctx: Context) -> Description | None:
    return d.model_copy(update={"full": d.full + " That is the 99th of the season."})


def _wrong_ref(m: Moment, d: Description, ctx: Context) -> Description | None:
    if not d.refs:
        return None
    first = d.refs[0]
    value = first.value + 1 if isinstance(first.value, int) else f"{first.value}x"
    wrong = FactRef(event_id=first.event_id, field=first.field, value=value)
    return d.model_copy(update={"refs": [wrong, *d.refs[1:]]})


def _foreign_event(m: Moment, d: Description, ctx: Context) -> Description | None:
    stray = FactRef(event_id=max(ctx.by_id) + 1, field="kind", value="goal")
    return d.model_copy(update={"refs": [*d.refs, stray]})


def _too_long(m: Moment, d: Description, ctx: Context) -> Description | None:
    return d.model_copy(update={"full": d.full + " " + " ".join(["and"] * 45)})


def _both(d: Description, change: Callable[[str], str]) -> Description:
    return d.model_copy(update={"full": change(d.full), "short": change(d.short)})


def _wrong_team(m: Moment, d: Description, ctx: Context) -> Description | None:
    a, b = ctx.short("home"), ctx.short("away")
    last = ctx.by_id[m.event_ids[-1]]
    if m.kind in ("halftime", "fulltime", "score_update") and last.home_score == last.away_score:
        return None  # "Harbour 1, Northgate 1" is still true
    new = _both(d, lambda t: re.sub(rf"\b({a}|{b})\b", lambda x: b if x.group(1) == a else a, t))
    return None if new == d else new


def _wrong_lane(m: Moment, d: Description, ctx: Context) -> Description | None:
    for group in ("lane_from", "lane_down", "side"):
        phrases = LEX[ctx.lang][group]
        for lane, phrase in phrases.items():
            if phrase in d.full:
                other = next(p for k, p in phrases.items() if k != lane)
                return _both(d, lambda t, p=phrase, o=other: t.replace(p, o))
    return None


def _foreign_word(m: Moment, d: Description, ctx: Context) -> Description | None:
    return d.model_copy(update={"full": d.full + " A controversial penalty."})


def _no_refs(m: Moment, d: Description, ctx: Context) -> Description | None:
    return d.model_copy(update={"refs": []})


def _roles_exchanged(m: Moment, d: Description, ctx: Context) -> Description | None:
    f = facts(m, ctx)
    if f.key != "goal_assist":
        return None
    p, a = f.fields["p"], f.fields["a"]
    return _both(d, lambda t: re.sub(rf"\b({p}|{a})\b", lambda x: a if x.group(1) == p else p, t))


def _emoji(m: Moment, d: Description, ctx: Context) -> Description | None:
    return d.model_copy(update={"full": d.full + " " + chr(0x274C)})


def _content_free(m: Moment, d: Description, ctx: Context) -> Description | None:
    return d.model_copy(update={"full": "!", "short": "!"})


def _unstated_lane(m: Moment, d: Description, ctx: Context) -> Description | None:
    """The lane of the last event, said in a moment whose refs do not carry a lane."""
    lane = ctx.by_id[m.event_ids[-1]].lane
    if lane is None or any(r.field == "lane" for r in d.refs):
        return None
    return d.model_copy(update={"full": d.full + " " + LEX[ctx.lang]["lane_from"][lane]})


MUTATIONS: dict[str, Callable[[Moment, Description, Context], Description | None]] = {
    "wrong player name": _wrong_name,
    "stray number": _wrong_number,
    "wrong fact in a ref": _wrong_ref,
    "ref to an unrelated event": _foreign_event,
    "text far too long": _too_long,
    "wrong team": _wrong_team,
    "another lane": _wrong_lane,
    "opinion or unsupported event word": _foreign_word,
    "refs left empty": _no_refs,
    "scorer and assister exchanged": _roles_exchanged,
    "emoji or symbol": _emoji,
    "text that says nothing": _content_free,
    "lane of an event the moment does not state": _unstated_lane,
}


def random_conforming(f: Facts, lang: str, rng: random.Random, min_words: int = 0) -> str | None:
    """A random sentence that conforms to SPEC §5 by construction: a template of the moment's key in
    which words are replaced by other words of the key, never an outcome word, and, next to a name, only
    by a word the templates put there. By the contract the verifier must accept every one; it checks
    the implementation, not safety (the tests check conformance with an independent reading)."""
    lang_articles = ARTICLES[lang]  # type: ignore[index]
    vocab = sorted(w for w in vocabulary(lang, f.key) if w not in lang_articles)  # type: ignore[arg-type]
    outcome = outcome_words(lang, f.key)  # type: ignore[arg-type]
    before, after = position_contexts(lang, f.key)  # type: ignore[arg-type]
    names = {"{p}": "qqp", "{team}": "qqteam", "{assist}": "qqassist", "{chain}": "qqchain", "{zone}": "qqzone",
             "{dir}": "qqdir", "{lane_from}": "qqlane", "{lane_down}": "qqlane", "{side}": "qqlane",
             "{score}": "qqscore", "{minute}": "qqminute"}
    minute = LEX[lang]["minute"]  # type: ignore[index]
    templates = [
        a.replace("{home} {hs}, {away} {as_}", "{score}").replace(minute + " {m}", "{minute}")
        for k in FAMILY.get(f.key, (f.key,))
        for a, _ in LEX[lang]["t"][k]  # type: ignore[index]
    ]
    usable = []
    for template in templates:
        try:
            if len(template.format(**f.fields).split()) >= min_words:
                usable.append(template)
        except KeyError:  # an assist template for a goal without an assist
            continue
    if not usable:
        return None
    template = rng.choice(usable)
    items = list(re.finditer(r"\{[^}]*\}|[^\W\d_]+(?:['\-][^\W\d_]+)*", template))
    kept = [i for i, m in enumerate(items) if m.group().lower() not in lang_articles]  # articles are transparent
    text = template
    for pos in reversed(range(len(kept))):
        m = items[kept[pos]]
        word = m.group()
        if word.startswith("{") or word.lower() in outcome or rng.random() > 0.35:
            continue
        prev_item = items[kept[pos - 1]].group() if pos else None
        next_item = items[kept[pos + 1]].group() if pos + 1 < len(kept) else None
        candidates = vocab
        if prev_item in names:
            candidates = [w for w in candidates if w in after[names[prev_item]]]
        if next_item in names:
            candidates = [w for w in candidates if w in before[names[next_item]]]
        if candidates:
            text = text[: m.start()] + rng.choice(candidates) + text[m.end() :]
    return text.format(**f.fields)


def _record_corpora(moment, described, ctx, verifier, acc) -> None:
    """Every sentence of each corpus on every moment it applies to, and the one sentence a
    deterministic describer would say for the moment (it is then verified or falls back)."""
    f = facts(moment, ctx)
    for name, corpus in CORPORA.items():
        patterns = patterns_for(corpus, ctx.lang, f.key)
        usable = []
        for pattern in patterns:
            try:
                text = pattern.format(**f.fields)
            except KeyError:  # e.g. an assist clause for a goal without an assist
                continue
            usable.append(pattern)
            issues = verifier.check(moment, described.model_copy(update={"full": text}))
            stat = acc["patterns"].setdefault((name, ctx.lang, f.key, pattern), [0, 0])
            stat[0] += not issues
            stat[1] += 1
            for issue in issues:
                if found := re.search(r"full text: '([^']+)' is not allowed", issue):
                    acc["words"][(name, ctx.lang)][found.group(1)] += 1
        if usable:
            chosen = usable[moment.id % len(usable)].format(**f.fields)
            ok = not verifier.check(moment, described.model_copy(update={"full": chosen}))
            acc["said"].setdefault((name, ctx.lang), [0, 0])[0 if ok else 1] += 1


def _record_false_rejections(moment, described, ctx, verifier, acc, seed) -> None:
    f = facts(moment, ctx)
    for key in FAMILY.get(f.key, (f.key,)):
        for full, short in LEX[ctx.lang]["t"][key]:
            try:
                variant = described.model_copy(
                    update={"full": full.format(**f.fields), "short": short.format(**f.fields)}
                )
            except KeyError:  # an assist template for a goal without an assist
                continue
            acc["variants"][1] += 1
            acc["variants"][0] += not verifier.check(moment, variant)
    rng = random.Random(moment.id * 7 + seed)
    for _ in range(2):
        text = random_conforming(f, ctx.lang, rng, len(described.short.split()))
        if text is None:
            continue
        acc["conforming"][1] += 1
        acc["conforming"][0] += not verifier.check(moment, described.model_copy(update={"full": text}))
    _record_corpora(moment, described, ctx, verifier, acc)


def evaluate(seeds: list[int]) -> dict:
    totals = {
        "sessions": 0,
        "overlaps": 0,
        "cues": 0,
        "short": 0,
        "speech_ms": 0,
        "duration_ms": 0,
        "priority": {str(p): [0, 0] for p in range(4)},
        "retry_runs": 0,
        "retry_ok": 0,
        "fallback_runs": 0,
        "fallback_ok": 0,
    }
    acc: dict = {
        "variants": [0, 0],  # accepted, tried
        "conforming": [0, 0],
        "patterns": {},  # (corpus, lang, key, sentence) -> [accepted, tried]
        "said": {},  # (corpus, lang) -> [said as written, template fallback]
        "words": {(name, lang): Counter() for name in CORPORA for lang in LANGS},
    }
    planted = {name: [0, 0] for name in MUTATIONS}  # applicable, caught
    for seed in seeds:
        match = generate_match(seed)
        for preset in build_presets(match):
            events = [e for e in match.events if preset.from_s <= e.t <= preset.to_s]
            for detail in DETAILS:
                for lang in LANGS:
                    profile = Profile(detail=detail, lang=lang)
                    session = build_session(match, preset, profile, TemplateDescriber())
                    totals["sessions"] += 1
                    report = session.report
                    totals["overlaps"] += report.overlaps
                    totals["cues"] += report.cues
                    totals["short"] += sum(1 for c in session.cues if c.variant == "short")
                    totals["speech_ms"] += report.speech_ms
                    totals["duration_ms"] += session.duration_ms
                    for p, stats in report.by_priority.items():
                        totals["priority"][p][0] += stats.total
                        totals["priority"][p][1] += stats.scheduled
                    if detail == "standard":
                        ctx = Context(match, lang)
                        verifier = Verifier(ctx)
                        moments = detect_moments(events, detail)
                        described = TemplateDescriber().describe(moments, ctx, {}, 1)
                        for moment in moments:
                            for name, mutate in MUTATIONS.items():
                                broken = mutate(moment, described[moment.id], ctx)
                                if broken is None:
                                    continue
                                planted[name][0] += 1
                                planted[name][1] += bool(verifier.check(moment, broken))
                            _record_false_rejections(moment, described[moment.id], ctx, verifier, acc, seed)
                        retried = build_session(match, preset, profile, FlawedDescriber(bad_attempts=1))
                        totals["retry_runs"] += 1
                        totals["retry_ok"] += (
                            retried.report.attempts == 2
                            and retried.report.fallback == 0
                            and [c.text for c in retried.cues] == [c.text for c in session.cues]
                        )
                        fell = build_session(match, preset, profile, FlawedDescriber(MAX_ATTEMPTS))
                        totals["fallback_runs"] += 1
                        totals["fallback_ok"] += (
                            fell.report.fallback == fell.report.moments
                            and fell.report.attempts == MAX_ATTEMPTS
                            and [c.text for c in fell.cues] == [c.text for c in session.cues]
                        )
    return {"seeds": len(seeds), "totals": totals, "planted": planted, "false_rejection": acc}


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "n/a"


def _corpus_rows(acc: dict) -> list[str]:
    rows = []
    for name in CORPORA:
        for lang in LANGS:
            mine = {k: v for k, v in acc["patterns"].items() if k[0] == name and k[1] == lang}
            sentences = {(k[2], k[3]): v for k, v in mine.items()}
            everywhere = sum(1 for a, n in sentences.values() if a == n)
            never = sum(1 for a, _ in sentences.values() if a == 0)
            ok = sum(a for a, _ in sentences.values())
            tried = sum(n for _, n in sentences.values())
            rows.append(
                f"| {name} | `{lang}` | {len(sentences)} | {everywhere} | {never} | {ok} of {tried} ({_pct(ok, tried)}) |"
            )
    return rows


def to_markdown(result: dict) -> str:
    t, planted, acc = result["totals"], result["planted"], result["false_rejection"]
    lines = [
        "# SoundPitch evaluation",
        "",
        (f"Generated by `python -m app.evaluate --seeds {result['seeds']}`. Every figure is a count over "
         f"{result['seeds']} generated matches x 5 windows x 3 detail levels x 2 languages = "
         f"{t['sessions']} sessions. No model is involved in these numbers. "
         "The score-context sentence (S31) is written by code after the verifier and is covered by "
         "`backend/tests/test_stakes.py`, not by these counts."),
        "",
        "## Timing",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Overlapping cues | {t['overlaps']} |",
    ]
    names = {"3": "must-say (goal, kick-off, half-time, full-time)", "2": "priority 2 (shots, saves, corners)",
             "1": "priority 1 (turnovers, fouls, build-ups)", "0": "priority 0 (routine passing)"}
    for p in ("3", "2", "1", "0"):
        total, scheduled = t["priority"][p]
        lines.append(f"| Moments said, {names[p]} | {scheduled} of {total} ({_pct(scheduled, total)}) |")
    lines += [
        f"| Cues that needed the short sentence | {t['short']} of {t['cues']} ({_pct(t['short'], t['cues'])}) |",
        f"| Share of the window spent speaking | {_pct(t['speech_ms'], t['duration_ms'])} |",
        "",
        "## False acceptance: false or unsupported text the verifier lets through",
        "",
        ("Each template description is altered on purpose so that it states something false or unsupported "
         "(standard detail, both languages). The verifier must reject every one. These alterations are the "
         "kinds the verifier was built for; the generated attacks in `backend/tests/test_grounding.py` and the "
         "separate adversarial review go further, and none of this measures a real model."),
        "",
        "| Planted error | Cases | Wrongly accepted |",
        "|---|---|---|",
    ]
    for name, (applicable, caught) in planted.items():
        lines.append(f"| {name} | {applicable} | {applicable - caught} ({_pct(applicable - caught, applicable)}) |")
    variants, conforming = acc["variants"], acc["conforming"]
    lines += [
        "",
        "## False rejection: valid text the verifier turns away",
        "",
        ("The other risk. It costs naturalness, not trust, because the template fallback speaks instead. "
         "Denominators are explicit."),
        "",
        "| Check | Accepted |",
        "|---|---|",
        f"| Every template variant of every moment | {variants[0]} of {variants[1]} ({_pct(*variants)}) |",
        (f"| Random sentences made only of what SPEC §5 allows for the moment (two per moment) "
         f"| {conforming[0]} of {conforming[1]} ({_pct(*conforming)}) |"),
        "",
        ("Hand-written commentary, all of it true. *Sentences* are distinct sentence patterns, each tried on "
         "every moment of its kind; *accepted on every moment* means no rejection at all. The last column "
         "counts sentence-on-moment pairs, so it is weighted by how often each kind of moment occurs."),
        "",
        "| Corpus | Language | Sentences | Accepted on every moment | Accepted on none | Sentence-on-moment pairs accepted |",
        "|---|---|---|---|---|---|",
        *_corpus_rows(acc),
        "",
        ("The first corpus is the price of a closed vocabulary (SPEC §5, D9) when a writer ignores it. The "
         "second, written by a separate AI review agent that had the word lists, tells how reachable the contract "
         "is. Neither is a measurement of a model (that needs a live run: `python -m app.foundry_run`). Words that caused most rejections in the "
         "first corpus, to be reviewed for the vocabulary (a word may join it only if it cannot change a fact):"),
        "",
    ]
    for (name, lang), counter in acc["words"].items():
        if name == "written without the word list":
            top = ", ".join(f"`{word}` ({n})" for word, n in counter.most_common(14))
            lines.append(f"- `{lang}`: {top}")
    lines += [
        "",
        "## Fallback: what the listener hears",
        "",
        ("A deterministic describer says one sentence of the corpus for each moment it has a sentence for "
         "(sentence number = moment id modulo the number of sentences). A rejected sentence is not rescued by a "
         "retry, because the describer would repeat it, so the moment ends in the verified template. Moments "
         "without a sentence in the corpus are not counted."),
        "",
        "| Corpus | Language | Moments | Said as written (verified) | Template fallback |",
        "|---|---|---|---|---|",
    ]
    for (name, lang), (said, fell_back) in sorted(acc["said"].items()):
        total = said + fell_back
        lines.append(
            f"| {name} | `{lang}` | {total} | {said} ({_pct(said, total)}) | {fell_back} ({_pct(fell_back, total)}) |"
        )
    lines += [
        "",
        "## Retry and fallback",
        "",
        "| Scenario | Runs | As specified |",
        "|---|---|---|",
        (f"| First attempt wrong, retry right: verified on attempt 2, same text as a clean run "
         f"| {t['retry_runs']} | {t['retry_ok']} ({_pct(t['retry_ok'], t['retry_runs'])}) |"),
        (f"| Every attempt wrong: all moments use the template fallback after 3 attempts, same track "
         f"| {t['fallback_runs']} | {t['fallback_ok']} ({_pct(t['fallback_ok'], t['fallback_runs'])}) |"),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    seeds = [SEED] + list(range(1, args.seeds))
    text = to_markdown(evaluate(seeds))
    if args.write:
        args.write.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
