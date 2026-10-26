"""Interpret: match statistics counted by code from the events, for the listener who wants numbers (SPEC §18)."""

import math
from dataclasses import dataclass

from app.contracts import Event, StatsPoint, Team, TeamStats

PASSES = {"pass", "long_ball"}
SHOTS = {"shot_on_target", "shot_off_target", "shot_blocked", "goal"}
ON_TARGET = {"shot_on_target", "goal"}
BALL_WON = {"tackle", "interception"}
WHISTLES = {"halftime", "fulltime"}
LENGTH_M, WIDTH_M = 105, 68
RECENT_S = 300  # "recent possession" looks back five minutes of match time


@dataclass
class _Tally:
    passes: int = 0
    completed: int = 0
    resolved: int = 0
    metres: float = 0.0
    shots: int = 0
    on_target: int = 0
    won: int = 0

    def stats(self, possession: int, recent: int) -> TeamStats:
        return TeamStats(
            possession=possession,
            recent_possession=recent,
            passes=self.passes,
            passes_completed=self.completed,
            pass_accuracy=round(100 * self.completed / self.resolved) if self.resolved else 0,
            avg_pass_m=round(self.metres / self.passes, 1) if self.passes else 0.0,
            shots=self.shots,
            shots_on_target=self.on_target,
            ball_won=self.won,
        )


class _Counter:
    def __init__(self) -> None:
        self.tally: dict[Team, _Tally] = {"home": _Tally(), "away": _Tally()}
        self.open_pass: Team | None = None  # the side whose last pass is not resolved yet
        self.previous: Event | None = None
        self.pass_times: list[tuple[int, Team]] = []

    def add(self, event: Event) -> None:
        if event.kind in WHISTLES:
            self.open_pass = None  # a pass open at the whistle is never resolved
        elif event.team and event.kind != "foul" and self.open_pass:  # a foul is by the other side: the passer keeps the ball
            passer = self.tally[self.open_pass]
            passer.resolved += 1
            passer.completed += event.team == self.open_pass
            self.open_pass = None
        if event.team:
            mine = self.tally[event.team]
            if event.kind in PASSES:
                start = self.previous or event  # an event's position is where the ball ends up
                mine.passes += 1
                self.pass_times.append((event.t, event.team))
                mine.metres += math.hypot((event.x - start.x) * LENGTH_M / 100, (event.y - start.y) * WIDTH_M / 100)
                self.open_pass = event.team
            mine.shots += event.kind in SHOTS
            mine.on_target += event.kind in ON_TARGET
            mine.won += event.kind in BALL_WON
        self.previous = event

    def point(self, t_ms: int) -> StatsPoint:
        home, away = self.tally["home"], self.tally["away"]
        share = _share(home.passes, away.passes)
        since = (self.previous.t if self.previous else 0) - RECENT_S
        recent = [team for t, team in self.pass_times if t >= since]
        recent_share = _share(recent.count("home"), recent.count("away"))
        return StatsPoint(
            t_ms=t_ms, home=home.stats(share, recent_share), away=away.stats(100 - share, 100 - recent_share)
        )


def _share(home: int, away: int) -> int:
    """Home's share in whole percent; 50 when neither side has any."""
    return round(100 * home / (home + away)) if home + away else 50


def count(events: list[Event]) -> tuple[TeamStats, TeamStats]:
    """Home and away statistics after these events, in match order."""
    counter = _Counter()
    for event in events:
        counter.add(event)
    point = counter.point(0)
    return point.home, point.away


def points(events: list[Event], from_s: int, to_s: int) -> list[StatsPoint]:
    """The counts before the window, then after each of its events, at times relative to the window start."""
    counter = _Counter()
    for event in (e for e in events if e.t < from_s):
        counter.add(event)
    result = [counter.point(0)]
    for event in (e for e in events if from_s <= e.t <= to_s):
        counter.add(event)
        result.append(counter.point((event.t - from_s) * 1000))
    return result
