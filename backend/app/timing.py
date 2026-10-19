"""Render: fit descriptions into the silence between moments (SPEC §6).

Deterministic and arithmetic only: estimate how long a sentence takes to speak, then reserve
speech slots in priority order so that a must-say moment (a goal) is never pushed out by a
routine one, and no two cues ever overlap.
"""

from dataclasses import dataclass

from app.contracts import Cue, Description, Dropped, Lang, Moment

WPM: dict[Lang, int] = {"en": 165, "it": 155}
PADDING_MS = 300
LEAD_MS = 300
GAP_MS = 250
MAX_LAG_MS = {3: 10_000, 2: 6_000, 1: 5_000, 0: 4_000}


def estimate_ms(text: str, lang: Lang, rate: float) -> int:
    return round(len(text.split()) * 60_000 / (WPM[lang] * rate)) + PADDING_MS


@dataclass(frozen=True)
class Candidate:
    moment: Moment
    description: Description
    status: str  # "verified" | "fallback"
    pan: float


def _find_slot(occupied: list[tuple[int, int]], earliest: int, duration: int) -> int:
    start = earliest
    for begin, end in occupied:  # sorted, non-overlapping
        if start + duration + GAP_MS <= begin:
            break
        start = max(start, end + GAP_MS)
    return start


def plan(
    candidates: list[Candidate], window_start_s: int, rate: float
) -> tuple[list[Cue], list[Dropped]]:
    occupied: list[tuple[int, int]] = []
    placed: list[tuple[int, int, Candidate, str, str]] = []  # start, end, candidate, text, variant
    dropped: list[Dropped] = []
    for candidate in sorted(candidates, key=lambda c: (-c.moment.priority, c.moment.t, c.moment.id)):
        moment, description = candidate.moment, candidate.description
        earliest = (moment.t - window_start_s) * 1000 + LEAD_MS
        deadline = (moment.t - window_start_s) * 1000 + MAX_LAG_MS[moment.priority]
        choice = None
        for variant, text in (("full", description.full), ("short", description.short)):
            duration = estimate_ms(text, description.lang, rate)
            start = _find_slot(occupied, earliest, duration)
            if choice is None and (start <= deadline or moment.priority == 3):
                choice = (start, start + duration, text, variant)
            if start <= deadline:
                choice = (start, start + duration, text, variant)
                break
        if choice is None:
            dropped.append(Dropped(moment_id=moment.id, priority=moment.priority, reason="no gap before the deadline"))
            continue
        start, end, text, variant = choice
        occupied.append((start, end))
        occupied.sort()
        placed.append((start, end, candidate, text, variant))

    placed.sort(key=lambda p: (p[0], p[2].moment.id))
    cues = [
        Cue(
            id=n,
            moment_id=c.moment.id,
            start_ms=start,
            end_ms=end,
            text=text,
            variant=variant,  # type: ignore[arg-type]
            priority=c.moment.priority,
            status=c.status,  # type: ignore[arg-type]
            event_ids=c.moment.event_ids,
            pan=c.pan,
        )
        for n, (start, end, c, text, variant) in enumerate(placed, start=1)
    ]
    return cues, sorted(dropped, key=lambda d: d.moment_id)
