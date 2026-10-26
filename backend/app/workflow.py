"""The pipeline as a Microsoft Agent Framework workflow (SPEC §12, D13).

    MomentDetector -> Describer -> Verifier -> TimingPlanner -> Analyst -> AnalysisChecker (one retry to Analyst)
                          ^           |  \\-> Fallback -> TimingPlanner
                          \\- retry --/

Each executor does one step of `app.pipeline` (the same functions the plain pipeline calls, so the two cannot
drift apart) and hands an immutable `Round` to the next one. The retry is a conditional edge, not a loop in
code. Two executors are agents that may use a model, the `Describer` and the `Analyst` (SPEC §20); the others are
deterministic code: the `Verifier` checks every description and the `AnalysisChecker` every point, whatever
produced it (SPEC §5).

The framework is imported only when a session is built, so the plain pipeline and the tests never need it.
"""

import asyncio
from dataclasses import dataclass, replace
from typing import Any

from app import analysis
from app.contracts import (
    AnalysisPoint,
    Description,
    Match,
    Moment,
    Preset,
    Profile,
    Session,
    TraceStep,
)
from app.describer import Context, Describer
from app.foundry import FoundryNotConfigured
from app.moments import detect_moments, focus_of
from app.pipeline import (
    MAX_ATTEMPTS,
    analysis_request,
    analyst_from_env,
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


@dataclass(frozen=True, eq=False)
class AnalysisRound:
    """What passes between the Analyst and the AnalysisChecker; never changed after it is sent."""

    session: Session
    request: analysis.Request
    kept: tuple[AnalysisPoint, ...]
    proposed: tuple[analysis.Proposed, ...]
    feedback: tuple[str, ...]
    rejected: int
    attempt: int
    trace: tuple[TraceStep, ...]


def _build(describer: Describer, analyst: analysis.Analyst) -> Any:
    try:
        from agent_framework import WorkflowBuilder, WorkflowContext, executor
    except ImportError as exc:
        raise FoundryNotConfigured(MISSING) from exc

    @executor(id="MomentDetector")
    async def moment_detector(job: Job, ctx: WorkflowContext[Round]) -> None:
        context = Context(job.match, job.profile.lang)
        moments = tuple(detect_moments(window_of(job.match, job.preset), job.profile.detail, focus_of(job.profile)))
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
    async def timing_planner(r: Round, ctx: WorkflowContext[AnalysisRound]) -> None:
        job = r.job
        session = assemble_session(
            job.match, job.preset, job.profile, r.ctx, list(r.moments), r.accepted, r.attempt, list(r.trace),
            "TimingPlanner",
        )  # fmt: skip
        request = analysis_request(job.match, job.preset, session)
        await ctx.send_message(AnalysisRound(session, request, (), (), (), 0, 0, tuple(session.trace)))

    @executor(id="Analyst")
    async def analyst_step(r: AnalysisRound, ctx: WorkflowContext[AnalysisRound]) -> None:
        attempt, trace = r.attempt + 1, list(r.trace)
        proposed = await asyncio.to_thread(
            analysis.propose_step, analyst, r.request, attempt, list(r.feedback), trace, "Analyst"
        )
        await ctx.send_message(replace(r, attempt=attempt, proposed=tuple(proposed), trace=tuple(trace)))

    @executor(id="AnalysisChecker")
    async def analysis_checker(r: AnalysisRound, ctx: WorkflowContext[AnalysisRound, Session]) -> None:
        trace, kept = list(r.trace), list(r.kept)
        issues = analysis.check_step(r.request, list(r.proposed), kept, r.attempt, trace, "AnalysisChecker")
        rejected = r.rejected + len(issues)
        if issues and r.attempt < analysis.MAX_ATTEMPTS:  # the retry edge carries the issues back
            await ctx.send_message(replace(r, kept=tuple(kept), feedback=tuple(issues), rejected=rejected, trace=tuple(trace)))
            return
        result = analysis.finish(r.request, analyst.by, kept, rejected, r.attempt)
        await ctx.yield_output(r.session.model_copy(update={"analysis": result, "trace": trace}))

    return (
        WorkflowBuilder(start_executor=moment_detector, output_from=[analysis_checker])
        .add_edge(moment_detector, describe, condition=lambda r: bool(r.pending))
        .add_edge(moment_detector, timing_planner, condition=lambda r: not r.pending)
        .add_edge(describe, verify)
        .add_edge(verify, describe, condition=lambda r: bool(r.pending) and r.attempt < MAX_ATTEMPTS)
        .add_edge(verify, fallback, condition=lambda r: bool(r.pending) and r.attempt >= MAX_ATTEMPTS)
        .add_edge(verify, timing_planner, condition=lambda r: not r.pending)
        .add_edge(fallback, timing_planner)
        .add_edge(timing_planner, analyst_step)
        .add_edge(analyst_step, analysis_checker)
        .add_edge(analysis_checker, analyst_step)
        .build()
    )


def build_session(
    match: Match, preset: Preset, profile: Profile, describer: Describer, analyst: analysis.Analyst | None = None
) -> Session:
    """The same signature and result as `app.pipeline.build_session`, built by the workflow."""
    flow = _build(describer, analyst or analyst_from_env())
    result = asyncio.run(flow.run(Job(match, preset, profile)))
    outputs = result.get_outputs()
    if len(outputs) != 1 or not isinstance(outputs[0], Session):
        raise RuntimeError("the workflow did not produce a session")
    return outputs[0]
