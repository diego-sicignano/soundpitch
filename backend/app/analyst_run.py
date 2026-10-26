"""Record the live Analyst agent's replies for every window and language (SPEC §20).

    python -m app.analyst_run --write ../docs/evidence/analyst-run.md

It spends model calls: 5 windows x 2 languages, at most 2 attempts each. Every attempt is one run of a
Microsoft Agent Framework `Agent` on Foundry (`FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, `az login`) whose tools
are the SoundPitch MCP server, started as a stdio subprocess in replay mode, so the agent sees exactly what
the judges' image serves. The usage ledger (D11) reserves each run's worst case before it starts. The points
are checked here as on every session; the replies go to `replay_data/analyst_replies.json` and the report
lists the tools each run called.
"""

import argparse
import asyncio
import datetime
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from app import analysis
from app.contracts import Profile
from app.foundry import FoundryNotConfigured, ledger_from_env, settings_from_env
from app.match_gen import SEED, generate_match
from app.pipeline import analysis_request, build_presets, build_session, describer_from_env
from app.usage import BudgetExceeded, UsageLedger

LANGS = ("en", "it")
ROUNDS = 3  # an agent run asks the model a few times: the tools first, then the points
RUN_INPUT_TOKENS = 10_000  # per round, under the ledger's 12,000-token cap for one request
RUN_OUTPUT_TOKENS = 1_000
RUN_TIMEOUT_S = 180.0


class PointReply(BaseModel):
    text: str
    source: str


class PointsReply(BaseModel):
    points: list[PointReply]


@dataclass
class Answer:
    raw: str
    tools: list[str]
    input_tokens: int | None = None
    output_tokens: int | None = None


Asker = Callable[[analysis.Request, int, list[str]], Answer]


def question(req: analysis.Request, feedback: list[str]) -> str:
    text = f"Window '{req.preset.id}' ({req.preset.title}). Call the tools with preset='{req.preset.id}' and lang='{req.lang}'."
    if feedback:
        text += " Your previous points were rejected: " + "; ".join(feedback) + ". Write points that state only what their line holds."
    return text


class AgentAsker:
    """One Agent Framework agent run on Foundry with the SoundPitch MCP server as its tools."""

    def __init__(self, endpoint: str, model: str):
        try:
            import agent_framework.foundry  # noqa: F401
        except ImportError as exc:
            raise FoundryNotConfigured("run pip install -r backend/requirements-agents.txt") from exc
        self.endpoint, self.model = endpoint, model

    def __call__(self, req: analysis.Request, attempt: int, feedback: list[str]) -> Answer:
        return asyncio.run(asyncio.wait_for(self._ask(req, feedback), RUN_TIMEOUT_S))

    async def _ask(self, req: analysis.Request, feedback: list[str]) -> Answer:
        from agent_framework import Agent, MCPStdioTool
        from agent_framework.foundry import FoundryChatClient
        from azure.identity.aio import DefaultAzureCredential

        language = "Italian" if req.lang == "it" else "English"
        server = MCPStdioTool(
            name="soundpitch",
            command=sys.executable,
            args=["-m", "app.mcp_server"],
            env=dict(os.environ, SOUNDPITCH_LLM="replay", SOUNDPITCH_ORCHESTRATOR="plain"),  # what the judges see
            load_prompts=False,
        )
        async with DefaultAzureCredential() as credential:
            client = FoundryChatClient(project_endpoint=self.endpoint, model=self.model, credential=credential)
            agent = Agent(client=client, instructions=analysis.INSTRUCTIONS.format(language=language), tools=[server])
            async with agent:
                response = await agent.run(
                    question(req, feedback), options={"response_format": PointsReply, "max_tokens": RUN_OUTPUT_TOKENS}
                )
        try:
            value = response.value
        except Exception:  # noqa: BLE001 - the SDK may raise when the text is not the schema; keep the text
            value = None
        raw = value.model_dump_json() if isinstance(value, PointsReply) else response.text
        tools = [c.name for m in response.messages for c in m.contents if getattr(c, "type", "") == "function_call"]
        usage = getattr(response, "usage_details", None) or {}
        return Answer(raw, tools, usage.get("input_token_count"), usage.get("output_token_count"))


@dataclass
class Row:
    preset: str
    lang: str
    attempts: int = 0
    asked: int = 0
    kept: int = 0
    rejected: int = 0
    tools: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _asked(asker: Asker, ledger: UsageLedger, req: analysis.Request, attempt: int, feedback: list[str]) -> Answer:
    """One agent run behind the ledger: every round's worst case is reserved first (BudgetExceeded stops the run
    before the agent starts); afterwards one reservation takes what the provider reported and the rest are freed.
    A run that fails keeps its worst case, because it may have been billed."""
    held = []
    try:
        for _ in range(ROUNDS):
            held.append(ledger.reserve(RUN_INPUT_TOKENS, RUN_OUTPUT_TOKENS))
    except BaseException:
        for reservation in held:
            ledger.release(reservation)
        raise
    answer = asker(req, attempt, feedback)
    ledger.settle(held[0], answer.input_tokens or RUN_INPUT_TOKENS * ROUNDS, answer.output_tokens or RUN_OUTPUT_TOKENS * ROUNDS)
    for reservation in held[1:]:
        ledger.release(reservation)
    return answer


def record(asker: Asker, ledger: UsageLedger, replies: dict[str, str]) -> list[Row]:
    """Ask, for every window and language, the questions the judges' sessions will ask; keep every reply."""
    match = generate_match(SEED)
    rows = []
    for preset in build_presets(match):
        for lang in LANGS:
            session = build_session(match, preset, Profile(lang=lang), describer_from_env(), analysis.CodeAnalyst())
            req, row, kept, feedback = analysis_request(match, preset, session), Row(preset.id, lang), [], []
            for attempt in range(1, analysis.MAX_ATTEMPTS + 1):
                row.attempts = attempt
                key = analysis.reply_key(req, attempt, feedback)
                if key not in replies:
                    answer = _asked(asker, ledger, req, attempt, feedback)
                    replies[key], row.asked, row.tools = answer.raw, row.asked + 1, row.tools + answer.tools
                issues = analysis.check_step(req, analysis.parse_points(replies[key]) or [], kept, attempt, [])
                row.rejected, row.issues = row.rejected + len(issues), row.issues + issues
                if not issues:
                    break
                feedback = issues
            row.kept = len(kept)
            rows.append(row)
    return rows


def to_markdown(rows: list[Row], model: str, today: datetime.date) -> str:
    lines = [
        "# Analyst runs",
        "",
        (
            f"Recorded {today.isoformat()} with `{model}` on Microsoft Foundry, as a Microsoft Agent Framework agent whose "
            "tools are the SoundPitch MCP server (`python -m app.analyst_run`). Every point is checked against the line it "
            "cites (SPEC §20); the rejected ones are listed with the reason."
        ),
        "",
        "| Window | Language | Attempts | Agent runs | Points kept | Points rejected | Tools called |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        tools = ", ".join(dict.fromkeys(r.tools)) or "stored"
        lines.append(f"| {r.preset} | {r.lang} | {r.attempts} | {r.asked} | {r.kept} | {r.rejected} | {tools} |")
    issues = [f"- {r.preset} {r.lang}: {issue}" for r in rows for issue in r.issues]
    lines += ["", "## Rejected points", "", *(issues or ["None."])]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record the live Analyst agent's replies.")
    parser.add_argument("--write", type=Path, help="write the report here (docs/evidence/analyst-run.md)")
    args = parser.parse_args(argv)
    os.environ["SOUNDPITCH_LLM"] = "replay"  # the sessions the agent analyses are the judges' sessions
    try:
        endpoint, model = settings_from_env()
        asker = AgentAsker(endpoint, model)
    except FoundryNotConfigured as exc:
        print(f"not configured: {exc}", file=sys.stderr)
        return 2
    replies = dict(analysis.load_store().replies)
    try:
        rows = record(asker, ledger_from_env(), replies)
    except BudgetExceeded as exc:
        print(f"stopped by the usage ledger: {exc}", file=sys.stderr)
        rows = []
    data = {"version": analysis.VERSION, "model": model, "recorded": datetime.date.today().isoformat(), "replies": replies}
    analysis.STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    report = to_markdown(rows, model, datetime.date.today())
    if args.write:
        args.write.write_text(report, encoding="utf-8")
    print(report)
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
