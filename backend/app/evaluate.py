"""Evaluation harness: counts, not models. `python -m app.evaluate --seeds 20 --write ../docs/evaluation.md`.

Every figure is a plain count over generated matches, so a reader can check it by hand.
"""

import argparse
from collections.abc import Callable
from pathlib import Path

from app.contracts import Description, FactRef, Moment, Profile
from app.describer import Context, FlawedDescriber, TemplateDescriber
from app.match_gen import SEED, generate_match
from app.moments import detect_moments
from app.pipeline import MAX_ATTEMPTS, build_presets, build_session
from app.verifier import Verifier

DETAILS = ("essential", "standard", "full")
LANGS = ("en", "it")


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


MUTATIONS: dict[str, Callable[[Moment, Description, Context], Description | None]] = {
    "wrong player name": _wrong_name,
    "stray number": _wrong_number,
    "wrong fact in a ref": _wrong_ref,
    "ref to an unrelated event": _foreign_event,
    "text far too long": _too_long,
}


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
                        ctx, verifier = Context(match, lang), Verifier(Context(match, lang))
                        described = TemplateDescriber().describe(
                            detect_moments(events, detail), ctx, {}, 1
                        )
                        for moment in detect_moments(events, detail):
                            for name, mutate in MUTATIONS.items():
                                broken = mutate(moment, described[moment.id], ctx)
                                if broken is None:
                                    continue
                                planted[name][0] += 1
                                planted[name][1] += bool(verifier.check(moment, broken))
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
    return {"seeds": len(seeds), "totals": totals, "planted": planted}


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "n/a"


def to_markdown(result: dict) -> str:
    t, planted = result["totals"], result["planted"]
    lines = [
        "# SoundPitch evaluation",
        "",
        (f"Generated by `python -m app.evaluate --seeds {result['seeds']}`. Every figure is a count over "
        f"{result['seeds']} generated matches x 5 windows x 3 detail levels x 2 languages = "
        f"{t['sessions']} sessions. No model is involved in these numbers."),
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
        "## Verifier: planted errors",
        "",
        "Each template description is broken on purpose and the verifier must reject it.",
        "",
        "| Planted error | Cases | Caught |",
        "|---|---|---|",
    ]
    for name, (applicable, caught) in planted.items():
        lines.append(f"| {name} | {applicable} | {caught} ({_pct(caught, applicable)}) |")
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
