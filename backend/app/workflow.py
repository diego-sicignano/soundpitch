"""The pipeline as a Microsoft Agent Framework workflow (SPEC §12, D13).

    MomentDetector -> Describer -> Verifier -> TimingPlanner
                          ^           |  \\-> Fallback -> TimingPlanner
                          \\- retry --/

Each executor does one step of `app.pipeline` (the same functions the plain pipeline calls, so the two cannot
drift apart) and hands an immutable `Round` to the next one. The retry is a conditional edge, not a loop in
code. Only the `Describer` touches a model; every other executor is deterministic code, and the `Verifier`
checks every description whatever produced it (SPEC §5).

The framework is imported only when a session is built, so the plain pipeline and the tests never need it.
"""

import asyncio
from dataclasses import dataclass, replace
from typing import Any, Never

from app.contracts import Description, Match, Moment, Preset, Profile, Session, TraceStep
from app.describer import Context, Describer
from app.foundry import FoundryNotConfigured
from app.moments import detect_moments
from app.pipeline import (
    MAX_ATTEMPTS,
    assemble_session,
    describe_step,
    fallback_step,
    verify_step,
    window_of,
)
from app.verifier import Verifier

MISSING = "agent-framework-core is not installed: run pip install -r backend/requirements-agents.txt"


@dataclass(frozen=True, eq=False)
class Job:
    match: Match
    preset: Preset
    profile: Profile


@dataclass(frozen=True, eq=False)
class Round:
    """What passes between executors. Never changed after it is sent: an edge condition is evaluated when the
    message is delivered, so a message changed by its sender would send it down the wrong edge."""

    job: Job
    ctx: Context
    moments: tuple[Moment, ...]
    pending: tuple[Moment, ...]
    accepted: dict[int, tuple[Description, str]]
    feedback: dict[int, list[str]]
    described: dict[int, Description]
    attempt: int
    trace: tuple[TraceStep, ...]


def _build(describer: Describer) -> Any:
    try:
        from agent_framework import WorkflowBuilder, WorkflowContext, executor
    except ImportError as exc:
        raise FoundryNotConfigured(MISSING) from exc

    @executor(id="MomentDetector")
    async def moment_detector(job: Job, ctx: WorkflowContext[Round]) -> None:
        context = Context(job.match, job.profile.lang)
        moments = tuple(detect_moments(window_of(job.match, job.preset), job.profile.detail))
        step = TraceStep(
            step="moment_detector", status="ok", attempt=1, detail=f"{len(moments)} moments", executor="MomentDetector"
        )
        await ctx.send_message(Round(job, context, moments, moments, {}, {}, {}, 0, (step,)))

    @executor(id="Describer")
    async def describe(r: Round, ctx: WorkflowContext[Round]) -> None:
        attempt, trace = r.attempt + 1, list(r.trace)
        feedback = {k: list(v) for k, v in r.feedback.items()}
        # in a thread: a model call blocks, and the describer reads its own note on the thread that called it
        described = await asyncio.to_thread(
            describe_step, describer, r.ctx, list(r.pending), feedback, attempt, trace, "Describer"
        )
        await ctx.send_message(replace(r, attempt=attempt, described=described, feedback=feedback, trace=tuple(trace)))

    @executor(id="Verifier")
    async def verify(r: Round, ctx: WorkflowContext[Round]) -> None:
        trace, accepted = list(r.trace), dict(r.accepted)
        feedback = {k: list(v) for k, v in r.feedback.items()}
        failed = verify_step(
            Verifier(r.ctx), list(r.pending), r.described, feedback, accepted, r.attempt, trace, "Verifier"
        )
        await ctx.send_message(
            replace(r, pending=tuple(failed), accepted=accepted, feedback=feedback, described={}, trace=tuple(trace))
        )

    @executor(id="Fallback")
    async def fallback(r: Round, ctx: WorkflowContext[Round]) -> None:
        trace, accepted = list(r.trace), dict(r.accepted)
        fallback_step(Verifier(r.ctx), r.ctx, list(r.pending), r.attempt, accepted, trace, "Fallback")
        await ctx.send_message(replace(r, pending=(), accepted=accepted, trace=tuple(trace)))

    @executor(id="TimingPlanner")
    async def timing_planner(r: Round, ctx: WorkflowContext[Never, Session]) -> None:
        job = r.job
        session = assemble_session(
            job.match, job.preset, job.profile, r.ctx, list(r.moments), r.accepted, r.attempt, list(r.trace),
            "TimingPlanner",
        )  # fmt: skip
        await ctx.yield_output(session)

    return (
        WorkflowBuilder(start_executor=moment_detector, output_from=[timing_planner])
        .add_edge(moment_detector, describe, condition=lambda r: bool(r.pending))
        .add_edge(moment_detector, timing_planner, condition=lambda r: not r.pending)
        .add_edge(describe, verify)
        .add_edge(verify, describe, condition=lambda r: bool(r.pending) and r.attempt < MAX_ATTEMPTS)
        .add_edge(verify, fallback, condition=lambda r: bool(r.pending) and r.attempt >= MAX_ATTEMPTS)
        .add_edge(verify, timing_planner, condition=lambda r: not r.pending)
        .add_edge(fallback, timing_planner)
        .build()
    )


def build_session(match: Match, preset: Preset, profile: Profile, describer: Describer) -> Session:
    """The same signature and result as `app.pipeline.build_session`, built by the workflow."""
    flow = _build(describer)
    result = asyncio.run(flow.run(Job(match, preset, profile)))
    outputs = result.get_outputs()
    if len(outputs) != 1 or not isinstance(outputs[0], Session):
        raise RuntimeError("the workflow did not produce a session")
    return outputs[0]
