"""Deterministic synthetic match: a possession simulation with a pinned storyline (SPEC §3)."""

import random

from app.contracts import Event, Kind, Match, Player, Team, TeamInfo
from app.pitch import attacks_right, lane_of

SEED = 424242
GOALS: tuple[tuple[int, Team], ...] = ((16, "home"), (52, "away"), (78, "home"))
FIRST_HALF_END = 2699
SECOND_HALF_START = 2700
FULL_TIME = 5399


def _team(side: Team, name: str, short: str, squad: list[tuple[int, str, str]]) -> TeamInfo:
    return TeamInfo(
        side=side, name=name, short=short, players=[Player(shirt=s, name=n, role=r) for s, n, r in squad]
    )


HOME = _team(
    "home",
    "Northgate Red",
    "Northgate",
    [
        (1, "Moretti", "gk"),
        (2, "Okafor", "def"),
        (3, "Duval", "def"),
        (4, "Brandt", "def"),
        (5, "Hollis", "def"),
        (6, "Tanaka", "mid"),
        (8, "Reyes", "mid"),
        (10, "Kovacs", "mid"),
        (7, "Marsh", "fwd"),
        (9, "Lindqvist", "fwd"),
        (11, "Adeyemi", "fwd"),
    ],
)
AWAY = _team(
    "away",
    "Harbour Blue",
    "Harbour",
    [
        (1, "Petrov", "gk"),
        (2, "Silva", "def"),
        (3, "Fischer", "def"),
        (4, "Novak", "def"),
        (5, "Haddad", "def"),
        (6, "Costa", "mid"),
        (8, "Mbeki", "mid"),
        (10, "Laurent", "mid"),
        (7, "Rossi", "fwd"),
        (9, "Duarte", "fwd"),
        (11, "Nakamura", "fwd"),
    ],
)


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return int(max(low, min(high, round(value))))


class _Generator:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.events: list[Event] = []
        self.t = 0
        self.half = 1
        self.team: Team = "home"
        self.p = 50  # progress of the team in possession
        self.y = 50
        self.holder = 10
        self.score = {"home": 0, "away": 0}

    # --- helpers -----------------------------------------------------------------------
    @staticmethod
    def other(team: Team) -> Team:
        return "away" if team == "home" else "home"

    @staticmethod
    def info(team: Team) -> TeamInfo:
        return HOME if team == "home" else AWAY

    def pick(self, team: Team, p: int, exclude: int | None = None) -> int:
        if p < 25:
            weights = {"gk": 0.15, "def": 0.45, "mid": 0.35, "fwd": 0.05}
        elif p < 65:
            weights = {"gk": 0.0, "def": 0.2, "mid": 0.5, "fwd": 0.3}
        else:
            weights = {"gk": 0.0, "def": 0.05, "mid": 0.35, "fwd": 0.6}
        role = self.rng.choices(list(weights), weights=list(weights.values()))[0]
        players = self.info(team).players
        pool = [pl.shirt for pl in players if pl.role == role and pl.shirt != exclude]
        if not pool:  # the keeper passing to himself
            pool = [pl.shirt for pl in players if pl.role == "def"]
        return self.rng.choice(pool)

    def emit(
        self,
        kind: Kind,
        team: Team | None,
        player: int | None = None,
        target: int | None = None,
        p: int | None = None,
        y: int | None = None,
    ) -> None:
        p = self.p if p is None else p
        y = self.y if y is None else y
        if team is None:
            x, lane = 50, None
        else:
            x = p if attacks_right(team, self.half) else 100 - p
            lane = lane_of(_clamp(y), team, self.half)
        if kind == "goal":
            assert team is not None
            self.score[team] += 1
        self.events.append(
            Event(
                id=len(self.events) + 1,
                t=self.t,
                minute=self.t // 60 + 1,
                half=self.half,
                team=team,
                player=player,
                target=target,
                kind=kind,
                x=_clamp(x),
                y=_clamp(y),
                lane=lane,
                home_score=self.score["home"],
                away_score=self.score["away"],
            )
        )

    def give_ball(self, team: Team, p: int, holder: int | None = None) -> None:
        self.team, self.p = team, p
        self.holder = holder if holder is not None else self.pick(team, p)

    # --- open play ---------------------------------------------------------------------
    def pass_to(self, kind: Kind, dp: int, dys: tuple[int, ...], target: int | None = None) -> None:
        new_p = _clamp(self.p + dp, 3, 96)
        new_y = _clamp(self.y + self.rng.choice(dys), 8, 92)
        receiver = target or self.pick(self.team, new_p, exclude=self.holder)
        self.emit(kind, self.team, self.holder, receiver, new_p, new_y)
        self.p, self.y, self.holder = new_p, new_y, receiver

    def do_pass_fwd(self) -> None:
        self.pass_to("pass", self.rng.randint(5, 16), (-20, 0, 0, 20))

    def do_pass_sq(self) -> None:
        self.pass_to("pass", self.rng.randint(-3, 3), (-35, -25, 25, 35))

    def do_pass_back(self) -> None:
        self.pass_to("pass", -self.rng.randint(5, 14), (-15, 0, 15))

    def do_long(self) -> None:
        self.pass_to("long_ball", self.rng.randint(18, 32), (-30, 0, 30))

    def do_dribble(self) -> None:
        new_p = _clamp(self.p + self.rng.randint(3, 9), 3, 96)
        self.emit("dribble", self.team, self.holder, None, new_p, self.y)
        self.p = new_p

    def do_clear(self) -> None:
        new_p = self.rng.randint(45, 65)
        self.emit("clearance", self.team, self.holder, None, new_p, self.rng.randint(15, 85))
        self.give_ball(self.team, new_p)

    def do_turnover(self) -> None:
        winner = self.other(self.team)
        new_p = _clamp(100 - self.p + self.rng.randint(-8, 8), 5, 95)
        player = self.pick(winner, new_p)
        self.emit(self.rng.choice(["tackle", "interception"]), winner, player, None, new_p, self.y)
        self.give_ball(winner, new_p, player)

    def do_foul(self) -> None:
        offender = self.other(self.team)
        offender_p = 100 - self.p
        self.emit("foul", offender, self.pick(offender, offender_p), None, offender_p, self.y)
        self.t += 2
        taker = self.pick(self.team, self.p)
        self.emit("free_kick", self.team, taker, None, self.p, self.y)
        self.holder = taker

    def do_throw(self) -> None:
        new_p = _clamp(self.p + self.rng.randint(-5, 8), 5, 95)
        new_y = self.rng.choice([4, 96])
        taker = self.pick(self.team, new_p)
        self.emit("throw_in", self.team, taker, None, new_p, new_y)
        self.p, self.y, self.holder = new_p, new_y, taker

    def do_shot(self) -> None:
        opponent = self.other(self.team)
        shooter = self.pick(self.team, self.p)
        roll = self.rng.random()
        if roll < 0.35:
            self.emit("shot_on_target", self.team, shooter, None, min(self.p + 4, 97), self.y)
            self.t += 1
            self.emit("save", opponent, 1, None, 4, 50)
            self.give_ball(opponent, 6, 1)
        elif roll < 0.70:
            self.emit("shot_off_target", self.team, shooter, None, min(self.p + 4, 97), self.y)
            self.give_ball(opponent, 8)
        else:
            self.emit("shot_blocked", self.team, shooter, None, self.p, self.y)
            if self.rng.random() < 0.4:
                self.t += 2
                self.emit("corner", self.team, self.pick(self.team, 80), None, 99, self.rng.choice([2, 98]))
                self.p, self.y = 88, 50
                self.holder = self.pick(self.team, 88)
            else:
                self.give_ball(opponent, 15)

    def step(self) -> None:
        self.t += self.rng.randint(3, 9)
        near, mid = self.p >= 72, 60 <= self.p < 72
        table = [
            ("pass_fwd", 0.34),
            ("pass_sq", 0.20),
            ("pass_back", 0.08),
            ("dribble", 0.08),
            ("long", 0.04),
            ("turnover", 0.16),
            ("foul", 0.04),
            ("throw", 0.03),
            ("clear", 0.03 if self.p < 30 else 0.0),
            ("shot", 0.11 if near else 0.02 if mid else 0.0),
        ]
        action = self.rng.choices([a for a, _ in table], weights=[w for _, w in table])[0]
        getattr(self, f"do_{action}")()

    # --- storyline ---------------------------------------------------------------------
    def forced_goal(self, minute: int, team: Team) -> None:
        goal_t = (minute - 1) * 60 + 15
        if self.team != team:
            self.t += self.rng.randint(3, 6)
            player = self.pick(team, 45)
            self.emit("interception", team, player, None, 45, self.y)
            self.give_ball(team, 45, player)
        while self.p < 78:
            self.t += self.rng.randint(3, 7)
            self.pass_to("pass", self.rng.randint(8, 18), (-20, 0, 0, 20))
        scorer = self.rng.choice([p.shirt for p in self.info(team).players if p.role == "fwd"])
        if scorer == self.holder:
            scorer = next(p.shirt for p in self.info(team).players if p.role == "fwd" and p.shirt != scorer)
        self.t += self.rng.randint(3, 6)
        self.pass_to("pass", 4, (0,), target=scorer)
        self.t = max(self.t + 2, goal_t)
        self.emit("goal", team, scorer, None, 96, self.rng.randint(44, 56))
        self.t += 30
        conceding = self.other(team)
        self.emit("kickoff", conceding, self.pick(conceding, 50), None, 50, 50)
        self.give_ball(conceding, 50)

    def play_half(self, end: int, goals: list[tuple[int, Team]]) -> None:
        pending = list(goals)
        while self.t < end - 60:
            if pending and self.t >= (pending[0][0] - 1) * 60 + 15 - 45:
                self.forced_goal(*pending.pop(0))
                continue
            self.step()

    def run(self) -> list[Event]:
        self.emit("kickoff", "home", 10, None, 50, 50)
        self.give_ball("home", 50, 10)
        self.play_half(FIRST_HALF_END, [g for g in GOALS if g[0] <= 45])
        self.t = FIRST_HALF_END
        self.emit("halftime", None)
        self.half, self.t = 2, SECOND_HALF_START
        self.emit("kickoff", "away", 10, None, 50, 50)
        self.give_ball("away", 50, 10)
        self.play_half(FULL_TIME, [g for g in GOALS if g[0] > 45])
        self.t = FULL_TIME
        self.emit("fulltime", None)
        return self.events


def generate_match(seed: int = SEED) -> Match:
    return Match(seed=seed, home=HOME, away=AWAY, events=_Generator(seed).run())
