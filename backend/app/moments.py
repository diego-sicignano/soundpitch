"""Interpret: group events into prioritised moments (SPEC §4)."""

from app.contracts import Detail, Event, Moment, MomentKind
from app.pitch import event_progress

PASS_LIKE = {"pass", "dribble", "long_ball", "clearance"}
MIN_PRIORITY: dict[Detail, int] = {"essential": 2, "standard": 1, "full": 0}
SINGLE: dict[str, tuple[MomentKind, int]] = {
    "kickoff": ("kickoff", 3),
    "goal": ("goal", 3),
    "halftime": ("halftime", 3),
    "fulltime": ("fulltime", 3),
    "shot_on_target": ("shot", 2),
    "shot_off_target": ("shot", 2),
    "shot_blocked": ("shot", 2),
    "save": ("save", 2),
    "corner": ("corner", 2),
    "foul": ("foul", 1),
    "throw_in": ("throw_in", 1),
}
REMINDER_MINUTES = range(10, 90, 10)


def _single(event: Event, assist: Event | None) -> tuple[MomentKind, int, list[int]] | None:
    if event.kind in SINGLE:
        kind, priority = SINGLE[event.kind]
        ids = [assist.id, event.id] if event.kind == "goal" and assist else [event.id]
        return kind, priority, ids
    if event.kind == "free_kick":
        return "free_kick", 2 if event_progress(event) >= 70 else 1, [event.id]
    if event.kind in ("tackle", "interception"):
        return "turnover", 1 if event_progress(event) >= 40 else 0, [event.id]
    return None


def _is_assist(event: Event, following: Event | None) -> bool:
    return (
        following is not None
        and following.kind == "goal"
        and event.kind == "pass"
        and event.team == following.team
        and event.target == following.player
    )


def detect_moments(events: list[Event], detail: Detail) -> list[Moment]:
    """Moments of a window of events, filtered by detail level (priority 3 is always kept)."""
    raw: list[tuple[int, int, MomentKind, int, object, list[int]]] = []  # t, order, kind, prio, team, ids
    run: list[Event] = []

    def close_run() -> None:
        if not run:
            return
        priority = 1 if max(event_progress(e) for e in run) >= 60 else 0
        raw.append((run[-1].t, run[0].id, "buildup", priority, run[0].team, [e.id for e in run]))
        run.clear()

    for index, event in enumerate(events):
        following = events[index + 1] if index + 1 < len(events) else None
        if event.kind in PASS_LIKE:
            if run and run[-1].team != event.team:
                close_run()
            if _is_assist(event, following):  # the assist belongs to the goal moment
                close_run()
            else:
                run.append(event)
            continue
        close_run()
        previous = events[index - 1] if index else None
        assist = previous if previous is not None and _is_assist(previous, event) else None
        single = _single(event, assist)
        if single:
            kind, priority, ids = single
            raw.append((event.t, ids[0], kind, priority, event.team, ids))
    close_run()

    if events:
        first, last = events[0].t, events[-1].t
        for minute in REMINDER_MINUTES:
            t = minute * 60
            if first <= t <= last:
                latest = max((e for e in events if e.t <= t), key=lambda e: e.id)
                raw.append((t, latest.id, "score_update", 2, None, [latest.id]))

    raw.sort(key=lambda r: (r[0], r[1]))
    kept = [r for r in raw if r[3] == 3 or r[3] >= MIN_PRIORITY[detail]]
    return [
        Moment(id=n, t=t, priority=priority, kind=kind, team=team, event_ids=ids)
        for n, (t, _, kind, priority, team, ids) in enumerate(kept, start=1)
    ]
