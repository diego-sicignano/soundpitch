"""Replay of recorded Foundry replies: the judges' demo needs no live model (SPEC §11, D12).

`ReplayDescriber` answers a request with the reply a Foundry model gave to the same request earlier,
read from a JSON file shipped with the code. It makes no network call and spends nothing. It does not
verify anything itself: like every describer it is checked by the pipeline's verifier on every
session, so a recorded reply that is stale, hand-edited or hostile can only end in the template fallback.
A request with no recorded reply (a changed prompt, a new window, a retry with new feedback) is described by
the templates and the trace says so.
"""

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import get_args

from app.contracts import Description, Detail, Lang, Moment
from app.describer import Context, TemplateDescriber
from app.foundry import (
    MAX_BATCH,
    MAX_REPLY_CHARS,
    build_prompt,
    chunk_key,
    descriptions_from,
    parse_reply,
    reply_key,
)
from app.match_gen import SEED, generate_match
from app.moments import detect_moments
from app.pipeline import build_presets

log = logging.getLogger("soundpitch.replay")

STORE_PATH = Path(__file__).resolve().parent / "replay_data" / "foundry_replies.json"
VERSION = 1
NOTE_REPLAYED = "recorded Foundry reply"
NOTE_MISSING = "no recorded reply: templates"
_KEY = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class ReplayStore:
    replies: dict[str, str] = field(default_factory=dict)
    model: str = ""
    recorded: str = ""


def load_store(path: Path | str = STORE_PATH) -> ReplayStore:
    """The recorded replies. A missing or invalid file is an empty store: the templates speak, nothing breaks."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        replies = data["replies"]
        valid = (
            data["version"] == VERSION
            and isinstance(replies, dict)
            and all(_KEY.fullmatch(k) and isinstance(v, str) and len(v) <= MAX_REPLY_CHARS for k, v in replies.items())
        )
        if not valid:
            raise ValueError("unexpected structure")
        return ReplayStore(dict(replies), str(data.get("model", "")), str(data.get("recorded", "")))
    except FileNotFoundError:
        log.warning("no recorded replies at %s: the replay mode speaks with templates", Path(path).name)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.error("the recorded replies could not be read (%s): the replay mode speaks with templates", type(exc).__name__)
    return ReplayStore()


class ReplayDescriber:
    def __init__(self, store: ReplayStore):
        self.store = store
        self._local = threading.local()

    @property
    def note(self) -> str:
        """What the trace should say about the last `describe` on this thread."""
        return getattr(self._local, "note", "")

    def describe(
        self, moments: list[Moment], ctx: Context, feedback: dict[int, list[str]], attempt: int
    ) -> dict[int, Description]:
        described: dict[int, Description] = {}
        missing = 0
        for start in range(0, len(moments), MAX_BATCH):
            chunk = moments[start : start + MAX_BATCH]
            found = self._recorded(chunk, ctx, feedback, attempt)
            if found is None:
                missing += len(chunk)
                described.update(TemplateDescriber().describe(chunk, ctx, feedback, attempt))
            else:
                described.update(descriptions_from(found, chunk, ctx))
        self._local.note = f"{missing} moments: {NOTE_MISSING}" if missing else NOTE_REPLAYED
        return described

    def _recorded(self, chunk, ctx, feedback, attempt):
        system, _ = build_prompt(chunk, ctx, feedback)
        raw = self.store.replies.get(reply_key(chunk_key(chunk, ctx, feedback, attempt), system))
        if raw is None:
            return None
        try:
            return parse_reply(raw, {m.id for m in chunk})
        except (ValueError, TypeError):  # json.JSONDecodeError is a ValueError
            return None


_SHARED: ReplayDescriber | None = None
_SHARED_LOCK = threading.Lock()


def shared_replay() -> ReplayDescriber:
    global _SHARED
    with _SHARED_LOCK:
        if _SHARED is None:
            _SHARED = ReplayDescriber(load_store(STORE_PATH))
        return _SHARED


def reset_shared() -> None:
    global _SHARED
    with _SHARED_LOCK:
        _SHARED = None


def coverage(store: ReplayStore) -> tuple[int, int]:
    """(requests with a recorded reply, requests) over every preset, detail level and language, first attempt."""
    match = generate_match(SEED)
    hit = total = 0
    for preset in build_presets(match):
        window = [e for e in match.events if preset.from_s <= e.t <= preset.to_s]
        for detail in get_args(Detail):
            moments = detect_moments(window, detail)
            for lang in get_args(Lang):
                ctx = Context(match, lang)
                for start in range(0, len(moments), MAX_BATCH):
                    chunk = moments[start : start + MAX_BATCH]
                    system, _ = build_prompt(chunk, ctx, {})
                    total += 1
                    hit += reply_key(chunk_key(chunk, ctx, {}, 1), system) in store.replies
    return hit, total
