"""Explain: turn moments into audio-description sentences (SPEC §5).

`TemplateDescriber` is deterministic and always verifiable, so it is both the offline mode and
the fallback when an LLM describer cannot pass the verifier. `FlawedDescriber` plants errors for
the retry scenarios and the evaluation harness.
"""

import re
from typing import NamedTuple, Protocol

from app.contracts import Description, Event, FactRef, Lang, Match, Moment, Team
from app.pitch import attacks_right, event_progress


class Context:
    """Read-only lookups over a match, shared by describers and the verifier."""

    def __init__(self, match: Match, lang: Lang):
        self.match = match
        self.lang = lang
        self.by_id = {e.id: e for e in match.events}
        self._names = {(t.side, p.shirt): p.name for t in (match.home, match.away) for p in t.players}
        self.all_names = sorted(self._names.values())

    def name(self, team: Team | None, shirt: int | None) -> str:
        assert team is not None and shirt is not None
        return self._names[(team, shirt)]

    def short(self, team: Team) -> str:
        return (self.match.home if team == "home" else self.match.away).short

    def involved(self, moment: Moment) -> set[str]:
        names = set()
        for event_id in moment.event_ids:
            event = self.by_id[event_id]
            for shirt in (event.player, event.target):
                if shirt is not None and event.team is not None:
                    names.add(self.name(event.team, shirt))
        return names


class Describer(Protocol):
    def describe(
        self, moments: list[Moment], ctx: Context, feedback: dict[int, list[str]], attempt: int
    ) -> dict[int, Description]: ...


LEX: dict[str, dict] = {
    "en": {
        "assist": "set up by",
        "minute": "Minute",
        "dir": {True: "left to right", False: "right to left"},
        "lane_from": {"left": "from the left", "centre": "from the centre", "right": "from the right"},
        "lane_down": {"left": "down the left", "centre": "through the middle", "right": "down the right"},
        "side": {"left": "on the left", "centre": "in the centre", "right": "on the right"},
        "zone_at": ["in their own half", "in midfield", "in the opposition half", "in the final third"],
        "zone_to": ["in their own half", "through midfield", "into the opposition half", "into the final third"],
        "t": {
            "kickoff": [("Kick-off. {team} get us under way, attacking {dir}.", "Kick-off.")],
            "goal": [
                ("Goal! {p} scores for {team}. {home} {hs}, {away} {as_}.", "Goal! {p} scores for {team}."),
                ("It's in! {p} finds the net for {team}. {home} {hs}, {away} {as_}.", "It's in! {p} scores."),
            ],
            "goal_assist": [
                (
                    "Goal! {p} scores for {team}, {assist}. {home} {hs}, {away} {as_}.",
                    "Goal! {p} scores for {team}.",
                ),
                (
                    "It's in! {p} finishes for {team}, {assist}. {home} {hs}, {away} {as_}.",
                    "It's in! {p} scores.",
                ),
            ],
            "halftime": [("Half-time. {home} {hs}, {away} {as_}.", "Half-time.")],
            "fulltime": [("Full-time. {home} {hs}, {away} {as_}.", "Full-time.")],
            "shot_on_target": [
                ("{p} shoots {lane_from}, on target.", "{p} shoots, on target."),
                ("{p} has a go {lane_from} and it's on target.", "{p} shoots, on target."),
            ],
            "shot_off_target": [
                ("{p} shoots {lane_from}, wide.", "{p} shoots wide."),
                ("{p} lets fly {lane_from} but it goes wide.", "{p} shoots wide."),
            ],
            "shot_blocked": [("{p} shoots {lane_from}, blocked.", "{p} shoots, blocked.")],
            "save": [("{p} makes the save.", "{p} saves."), ("The keeper {p} gathers it.", "{p} saves.")],
            "corner": [("Corner to {team}, taken by {p} {lane_from}.", "Corner to {team}.")],
            "free_kick": [("Free kick to {team}, {p} to take it.", "Free kick, {team}.")],
            "foul": [("Foul by {p} of {team}.", "Foul, {team}.")],
            "throw_in": [("Throw-in to {team} {side}.", "Throw-in, {team}.")],
            "turnover": [
                ("{p} of {team} wins the ball {zone}.", "{p} wins the ball."),
                ("{team} regain possession {zone}, through {p}.", "{team} win it back."),
            ],
            "buildup": [
                ("{team} build {lane_down}: {chain}, {zone}.", "{team} move forward {lane_down}."),
                ("{team} work it {lane_down} through {chain}, {zone}.", "{team} move forward."),
            ],
            "score_update": [("Minute {m}. {home} {hs}, {away} {as_}.", "{home} {hs}, {away} {as_}.")],
        },
    },
    "it": {
        "assist": "assist di",
        "minute": "Minuto",
        "dir": {True: "da sinistra a destra", False: "da destra a sinistra"},
        "lane_from": {"left": "dalla sinistra", "centre": "dal centro", "right": "dalla destra"},
        "lane_down": {"left": "sulla sinistra", "centre": "per vie centrali", "right": "sulla destra"},
        "side": {"left": "sulla sinistra", "centre": "al centro", "right": "sulla destra"},
        "zone_at": [
            "nella propria metà campo",
            "a centrocampo",
            "nella metà campo avversaria",
            "nell'ultimo terzo",
        ],
        "zone_to": [
            "nella propria metà campo",
            "attraverso il centrocampo",
            "nella metà campo avversaria",
            "fino all'ultimo terzo",
        ],
        "t": {
            "kickoff": [("Calcio d'inizio. {team} danno il via, attaccano {dir}.", "Calcio d'inizio.")],
            "goal": [
                ("Gol! {p} segna per {team}. {home} {hs}, {away} {as_}.", "Gol! {p} segna per {team}."),
                ("Rete! {p} trova il gol per {team}. {home} {hs}, {away} {as_}.", "Rete! {p} segna."),
            ],
            "goal_assist": [
                (
                    "Gol! {p} segna per {team}, {assist}. {home} {hs}, {away} {as_}.",
                    "Gol! {p} segna per {team}.",
                ),
                (
                    "Rete! {p} finalizza per {team}, {assist}. {home} {hs}, {away} {as_}.",
                    "Rete! {p} segna.",
                ),
            ],
            "halftime": [("Fine primo tempo. {home} {hs}, {away} {as_}.", "Fine primo tempo.")],
            "fulltime": [("Fine partita. {home} {hs}, {away} {as_}.", "Fine partita.")],
            "shot_on_target": [
                ("{p} tira {lane_from}, nello specchio.", "{p} tira, in porta."),
                ("{p} ci prova {lane_from} e inquadra la porta.", "{p} tira, in porta."),
            ],
            "shot_off_target": [
                ("{p} tira {lane_from}, fuori.", "{p} tira fuori."),
                ("{p} calcia {lane_from} ma la palla finisce fuori.", "{p} tira fuori."),
            ],
            "shot_blocked": [("{p} tira {lane_from}, respinto.", "{p} tira, respinto.")],
            "save": [("Parata di {p}.", "Parata di {p}."), ("Il portiere {p} blocca.", "{p} para.")],
            "corner": [("Calcio d'angolo per {team}, batte {p} {lane_from}.", "Angolo per {team}.")],
            "free_kick": [("Punizione per {team}, batte {p}.", "Punizione, {team}.")],
            "foul": [("Fallo di {p}, {team}.", "Fallo, {team}.")],
            "throw_in": [("Rimessa laterale per {team} {side}.", "Rimessa, {team}.")],
            "turnover": [
                ("{p} del {team} recupera palla {zone}.", "{p} recupera palla."),
                ("{team} riconquistano il possesso {zone}, con {p}.", "{team} recuperano."),
            ],
            "buildup": [
                ("{team} costruiscono {lane_down}: {chain}, {zone}.", "{team} avanzano {lane_down}."),
                ("{team} manovrano {lane_down} con {chain}, {zone}.", "{team} avanzano."),
            ],
            "score_update": [("Minuto {m}. {home} {hs}, {away} {as_}.", "{home} {hs}, {away} {as_}.")],
        },
    },
}


def _zone(options: list[str], progress: int) -> str:
    return options[0 if progress < 40 else 1 if progress < 60 else 2 if progress < 78 else 3]


def _chain(events: list[Event], ctx: Context) -> str:
    players = [ctx.name(e.team, e.player) for e in events if e.player is not None]
    last = events[-1]
    if last.target is not None:
        players.append(ctx.name(last.team, last.target))
    sequence = list(dict.fromkeys(players))  # each name once, in order of first touch
    if len(sequence) > 3:
        sequence = [sequence[0], sequence[len(sequence) // 2], sequence[-1]]
    return ", ".join(sequence)


class Facts(NamedTuple):
    """What the code knows about a moment: its template key, the values a sentence may use and
    the refs that go with them. The verifier derives its expectations from the same object."""

    key: str
    fields: dict[str, object]
    refs: list[FactRef]


def facts(moment: Moment, ctx: Context) -> Facts:
    lex = LEX[ctx.lang]
    events = [ctx.by_id[i] for i in moment.event_ids]
    last = events[-1]
    ref = lambda e, field: FactRef(event_id=e.id, field=field, value=getattr(e, field))
    fields: dict[str, object] = {
        "home": ctx.short("home"),
        "away": ctx.short("away"),
        "hs": last.home_score,
        "as_": last.away_score,
    }
    fields["score"] = f"{fields['home']} {fields['hs']}, {fields['away']} {fields['as_']}"
    refs = [ref(last, "home_score"), ref(last, "away_score")]
    key = moment.kind
    if last.team is not None:
        fields["team"] = ctx.short(last.team)
    if last.lane is not None:
        fields["lane_from"] = lex["lane_from"][last.lane]
        fields["lane_down"] = lex["lane_down"][last.lane]
        fields["side"] = lex["side"][last.lane]
    if key == "kickoff":
        fields["dir"] = lex["dir"][attacks_right(last.team, last.half)]
        refs = [ref(last, "team")]
    elif key == "goal":
        fields["p"] = ctx.name(last.team, last.player)
        refs += [ref(last, "team"), ref(last, "player")]
        if len(events) > 1:
            key = "goal_assist"
            fields["a"] = ctx.name(events[0].team, events[0].player)
            fields["assist"] = f"{lex['assist']} {fields['a']}"
            refs.append(ref(events[0], "player"))
    elif key in ("halftime", "fulltime"):
        pass
    elif key == "shot":
        key = last.kind
        fields["p"] = ctx.name(last.team, last.player)
        refs = [ref(last, "team"), ref(last, "player"), ref(last, "lane"), ref(last, "kind")]
    elif key in ("save", "free_kick", "foul", "corner", "throw_in", "turnover"):
        if last.player is not None:
            fields["p"] = ctx.name(last.team, last.player)
        refs = [ref(last, "team"), ref(last, "player")]
        if key in ("corner", "throw_in"):
            refs.append(ref(last, "lane"))
        if key == "turnover":
            fields["zone"] = _zone(lex["zone_at"], event_progress(last))
    elif key == "buildup":
        fields["chain"] = _chain(events, ctx)
        fields["zone"] = _zone(lex["zone_to"], event_progress(last))
        fields["team"] = ctx.short(events[0].team)
        refs = [ref(events[0], "team"), ref(events[0], "player"), ref(last, "lane")]
        if last.target is not None:
            refs.append(ref(last, "target"))
    elif key == "score_update":
        fields["m"] = moment.t // 60
        fields["minute"] = f"{lex['minute']} {fields['m']}"
    # A sentence may state a team, a player or a lane only if the refs carry it; the last event of a
    # save, a foul or a score reminder has all three, but they are not part of that story.
    supported = {r.field for r in refs}
    for field, names in (("team", ("team",)), ("player", ("p",)), ("lane", ("lane_from", "lane_down", "side"))):
        if field not in supported:
            for name in names:
                fields.pop(name, None)
    return Facts(key, fields, refs)


def render(moment: Moment, ctx: Context) -> Description:
    key, fields, refs = facts(moment, ctx)
    options = LEX[ctx.lang]["t"][key]
    full, short = options[moment.id % len(options)]
    return Description(
        moment_id=moment.id, lang=ctx.lang, full=full.format(**fields), short=short.format(**fields), refs=refs
    )


class TemplateDescriber:
    """Deterministic offline describer; also the verified fallback."""

    def describe(
        self, moments: list[Moment], ctx: Context, feedback: dict[int, list[str]], attempt: int
    ) -> dict[int, Description]:
        return {m.id: render(m, ctx) for m in moments}


class FlawedDescriber:
    """Plants a wrong name (or an impossible score) in every description for the first N attempts."""

    def __init__(self, bad_attempts: int, inner: Describer | None = None):
        self.bad_attempts = bad_attempts
        self.inner = inner or TemplateDescriber()

    def describe(
        self, moments: list[Moment], ctx: Context, feedback: dict[int, list[str]], attempt: int
    ) -> dict[int, Description]:
        described = self.inner.describe(moments, ctx, feedback, attempt)
        if attempt > self.bad_attempts:
            return described
        return {m.id: self._corrupt(m, described[m.id], ctx) for m in moments}

    @staticmethod
    def _corrupt(moment: Moment, description: Description, ctx: Context) -> Description:
        involved = ctx.involved(moment)
        present = [n for n in involved if re.search(rf"\b{n}\b", description.full)]
        if present:
            foreign = next(n for n in ctx.all_names if n not in involved)
            swap = lambda text: re.sub(rf"\b{present[0]}\b", foreign, text)
            return description.model_copy(update={"full": swap(description.full), "short": swap(description.short)})
        return description.model_copy(update={"full": description.full + " Score 99-0."})
