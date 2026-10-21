"""Explain with a model on Microsoft Foundry (SPEC §11).

The model only chooses words. `FoundryDescriber` builds a prompt from the facts the code derives
(`describer.facts`), asks an `LlmClient`, and turns the reply into `Description`s whose refs are the
code's, not the model's. It does not verify, retry or fall back: the pipeline does, with the same
verifier as for every other describer, so a reply is never trusted for being valid JSON.

Nothing here imports the Foundry SDK except `AgentFrameworkClient`, and only when it is created.
"""

import asyncio
import concurrent.futures
import hashlib
import json
import logging
import math
import os
import re
import threading
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ValidationError

from app.contracts import Description, Moment
from app.describer import LEX, Context, TemplateDescriber, facts
from app.usage import (
    MAX_EUR_PER_MONTH,
    BudgetExceeded,
    LedgerUnavailable,
    Reservation,
    UsageLedger,
    estimate_input_tokens,
)
from app.verifier import (
    FAMILY,
    PHRASES,
    REQUIRED_FULL,
    REQUIRED_SHORT,
    _marker,
    position_contexts,
    vocabulary,
)

log = logging.getLogger("soundpitch.usage")

MAX_BATCH = 20
TIMEOUT_S = 20.0
MAX_OUTPUT_TOKENS = 1000  # 20 moments of speech are about 600 tokens
MAX_REPLY_CHARS = 20_000  # 1,000 tokens are about 4,000 characters
MAX_IN_FLIGHT = 2
DEFAULT_CALLS_PER_MINUTE = 2
DEFAULT_CALLS_PER_DAY = 20
DEFAULT_TOKENS_PER_DAY = 120_000
DEFAULT_EUR_PER_MONTH = 2.0
DEFAULT_USAGE_DB = Path(__file__).resolve().parents[1] / "data" / "usage.sqlite"  # git-ignored
LANGUAGES = {"en": "English", "it": "Italian"}
BUDGET_NOTE = "llm budget exhausted: templates"
EDGE_NAMES = {"·": "<edge>", "qqp": "<player>", "qqteam": "<team>", "qqother": "<other>"}


class FoundryNotConfigured(RuntimeError):
    """A setting or the optional package is missing; the message names it."""


@dataclass(frozen=True)
class Reply:
    """The model's text and the usage the provider reported (None when it did not report any)."""

    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LlmClient(Protocol):
    def complete(self, system: str, user: str) -> "str | Reply":
        """Send one request and return the model's text (JSON). May raise: that is a failed attempt."""
        ...


class Wording(BaseModel):
    moment_id: int
    full: str
    short: str


class Wordings(BaseModel):
    items: list[Wording]


# ---- the prompt ------------------------------------------------------------------------------------

SYSTEM = """You write audio description of a football match for blind listeners, one moment at a time.
The match is synthetic. Reply with JSON only, no other text, in {language}:
{"items": [{"moment_id": 1, "full": "...", "short": "..."}, {"moment_id": 2, "full": "...", "short": "..."}]}
The list must hold one item for EVERY moment you are given, in the same order: "items_expected" says how many.
Stopping after the first moment is an error.
Present tense, factual, no opinions or praise.

A program checks every sentence against the match events. It rejects a sentence that breaks one of
these rules and then speaks a fixed sentence instead, so follow them exactly:
1. Use only the words in the moment's "words", the "player" and "team" names given for it, and its "phrases".
2. Copy every phrase exactly, character for character. Never split, reorder or change one.
3. A name or a phrase may stand only between the neighbours listed in "positions" for it
   ("<edge>" is the start or end of the sentence or a neighbouring phrase; "<player>" and "<team>" are names).
   Do not use a name or a phrase that "positions" does not list.
4. Every item of "required" must appear in "full"; "required_short" must appear in "short".
5. "full" has at most 45 words. "short" has at most 15 words and is never longer than "full".
6. Use only letters, spaces and . , ! : ; ' - . No digits outside a phrase, no symbols, emoji, quotes or brackets.
7. "examples" show accepted sentences made of the same facts. Follow their order; vary the words only
   within these rules. Never mention anything that is not given for the moment.
If a moment has "issues", your last sentence broke those rules: fix exactly that."""


@cache
def _used(lang: str, key: str) -> frozenset[str]:
    """The fields (names and phrases) that the templates of this kind of event use."""
    found: set[str] = set()
    for k in FAMILY.get(key, (key,)):
        for templates in LEX[lang]["t"][k]:
            for template in templates:
                if "{home} {hs}, {away} {as_}" in template:
                    found.add("score")
                if LEX[lang]["minute"] + " {m}" in template:
                    found.add("minute")
                found.update(re.findall(r"\{(\w+)\}", template))
    return frozenset(found)


def _moment_block(moment: Moment, ctx: Context, issues: list[str] | None) -> dict:
    f = facts(moment, ctx)
    used = _used(ctx.lang, f.key)
    block: dict = {"moment_id": moment.id, "kind": f.key}
    if "p" in used and "p" in f.fields:
        block["player"] = f.fields["p"]
    if "team" in used and "team" in f.fields:
        block["team"] = f.fields["team"]
    phrases = {name: str(f.fields[name]) for name in PHRASES if name in used and name in f.fields}
    block["phrases"] = phrases
    block["words"] = sorted(vocabulary(ctx.lang, f.key))
    before, after = position_contexts(ctx.lang, f.key)
    markers = {"qqp": "player", "qqteam": "team", **{_marker(n): n for n in phrases}}
    block["positions"] = {
        label: {
            "before": sorted(EDGE_NAMES.get(w, w) for w in before[marker]),
            "after": sorted(EDGE_NAMES.get(w, w) for w in after[marker]),
        }
        for marker, label in markers.items()
        if marker in before and (before[marker] or after[marker])
    }
    names = {"p": "player", "team": "team", "score": "score"}
    block["required"] = [names[n] for n in REQUIRED_FULL.get(f.key, ())]
    block["required_short"] = [names[n] for n in REQUIRED_SHORT.get(f.key, ())]
    block["examples"] = []
    for key in FAMILY.get(f.key, (f.key,)):
        for full, short in LEX[ctx.lang]["t"][key]:
            try:
                block["examples"].append({"full": full.format(**f.fields), "short": short.format(**f.fields)})
            except KeyError:  # an assist template for a goal without an assist
                continue
    if issues:
        block["issues"] = list(issues)
    return block


def build_prompt(moments: list[Moment], ctx: Context, feedback: dict[int, list[str]]) -> tuple[str, str]:
    """The system and the user message for these moments: the facts of each moment and nothing else."""
    language = LANGUAGES[ctx.lang]
    payload = {
        "language": language,
        "items_expected": len(moments),
        "moments": [_moment_block(m, ctx, feedback.get(m.id)) for m in moments],
    }
    return SYSTEM.replace("{language}", language), json.dumps(payload, ensure_ascii=False)


def parse_reply(text: str, asked: set[int]) -> dict[int, Wording]:
    """The usable items of a reply: unknown moments, duplicates and malformed items are dropped."""
    body = text.strip()
    if body.startswith("```") and body.endswith("```") and len(body) >= 6:
        body = body[3:-3].strip().removeprefix("json").strip()
    data = json.loads(body)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise TypeError("the reply has no list of items")
    found: dict[int, Wording] = {}
    for raw in items:
        try:
            item = Wording.model_validate(raw)
        except ValidationError:
            continue
        if item.moment_id in asked and item.moment_id not in found:
            found[item.moment_id] = item
    if not found:
        raise ValueError("the reply has no usable item")
    return found


def chunk_key(chunk: list[Moment], ctx: Context, feedback: dict[int, list[str]], attempt: int) -> tuple:
    """What a request to the model is about: the match, the language, the attempt, the moments and the issues."""
    return (
        ctx.match.seed,
        ctx.lang,
        attempt,
        tuple((m.id, m.t, m.kind, tuple(m.event_ids)) for m in chunk),
        tuple((m.id, tuple(feedback.get(m.id, ()))) for m in chunk),
    )


def reply_key(key: tuple, system: str) -> str:
    """The key under which a reply is stored: a new prompt is a new question."""
    return hashlib.sha256(repr((key, system)).encode()).hexdigest()


def descriptions_from(found: dict[int, Wording], chunk: list[Moment], ctx: Context) -> dict[int, Description]:
    """The model's words with the code's refs: a reply never certifies its own facts."""
    return {
        m.id: Description(
            moment_id=m.id,
            lang=ctx.lang,
            full=found[m.id].full,
            short=found[m.id].short,
            refs=facts(m, ctx).refs,
        )
        for m in chunk
        if m.id in found
    }


# ---- the describer ---------------------------------------------------------------------------------


class FoundryDescriber:
    def __init__(
        self,
        client: LlmClient,
        ledger: UsageLedger,
        *,
        timeout_s: float = TIMEOUT_S,
    ):
        self.client = client
        self.ledger = ledger
        self.timeout_s = timeout_s
        self._lock = threading.Lock()
        self._local = threading.local()
        self._flights: dict[tuple, list] = {}
        self._slots = threading.BoundedSemaphore(MAX_IN_FLIGHT)
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_IN_FLIGHT, thread_name_prefix="foundry"
        )

    @property
    def note(self) -> str:
        """What happened that the trace should say (per thread, valid after `describe`)."""
        return getattr(self._local, "note", "")

    def describe(
        self, moments: list[Moment], ctx: Context, feedback: dict[int, list[str]], attempt: int
    ) -> dict[int, Description]:
        self._local.note = ""
        described: dict[int, Description] = {}
        for start in range(0, len(moments), MAX_BATCH):
            described.update(self._chunk(moments[start : start + MAX_BATCH], ctx, feedback, attempt))
        return described

    def _chunk(self, chunk, ctx, feedback, attempt) -> dict[int, Description]:
        key = chunk_key(chunk, ctx, feedback, attempt)
        with self._lock:  # single flight: identical requests wait for the one call in progress
            flight = self._flights.setdefault(key, [threading.Lock(), 0])
            flight[1] += 1
        try:
            with flight[0]:
                return self._answer(key, chunk, ctx, feedback, attempt)
        finally:
            with self._lock:
                flight[1] -= 1
                if flight[1] == 0:
                    del self._flights[key]

    def _answer(self, key, chunk, ctx, feedback, attempt) -> dict[int, Description]:
        asked = {m.id for m in chunk}
        system, user = build_prompt(chunk, ctx, feedback)
        stored = reply_key(key, system)
        raw = self.ledger.cache_get(stored)
        if raw is None:
            if not self._slots.acquire(blocking=False):  # earlier calls still hang: fail fast, spend nothing
                raise RuntimeError("the model is busy: earlier calls have not finished")
            try:
                held = self.ledger.reserve(estimate_input_tokens(system, user), MAX_OUTPUT_TOKENS)
            except (BudgetExceeded, LedgerUnavailable) as exc:  # nothing is sent: the templates speak
                self._slots.release()
                reason = "ledger unavailable" if isinstance(exc, LedgerUnavailable) else str(exc)
                self._local.note = f"{BUDGET_NOTE} ({reason})"
                return TemplateDescriber().describe(chunk, ctx, feedback, attempt)
            except BaseException:
                self._slots.release()
                raise
            raw = self._ask(system, user, held)  # the slot is released when the call ends
            found = parse_reply(raw, asked)  # an unusable reply is not kept: the next request asks again
            self.ledger.cache_put(stored, raw)
        else:
            found = parse_reply(raw, asked)
        return descriptions_from(found, chunk, ctx)

    def _ask(self, system: str, user: str, held: Reservation) -> str:
        """Send one request. The reservation is settled by the worker when the call returns, even if the
        caller gave up; a call that raises keeps its worst case, because it may have been billed."""

        def call() -> str:
            try:
                answer = self.client.complete(system, user)
                reply = answer if isinstance(answer, Reply) else Reply(answer if isinstance(answer, str) else "")
                self._settle(held, reply, system, user)
                return reply.text
            finally:
                self._slots.release()

        try:
            future = self._pool.submit(call)
        except BaseException:
            self._slots.release()
            self._release(held)  # never sent
            raise
        try:
            raw = future.result(timeout=self.timeout_s)
        except concurrent.futures.TimeoutError:
            if future.cancel():  # it had not started: nothing was sent
                self._slots.release()
                self._release(held)
            raise TimeoutError(f"the model call took more than {self.timeout_s:g} s") from None
        if not isinstance(raw, str) or len(raw) > MAX_REPLY_CHARS:
            raise ValueError("the reply is too long or is not text")
        return raw

    def _settle(self, held: Reservation, reply: Reply, system: str, user: str) -> None:
        """Replace the worst case with what the provider reported; without a report, with an estimate."""
        used_in = reply.input_tokens if reply.input_tokens is not None else estimate_input_tokens(system, user)
        used_out = reply.output_tokens if reply.output_tokens is not None else estimate_input_tokens(reply.text)
        try:
            self.ledger.settle(held, used_in, used_out)  # never clamped: a higher report must be counted
        except LedgerUnavailable:
            pass  # logged by the ledger; the worst case stays held

    def _release(self, held: Reservation) -> None:
        try:
            self.ledger.release(held)
        except LedgerUnavailable:
            pass  # logged by the ledger; the worst case stays held


# ---- the Microsoft Agent Framework client ------------------------------------------------------------


class AgentFrameworkClient:
    """`FoundryChatClient` on one long-lived event loop: the SDK client is async and must not be shared
    across threads or loops, and one loop lets the connection and the token be reused."""

    def __init__(self, endpoint: str, model: str, timeout_s: float = TIMEOUT_S):
        try:
            import agent_framework.foundry  # noqa: F401
        except ImportError as exc:
            raise FoundryNotConfigured(
                "agent-framework-foundry is not installed: run pip install -r backend/requirements-agents.txt"
            ) from exc
        self.endpoint, self.model, self.timeout_s = endpoint, model, timeout_s
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client = None
        self._guard = threading.Lock()

    def _running_loop(self) -> asyncio.AbstractEventLoop:
        with self._guard:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                threading.Thread(target=loop.run_forever, name="foundry-loop", daemon=True).start()
                self._loop = loop
            return self._loop

    def complete(self, system: str, user: str) -> Reply:
        future = asyncio.run_coroutine_threadsafe(self._complete(system, user), self._running_loop())
        try:
            return future.result(timeout=self.timeout_s + 5)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"the model call took more than {self.timeout_s:g} s") from None

    async def _complete(self, system: str, user: str) -> Reply:
        from agent_framework import Message

        if self._client is None:
            from agent_framework.foundry import FoundryChatClient
            from azure.identity.aio import DefaultAzureCredential

            self._client = FoundryChatClient(
                project_endpoint=self.endpoint, model=self.model, credential=DefaultAzureCredential()
            )
        response = await asyncio.wait_for(
            self._client.get_response(
                [Message(role="user", contents=[user])],
                options={"instructions": system, "response_format": Wordings, "max_tokens": MAX_OUTPUT_TOKENS},
            ),
            self.timeout_s,
        )
        try:
            value = response.value
        except Exception:  # noqa: BLE001 - the SDK may raise when the text is not the schema; read the text
            value = None
        text = value.model_dump_json() if isinstance(value, Wordings) else response.text
        usage = getattr(response, "usage_details", None) or {}
        return Reply(text, _count(usage, "input_token_count"), _count(usage, "output_token_count"))


# ---- configuration -----------------------------------------------------------------------------------

_SHARED: FoundryDescriber | None = None
_SHARED_LOCK = threading.Lock()


def _count(usage, name: str) -> int | None:
    """A token count the provider reported, or None if it is missing or not a sane whole number."""
    try:
        value = usage.get(name) if hasattr(usage, "get") else getattr(usage, name, None)
    except Exception:  # noqa: BLE001 - a usage object that cannot be read is a report that is missing
        return None
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _whole_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise FoundryNotConfigured(f"{name} must be a whole number of at least 1")
    return value


def _euros_from_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value <= 0:
        raise FoundryNotConfigured(f"{name} must be an amount of euros above 0")
    if value > MAX_EUR_PER_MONTH:
        raise FoundryNotConfigured(
            f"{name} cannot be above {MAX_EUR_PER_MONTH:g}: the Azure budget (5 EUR) only alerts, so the ceiling stays well below it"
        )
    return value


def ledger_from_env() -> UsageLedger:
    """The ledger with the strict defaults. The environment may change the calls and tokens (the recording run
    raises them on purpose); only the month is capped for good: it can never be set above MAX_EUR_PER_MONTH."""
    return UsageLedger(
        os.environ.get("SOUNDPITCH_USAGE_DB") or DEFAULT_USAGE_DB,
        per_minute=_whole_from_env("SOUNDPITCH_LLM_CALLS_PER_MINUTE", DEFAULT_CALLS_PER_MINUTE),
        per_day=_whole_from_env("SOUNDPITCH_LLM_CALLS_PER_DAY", DEFAULT_CALLS_PER_DAY),
        tokens_per_day=_whole_from_env("SOUNDPITCH_LLM_TOKENS_PER_DAY", DEFAULT_TOKENS_PER_DAY),
        eur_per_month=_euros_from_env("SOUNDPITCH_LLM_EUR_PER_MONTH", DEFAULT_EUR_PER_MONTH),
    )


def settings_from_env() -> tuple[str, str]:
    """(endpoint, model); the error names what is missing. Values are never printed."""
    for name in ("FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_MODEL"):
        if not os.environ.get(name):
            raise FoundryNotConfigured(f"{name} is not set (SOUNDPITCH_LLM=foundry needs it, see backend/.env.example)")
    return os.environ["FOUNDRY_PROJECT_ENDPOINT"], os.environ["FOUNDRY_MODEL"]


def shared_describer() -> FoundryDescriber:
    """One describer per process: the in-flight guard and the single flight are only worth anything if shared."""
    global _SHARED
    with _SHARED_LOCK:
        if _SHARED is None:
            endpoint, model = settings_from_env()
            ledger = ledger_from_env()
            _SHARED = FoundryDescriber(AgentFrameworkClient(endpoint, model), ledger)
        return _SHARED


def reset_shared() -> None:
    global _SHARED
    with _SHARED_LOCK:
        _SHARED = None
