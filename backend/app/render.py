"""Render: sonification (earcons), the ball track and WebVTT captions (SPEC §7)."""

from app.contracts import BallPoint, Cue, Earcon, Event, Profile
from app.moments import focus_of, involves
from app.pitch import event_progress

EARCON: dict[str, tuple[str, float]] = {
    "pass": ("tick", 0.25),
    "dribble": ("tick", 0.25),
    "long_ball": ("tick", 0.25),
    "clearance": ("tick", 0.25),
    "tackle": ("turnover", 0.3),
    "interception": ("turnover", 0.3),
    "shot_on_target": ("shot", 0.6),
    "shot_off_target": ("shot", 0.6),
    "shot_blocked": ("shot", 0.6),
    "save": ("save", 0.5),
    "goal": ("goal", 0.9),
    "corner": ("set_piece", 0.4),
    "free_kick": ("set_piece", 0.4),
    "throw_in": ("set_piece", 0.4),
    "foul": ("whistle", 0.5),
    "kickoff": ("whistle", 0.5),
    "halftime": ("whistle_long", 0.5),
    "fulltime": ("whistle_long", 0.5),
}
CALM_KINDS = {"goal", "whistle", "whistle_long"}
CALM_GAIN = 0.3
FOCUS_GAIN = 1.5  # the followed player's sounds are louder (SPEC §17)


def pan_of(event: Event) -> float:
    return round((event.x - 50) / 50, 3)


def earcons(events: list[Event], window_start_s: int, profile: Profile) -> list[Earcon]:
    if not profile.earcons:
        return []
    focus = focus_of(profile)
    result = []
    for event in events:
        kind, gain = EARCON[event.kind]
        if profile.calm:
            if kind not in CALM_KINDS:
                continue
            gain = CALM_GAIN
        if involves(event, focus):
            gain = min(1.0, round(gain * FOCUS_GAIN, 3))
        progress = event_progress(event) if event.team else 50
        result.append(
            Earcon(
                t_ms=(event.t - window_start_s) * 1000,
                kind=kind,  # type: ignore[arg-type]
                pan=pan_of(event),
                pitch=round(progress / 100, 3),
                gain=gain,
            )
        )
    return result


def track(events: list[Event], window_start_s: int) -> list[BallPoint]:
    return [
        BallPoint(t_ms=(e.t - window_start_s) * 1000, x=e.x, y=e.y, home_score=e.home_score, away_score=e.away_score)
        for e in events
    ]


def _timestamp(ms: int) -> str:
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def webvtt(cues: list[Cue]) -> str:
    blocks = ["WEBVTT", ""]
    for cue in cues:
        blocks += [str(cue.id), f"{_timestamp(cue.start_ms)} --> {_timestamp(cue.end_ms)}", cue.text, ""]
    return "\n".join(blocks)
