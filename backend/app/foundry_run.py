"""Run the Foundry describer on every preset and write the evidence (SPEC §11, S12).

    python -m app.foundry_run --write ../docs/evidence/foundry-run.md

It needs a Foundry project and a model deployment (`FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, `az login`)
and spends model calls: 5 presets x 3 detail levels x 2 languages, at most 3 attempts each. The usage
ledger (D11) decides every call with the same limits as the API (2 a minute, 20 a day, 2 EUR a month by
default), so a full run needs those limits raised on purpose in the environment and `--pause-seconds`.
Nothing is loosened for the run: it reports how often the real model's words pass the verifier, and why not.
"""

import argparse
import datetime
import os
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from app.contracts import Profile
from app.describer import LEX, Context, facts
from app.foundry import (
    MAX_BATCH,
    AgentFrameworkClient,
    FoundryDescriber,
    FoundryNotConfigured,
    LlmClient,
    Reply,
    build_prompt,
    chunk_key,
    ledger_from_env,
    reply_key,
    settings_from_env,
)
from app.match_gen import SEED, generate_match
from app.moments import detect_moments
from app.pipeline import build_presets, build_session
from app.usage import UsageLedger
from app.verifier import FAMILY

DETAILS = ("essential", "standard", "full")
LANGS = ("en", "it")
REASONS = (
    (r"is not allowed in a", "a word outside the vocabulary of the moment"),
    (r"must state", "a required fact is missing"),
    (r"not where a", "a name or a phrase out of its place"),
    (r"does not say what happened", "no word that says what happened"),
    (r"symbols or control", "a symbol or an emoji"),
    (r"more than \d+ (words|characters)", "too long"),
    (r"no valid description|could not be checked", "no usable sentence returned"),
    (r"not in this moment|not supported by the events|refs must", "a name or a number the events do not support"),
)


class TimedClient:
    """Wraps an LlmClient to record how long each call took and whether it failed."""

    def __init__(self, inner: LlmClient):
        self.inner = inner
        self.durations: list[float] = []
        self.errors = 0

    def complete(self, system: str, user: str) -> str | Reply:
        started = time.monotonic()
        try:
            return self.inner.complete(system, user)
        except Exception:
            self.errors += 1
            raise
        finally:
            self.durations.append(time.monotonic() - started)


class Paced:
    """Waits before each request to the model, outside the call: a pause inside the call would count against the
    describer's timeout and make every real call fail. It keeps a run under the deployment's tokens-per-minute
    ceiling and under the ledger's calls-per-minute limit, which count reservations, not answers."""

    def __init__(self, inner: FoundryDescriber, pause_s: float):
        self.inner, self.pause_s = inner, pause_s

    @property
    def note(self) -> str:
        return self.inner.note

    def _will_ask(self, moments, ctx, feedback, attempt) -> bool:
        """True if any request of this attempt is not already stored in the ledger (a stored one costs nothing)."""
        for start in range(0, len(moments), MAX_BATCH):
            chunk = moments[start : start + MAX_BATCH]
            system, _ = build_prompt(chunk, ctx, feedback)
            if self.inner.ledger.cache_get(reply_key(chunk_key(chunk, ctx, feedback, attempt), system)) is None:
                return True
        return False

    def describe(self, moments, ctx, feedback, attempt):
        if self._will_ask(moments, ctx, feedback, attempt):
            time.sleep(self.pause_s)
        return self.inner.describe(moments, ctx, feedback, attempt)


def reason_of(issue: str) -> str:
    for pattern, label in REASONS:
        if re.search(pattern, issue):
            return label
    return "another reason"


def template_texts(moment, ctx: Context) -> set[str]:
    """Every sentence the templates would say for this moment (full and short)."""
    f = facts(moment, ctx)
    found: set[str] = set()
    for key in FAMILY.get(f.key, (f.key,)):
        for pair in LEX[ctx.lang]["t"][key]:
            for template in pair:
                try:
                    found.add(template.format(**f.fields))
                except KeyError:  # an assist template for a goal without an assist
                    continue
    return found


def run(client: LlmClient, ledger: UsageLedger, pause_s: float = 0.0) -> dict:
    """Every preset, detail level and language through the real pipeline with this client."""
    match = generate_match(SEED)
    timed = TimedClient(client)
    describer = Paced(FoundryDescriber(timed, ledger), pause_s)
    stats = {lang: Counter() for lang in LANGS}
    reasons = {lang: Counter() for lang in LANGS}
    words = {lang: Counter() for lang in LANGS}
    for preset in build_presets(match):
        for detail in DETAILS:
            for lang in LANGS:
                session = build_session(match, preset, Profile(detail=detail, lang=lang), describer)
                s = stats[lang]
                s["sessions"] += 1
                s["moments"] += session.report.moments
                s["fallback"] += session.report.fallback
                s["verified"] += session.report.verified
                s["retried_sessions"] += session.report.attempts > 1
                events = [e for e in match.events if preset.from_s <= e.t <= preset.to_s]
                moments = {m.id: m for m in detect_moments(events, detail)}
                ctx = Context(match, lang)
                for cue in session.cues:
                    if cue.status == "verified":
                        s["cues_verified"] += 1
                        s["cues_own_words"] += cue.text not in template_texts(moments[cue.moment_id], ctx)
                s["failed_calls"] += sum(1 for t in session.trace if t.step == "describer" and t.status == "failed")
                for step in session.trace:
                    if step.step != "verifier":
                        continue
                    found = re.match(r"(\d+) of (\d+) rejected: (.*)", step.detail)
                    asked = int(found.group(2)) if found else int(step.detail.split()[0])
                    rejected = int(found.group(1)) if found else 0
                    s[f"verified_at_{step.attempt}"] += asked - rejected
                    if found:
                        reasons[lang][reason_of(found.group(3))] += rejected
                        for word in re.findall(r"'([^']+)' is not allowed", found.group(3)):
                            words[lang][word] += 1
    return {
        "stats": stats,
        "reasons": reasons,
        "words": words,
        "latency": timed.durations,
        "call_errors": timed.errors,
    }


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "n/a"


def to_markdown(result: dict, model: str, today: datetime.date) -> str:
    lat = sorted(result["latency"])
    p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else 0.0
    lines = [
        "# Foundry run",
        "",
        f"Date: {today.isoformat()}. Model deployment: `{model}`. Written by `python -m app.foundry_run`.",
        "",
        (
            "Every preset (5) at every detail level (3) in English and Italian, through the real pipeline. "
            "Nothing was loosened for the run. The reasons below are the *first* issue of each rejected "
            "moment only."
        ),
        "",
        "| Language | Sessions | Moments | Verified at attempt 1 | Verified at attempt 2 or 3 | Template fallback |",
        "|---|---|---|---|---|---|",
    ]
    for lang, s in result["stats"].items():
        first = s["verified_at_1"]
        later = s["verified"] - first
        lines.append(
            f"| `{lang}` | {s['sessions']} | {s['moments']} | {first} of {s['moments']} ({_pct(first, s['moments'])}) "
            f"| {later} ({_pct(later, s['moments'])}) | {s['fallback']} ({_pct(s['fallback'], s['moments'])}) |"
        )
    lines += [
        "",
        "| Language | Sessions that needed a retry | Failed calls (error, timeout, unusable reply) |",
        "|---|---|---|",
    ]
    for lang, s in result["stats"].items():
        lines.append(f"| `{lang}` | {s['retried_sessions']} of {s['sessions']} | {s['failed_calls']} |")
    lines += [
        "",
        "| Language | Spoken cues the model wrote | Of those, in its own words (not a template sentence) |",
        "|---|---|---|",
    ]
    for lang, s in result["stats"].items():
        lines.append(f"| `{lang}` | {s['cues_verified']} | {s['cues_own_words']} ({_pct(s['cues_own_words'], s['cues_verified'])}) |")
    lines += [
        "",
        (
            f"Model calls: {len(lat)} ({result['call_errors']} raised). "
            f"Median latency {statistics.median(lat) if lat else 0:.2f} s, p95 {p95:.2f} s, "
            f"slowest {lat[-1] if lat else 0:.2f} s."
        ),
        "",
        "## Why moments were rejected (first issue, all attempts)",
        "",
    ]
    for lang, counter in result["reasons"].items():
        lines.append(f"**`{lang}`**")
        lines += [f"- {label}: {n}" for label, n in counter.most_common()] or ["- none"]
        top = ", ".join(f"`{w}` ({n})" for w, n in result["words"][lang].most_common(15))
        lines += [f"- words outside the vocabulary: {top or 'none'}", ""]
    lines += [
        (
            "Review those words before the vocabulary grows (SPEC §5): a word may join only if it cannot change "
            "a fact or a relation. A rejected sentence is not an error of the product: the verified template "
            "speaks instead."
        ),
        "",
    ]
    return "\n".join(lines)


def main(
    argv: list[str] | None = None,
    client: LlmClient | None = None,
    model: str | None = None,
    ledger: UsageLedger | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Run the Foundry describer on every preset and report.")
    parser.add_argument("--write", type=Path, help="write the report here (docs/evidence/foundry-run.md)")
    parser.add_argument(
        "--pause-seconds", type=float, default=0.0, help="wait before each call (30 for the default of 2 calls a minute)"
    )
    args = parser.parse_args(argv)
    if client is None:
        try:
            endpoint, deployment = settings_from_env()
            client = AgentFrameworkClient(endpoint, deployment)
            model = deployment
        except FoundryNotConfigured as exc:
            print(f"cannot run against Foundry: {exc}", file=sys.stderr)
            return 2
    try:
        ledger = ledger or ledger_from_env()
    except FoundryNotConfigured as exc:
        print(f"cannot run against Foundry: {exc}", file=sys.stderr)
        return 2
    result = run(client, ledger, args.pause_seconds)
    text = to_markdown(result, model or os.environ.get("FOUNDRY_MODEL", "unknown"), datetime.date.today())
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
