"""Orchestrate Interpret -> Explain -> Verify -> Render with retries and a verified fallback."""

import itertools
import os

from app.contracts import Description, Match, Moment, Preset, Profile, Report, Session, TraceStep
from app.describer import Context, Describer, FlawedDescriber, TemplateDescriber
from app.moments import detect_moments
from app.render import earcons, pan_of, track
from app.timing import Candidate, plan
from app.verifier import Verifier

MAX_ATTEMPTS = 3  # 1 try + 2 retries
CALM_RATE = 0.9


def build_presets(match: Match) -> list[Preset]:
    events = match.events
    goals = [e for e in events if e.kind == "goal"]
    presets = [Preset(id="kickoff", title="Kick-off", from_s=0, to_s=75)]
    for n, goal in enumerate(goals, start=1):
        scorer = (match.home if goal.team == "home" else match.away).short
        presets.append(
            Preset(
                id=f"goal_{n}",
                title=f"Goal {n}: {scorer}, minute {goal.minute}",
                from_s=max(0, goal.t - 100),
                to_s=goal.t + 35,
            )
        )
    end = events[-1].t
    presets.append(Preset(id="final_whistle", title="The final whistle", from_s=end - 60, to_s=end))
    return presets


def describer_from_env() -> Describer:
    mode = os.environ.get("SOUNDPITCH_LLM") or "scripted"
    if mode == "scripted":
        return TemplateDescriber()
    if mode == "bad_then_good":
        return FlawedDescriber(bad_attempts=1)
    if mode == "always_bad":
        return FlawedDescriber(bad_attempts=MAX_ATTEMPTS)
    if mode == "replay":
        # recorded Foundry replies: no SDK, no network, no cost
        from app.replay import shared_replay

        return shared_replay()
    if mode == "foundry":
        from app.foundry import shared_describer  # the SDK is only touched when this mode is chosen

        return shared_describer()
    raise ValueError(f"unknown SOUNDPITCH_LLM: {mode}")


def _snapshot(description: object) -> Description | None:
    """A frozen, validated copy of what a describer returned. Only the copy is checked and spoken, so
    an object that answers differently each time it is read cannot pass the check and then change."""
    if not isinstance(description, Description):
        return None
    try:
        return Description.model_validate(description.model_dump())
    except Exception:  # noqa: BLE001 - anything unreadable is simply not a description
        return None


def _issues(verifier: Verifier, moment: Moment, description: Description | None) -> list[str]:
    """Issues with a description. A check that cannot run rejects: it never passes."""
    if description is None:
        return ["no valid description returned"]
    try:
        return verifier.check(moment, description)
    except Exception as exc:  # noqa: BLE001 - fail closed, whatever the input did to the check
        return [f"the description could not be checked ({type(exc).__name__})"]


def describe_step(
    describer: Describer,
    ctx: Context,
    pending: list[Moment],
    feedback: dict[int, list[str]],
    attempt: int,
    trace: list[TraceStep],
    executor: str | None = None,
) -> dict[int, Description]:
    """One attempt of the describer. Any failure burns the attempt, not the session."""
    try:
        described = describer.describe(pending, ctx, feedback, attempt)
        note = getattr(describer, "note", "")  # e.g. the model call cap was reached
        detail = f"{len(pending)} moments" + (f"; {note}" if note else "")
        trace.append(TraceStep(step="describer", status="ok", attempt=attempt, detail=detail, executor=executor))
    except Exception as exc:  # noqa: BLE001 - any describer failure burns an attempt, not the session
        described = {}
        trace.append(
            TraceStep(step="describer", status="failed", attempt=attempt, detail=type(exc).__name__, executor=executor)
        )
    return described


def verify_step(
    verifier: Verifier,
    pending: list[Moment],
    described: dict[int, Description],
    feedback: dict[int, list[str]],
    accepted: dict[int, tuple[Description, str]],
    attempt: int,
    trace: list[TraceStep],
    executor: str | None = None,
) -> list[Moment]:
    """Check the descriptions of one attempt. Accepted ones are recorded, the issues of the rest become the
    feedback of the next attempt; returns the moments still pending."""
    failed = []
    for moment in pending:
        description = _snapshot(described.get(moment.id))
        issues = _issues(verifier, moment, description)
        if issues:
            feedback[moment.id] = issues
            failed.append(moment)
        else:
            accepted[moment.id] = (description, "verified")
    first = feedback[failed[0].id][0] if failed else ""
    trace.append(
        TraceStep(
            step="verifier",
            status="failed" if failed else "ok",
            attempt=attempt,
            detail=f"{len(failed)} of {len(pending)} rejected: {first}" if failed else f"{len(pending)} verified",
            executor=executor,
        )
    )
    return failed


def fallback_step(
    verifier: Verifier,
    ctx: Context,
    pending: list[Moment],
    attempt: int,
    accepted: dict[int, tuple[Description, str]],
    trace: list[TraceStep],
    executor: str | None = None,
) -> None:
    """The deterministic template for the moments the describer could not get right; it must verify."""
    fallback = TemplateDescriber().describe(pending, ctx, {}, attempt)
    for moment in pending:
        if verifier.check(moment, fallback[moment.id]):  # not an assert: it must hold under -O too
            raise RuntimeError("the template fallback must verify")
        accepted[moment.id] = (fallback[moment.id], "fallback")
    trace.append(
        TraceStep(
            step="describer",
            status="ok",
            attempt=attempt,
            detail=f"template fallback for {len(pending)}",
            executor=executor,
        )
    )


def _verified(
    moments: list[Moment], ctx: Context, describer: Describer, trace: list[TraceStep]
) -> tuple[dict[int, tuple[Description, str]], int]:
    verifier = Verifier(ctx)
    accepted: dict[int, tuple[Description, str]] = {}
    pending, feedback, attempt = moments, {}, 0
    while pending and attempt < MAX_ATTEMPTS:
        attempt += 1
        described = describe_step(describer, ctx, pending, feedback, attempt, trace)
        pending = verify_step(verifier, pending, described, feedback, accepted, attempt, trace)
    if pending:
        fallback_step(verifier, ctx, pending, attempt, accepted, trace)
    return accepted, attempt


def verified_descriptions(
    match: Match, preset: Preset, profile: Profile, describer: Describer
) -> dict[int, tuple[Description, str]]:
    """What the pipeline accepts for a window, by moment: the verified descriptions or the template fallback."""
    ctx = Context(match, profile.lang)
    moments = detect_moments(window_of(match, preset), profile.detail)
    accepted, _ = _verified(moments, ctx, describer, [])
    return accepted


def window_of(match: Match, preset: Preset) -> list:
    return [e for e in match.events if preset.from_s <= e.t <= preset.to_s]


def assemble_session(
    match: Match,
    preset: Preset,
    profile: Profile,
    ctx: Context,
    moments: list[Moment],
    accepted: dict[int, tuple[Description, str]],
    attempts: int,
    trace: list[TraceStep],
    executor: str | None = None,
) -> Session:
    """Timing and render: place the accepted descriptions into the silence and report what was checked."""
    window = window_of(match, preset)
    before = [e for e in match.events if e.t < preset.from_s]
    start_home, start_away = (before[-1].home_score, before[-1].away_score) if before else (0, 0)
    rate = min(profile.rate, CALM_RATE) if profile.calm else profile.rate

    candidates = [
        Candidate(m, accepted[m.id][0], accepted[m.id][1], pan_of(ctx.by_id[m.event_ids[-1]])) for m in moments
    ]
    cues, dropped = plan(candidates, preset.from_s, rate)
    trace.append(
        TraceStep(
            step="timing",
            status="ok",
            attempt=1,
            detail=f"{len(cues)} cues placed, {len(dropped)} dropped",
            executor=executor,
        )
    )

    duration_ms = (preset.to_s - preset.from_s) * 1000
    speech_ms = sum(c.end_ms - c.start_ms for c in cues)
    by_priority = {
        str(p): {
            "total": sum(1 for m in moments if m.priority == p),
            "scheduled": sum(1 for c in cues if c.priority == p),
        }
        for p in range(4)
    }
    report = Report(
        moments=len(moments),
        cues=len(cues),
        dropped=len(dropped),
        verified=sum(1 for s in accepted.values() if s[1] == "verified"),
        fallback=sum(1 for s in accepted.values() if s[1] == "fallback"),
        attempts=attempts,
        speech_ms=speech_ms,
        silence_ms=max(0, duration_ms - speech_ms),
        overlaps=sum(1 for a, b in itertools.pairwise(cues) if b.start_ms < a.end_ms),
        by_priority=by_priority,  # type: ignore[arg-type]
    )
    return Session(
        preset=preset.id,
        title=preset.title,
        lang=profile.lang,
        profile=profile,
        duration_ms=duration_ms,
        start_home_score=start_home,
        start_away_score=start_away,
        cues=cues,
        earcons=earcons(window, preset.from_s, profile.model_copy(update={"rate": rate})),
        dropped=dropped,
        track=track(window, preset.from_s),
        trace=trace,
        report=report,
    )


def build_session(match: Match, preset: Preset, profile: Profile, describer: Describer) -> Session:
    ctx = Context(match, profile.lang)
    trace: list[TraceStep] = []
    moments = detect_moments(window_of(match, preset), profile.detail)
    trace.append(TraceStep(step="moment_detector", status="ok", attempt=1, detail=f"{len(moments)} moments"))
    accepted, attempts = _verified(moments, ctx, describer, trace)
    return assemble_session(match, preset, profile, ctx, moments, accepted, attempts, trace)
