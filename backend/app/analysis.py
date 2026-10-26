"""Analyse: the Analyst agent's studio points, each checked against the one line it cites (SPEC §20).

An analyst proposes points; `check_point` rejects any point whose names or numbers are not in the line it
cites; a rejected point earns one more attempt with the issues; when no point passes, code writes them.
Only the live Analyst (`app.analyst_run`) talks to a model; here the analysts are code, a deliberately
flawed test analyst, and the recorded replies of the live one.
"""

import hashlib
import json
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app import stats
from app.contracts import Analysis, AnalysisPoint, Cue, Lang, Match, Preset, Recap, TraceStep

log = logging.getLogger("soundpitch.analysis")

MAX_ATTEMPTS = 2
MAX_POINTS = 4
MAX_WORDS, MAX_CHARS = 40, 300
VERSION = 1
STORE_PATH = Path(__file__).resolve().parent / "replay_data" / "analyst_replies.json"
INSTRUCTIONS = """You are the studio analyst for an audio-described football match (synthetic data).
Use the tools: get_recap for the result, the goals and the pressure before each goal; get_commentary for
the described moments; get_stats for the numbers at any minute. Then write 3 or 4 short points (at most 35
words each) on what decided the window: who pressed, how the goals came, what the numbers say.
Each point cites exactly one source: "recap:N" (line N of get_recap, counting from 1) or "stats:M" (get_stats
at minute M); the commentary is context only, never a source. Every name, number and minute in a point must
appear in the line it cites: no other names, no other numbers, no symbols other than . , ! : ; ' - % ( ).
Write in {language}. Reply only with JSON: {{"points": [{{"text": "...", "source": "recap:2"}}]}}."""
WORD = re.compile(r"[\w']+")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
ALLOWED = re.compile(r"[\w\s.,!:;'\-%()]+")
PRESSURE = re.compile(r"\b(press|domin|predomin|control)", re.IGNORECASE)  # pressing, dominated, controllo, ...


@dataclass(frozen=True)
class Proposed:
    """A point as an analyst wrote it, before any check: the source may not even exist."""

    text: str
    source: str


@dataclass(frozen=True)
class Request:
    """What the Analyst is asked about: one built session of one window (its cues are context, not sources)."""

    match: Match
    preset: Preset
    lang: Lang
    recap: Recap
    cues: list[Cue]


class Analyst(Protocol):
    by: str  # "model" or "code"

    def propose(self, req: Request, attempt: int, feedback: list[str]) -> list[Proposed] | None: ...


class Sources:
    """The lines a point may cite, and the names that count as names."""

    def __init__(self, req: Request):
        self.req = req
        teams = (req.match.home, req.match.away)
        self.names = {t.short.lower() for t in teams} | {p.name.lower() for t in teams for p in t.players}

    def text(self, ref: str) -> str | None:
        kind, _, number = ref.partition(":")
        if not number.isdigit():
            return None
        n = int(number)
        if kind == "recap":
            return self.req.recap.lines[n - 1] if 1 <= n <= len(self.req.recap.lines) else None
        if kind == "stats" and 1 <= n <= 90:
            home, away = stats.count([e for e in self.req.match.events if e.minute <= n])
            return f"Minute {n}. " + " ".join(
                f"{team.short}: possession {s.possession}%, last five minutes {s.recent_possession}%, passes completed "
                f"{s.passes_completed} of {s.passes}, pass accuracy {s.pass_accuracy}%, average pass {s.avg_pass_m} m, "
                f"shots {s.shots}, on target {s.shots_on_target}, balls won {s.ball_won}."
                for team, s in ((self.req.match.home, home), (self.req.match.away, away))
            )
        return None


def check_point(point: Proposed, sources: Sources) -> list[str]:
    """Why a point may not be said; empty when every name and number in it is in the line it cites (SPEC §20)."""
    line = sources.text(point.source)
    if line is None:
        return [f"{point.source} is no source: cite recap:N or stats:M"]
    found = []
    if len(point.text) > MAX_CHARS or len(point.text.split()) > MAX_WORDS:
        found.append(f"the point is too long (at most {MAX_WORDS} words)")
    if not ALLOWED.fullmatch(point.text):
        found.append("a character other than letters, digits and . , ! : ; ' - % ( )")
    words, line_words = set(WORD.findall(point.text.lower())), set(WORD.findall(line.lower()))
    names = sorted(words & sources.names)
    found += [f"{name.title()} is not in {point.source}" for name in names if name not in line_words]
    numbers, line_numbers = NUMBER.findall(point.text), set(NUMBER.findall(line))
    found += [f"{n} is not in {point.source}" for n in dict.fromkeys(numbers) if n not in line_numbers]
    if not names and not numbers:
        found.append("the point states no name and no number")
    if PRESSURE.search(point.text) and "%" not in line:
        found.append(f"a claim of pressure or dominance needs a share of passes in {point.source}")
    if point.source.startswith("stats:"):
        found += _one_team(point.text, line, sources, point.source)
    return found


def _one_team(text: str, line: str, sources: Sources, source: str) -> list[str]:
    """A statistics point speaks of one team, with that team's numbers, so no number changes hands (SPEC §20)."""
    teams = [t.short for t in (sources.req.match.home, sources.req.match.away) if t.short.lower() in WORD.findall(text.lower())]
    if len(teams) != 1:
        return [f"a {source} point must name exactly one team"]
    minute, _, rest = line.partition(". ")
    sentence = next(s for s in rest.split(". ") if s.startswith(teams[0]))
    allowed = set(NUMBER.findall(sentence)) | set(NUMBER.findall(minute))
    return [f"{n} is not {teams[0]}'s in {source}" for n in dict.fromkeys(NUMBER.findall(text)) if n not in allowed]


class CodeAnalyst:
    """The goal lines and the numbers line of the recap, cited as they are: always true, and the fallback."""

    by = "code"

    def propose(self, req: Request, attempt: int, feedback: list[str]) -> list[Proposed]:
        lines = req.recap.lines
        goals = [n for n, line in enumerate(lines, start=1) if line.startswith(("Minute ", "Minuto "))][: MAX_POINTS - 1]
        return [Proposed(lines[n - 1], f"recap:{n}") for n in goals + [len(lines)]]


@dataclass
class FlawedAnalyst:
    """A test analyst that puts a wrong name or number in every point, for `bad_attempts` attempts."""

    bad_attempts: int
    by: str = "model"
    feedback_seen: list[str] = field(default_factory=list)

    def propose(self, req: Request, attempt: int, feedback: list[str]) -> list[Proposed]:
        self.feedback_seen += feedback
        points = CodeAnalyst().propose(req, attempt, feedback)
        if attempt > self.bad_attempts:
            return points
        sources, flawed = Sources(req), []
        teams = {req.match.home.short.lower(), req.match.away.short.lower()}
        for point in points:
            line_words = set(WORD.findall(point.text.lower()))
            stranger = next(n for n in sorted(sources.names - teams) if n not in line_words)
            name = next((w for w in WORD.findall(point.text) if w.lower() in sources.names - teams), None)
            text = point.text.replace(name, stranger.title(), 1) if name else NUMBER.sub("99", point.text, count=1)
            flawed.append(Proposed(text, point.source))
        return flawed


def parse_points(raw: str) -> list[Proposed] | None:
    """The points of a JSON reply, or None when it is not one. Unchecked: `check_point` decides."""
    try:
        data = json.loads(raw)
        return [Proposed(str(p["text"])[: MAX_CHARS * 2], str(p["source"])[:20]) for p in data["points"][: MAX_POINTS * 2]]
    except (ValueError, KeyError, TypeError):
        return None


def reply_key(req: Request, attempt: int, feedback: list[str]) -> str:
    """The recorded reply's key: a changed instruction, window, language or recap is a new question. The cues are
    not in it, so one analysis serves every detail level and focus of a window (SPEC §20)."""
    material = [req.match.seed, req.preset.id, req.lang, attempt, sorted(feedback), INSTRUCTIONS, req.recap.lines]
    return hashlib.sha256(json.dumps(material, ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Store:
    replies: dict[str, str] = field(default_factory=dict)
    model: str = ""
    recorded: str = ""


def load_store(path: Path | str = STORE_PATH) -> Store:
    """The recorded Analyst replies; a missing or unreadable file is an empty store, so the fallback speaks."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data["version"] != VERSION or not isinstance(data["replies"], dict):
            raise ValueError("unexpected structure")
        replies = {str(k): str(v) for k, v in data["replies"].items()}
        return Store(replies, str(data.get("model", "")), str(data.get("recorded", "")))
    except FileNotFoundError:
        log.warning("no recorded analyst replies: the code points speak")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.error("the recorded analyst replies could not be read (%s)", type(exc).__name__)
    return Store()


class ReplayAnalyst:
    """The live Analyst's recorded replies, checked like any other reply on every session."""

    by = "model"

    def __init__(self, store: Store):
        self.store = store

    def propose(self, req: Request, attempt: int, feedback: list[str]) -> list[Proposed] | None:
        raw = self.store.replies.get(reply_key(req, attempt, feedback))
        return parse_points(raw) if raw is not None else None


_SHARED: ReplayAnalyst | None = None
_SHARED_LOCK = threading.Lock()


def shared_replay() -> ReplayAnalyst:
    global _SHARED
    with _SHARED_LOCK:
        if _SHARED is None:
            _SHARED = ReplayAnalyst(load_store())
        return _SHARED


# ---- the steps, shared by the plain pipeline and the workflow ------------------------------------------


def propose_step(
    analyst: Analyst, req: Request, attempt: int, feedback: list[str], trace: list[TraceStep], executor: str | None = None
) -> list[Proposed]:
    """One attempt of the analyst; a failure costs the attempt, not the session."""
    try:
        proposed = analyst.propose(req, attempt, list(feedback))
    except Exception as exc:  # noqa: BLE001 - any analyst failure burns an attempt
        trace.append(TraceStep(step="analyst", status="failed", attempt=attempt, detail=type(exc).__name__, executor=executor))
        return []
    detail = f"{len(proposed)} points" if proposed is not None else "no reply"
    trace.append(TraceStep(step="analyst", status="ok", attempt=attempt, detail=detail, executor=executor))
    return proposed or []


def check_step(
    req: Request,
    proposed: list[Proposed],
    kept: list[AnalysisPoint],
    attempt: int,
    trace: list[TraceStep],
    executor: str | None = None,
) -> list[str]:
    """Keep the points that pass (in order, no repeats, at most four); return the issues of the rest."""
    sources, issues = Sources(req), []
    for n, point in enumerate(proposed, start=1):
        found = check_point(point, sources)
        if found:
            issues.append(f"point {n}: {found[0]}")
        elif point.text not in {p.text for p in kept} and len(kept) < MAX_POINTS:
            kept.append(AnalysisPoint(text=point.text, source=point.source))
    detail = f"{len(proposed) - len(issues)} of {len(proposed)} points kept" + (f": {issues[0]}" if issues else "")
    status = "failed" if issues else "ok"
    trace.append(TraceStep(step="analysis_check", status=status, attempt=attempt, detail=detail, executor=executor))
    return issues


def finish(req: Request, by: str, kept: list[AnalysisPoint], rejected: int, attempts: int) -> Analysis:
    """The points that passed, or, when none did, the code points marked as the fallback."""
    if kept:
        return Analysis(by=by, status="verified", attempts=attempts, rejected=rejected, points=kept)  # type: ignore[arg-type]
    code = [AnalysisPoint(text=p.text, source=p.source) for p in CodeAnalyst().propose(req, attempts, [])]
    return Analysis(by="code", status="fallback", attempts=attempts, rejected=rejected, points=code)


def analyse(req: Request, analyst: Analyst, trace: list[TraceStep]) -> Analysis:
    """Propose, check, retry once with the issues, then the points that passed or the code points."""
    kept: list[AnalysisPoint] = []
    rejected, feedback, attempt = 0, [], 0
    while attempt < MAX_ATTEMPTS:
        attempt += 1
        proposed = propose_step(analyst, req, attempt, feedback, trace)
        issues = check_step(req, proposed, kept, attempt, trace)
        rejected += len(issues)
        if not issues:
            break
        feedback = issues
    return finish(req, analyst.by, kept, rejected, attempt)
