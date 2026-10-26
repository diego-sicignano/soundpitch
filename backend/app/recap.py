"""Context: the code-written summary of the match up to the end of a window (SPEC §19).

Fixed phrases filled from the events, like the score context of `stakes`: no model writes them, so they carry
only names, minutes and numbers the events hold.
"""

from app.contracts import Event, Lang, Match, Preset, Recap, TeamInfo
from app.stats import count

PRESSING, AGAINST_THE_RUN = 60, 40  # a share of passes in the five minutes before a goal worth saying
PHRASES = {
    "en": {
        "final": "Full-time: {home} {hs}, {away} {as_}.",
        "after": "After {m} minutes: {home} {hs}, {away} {as_}.",
        "goal": "Minute {m}: {scorer} scores for {team}",
        "assist": ", set up by {assister}",
        "pressing": " {team} had {p}% of the passes in the five minutes before.",
        "against": " It came against the run of play: {team} had {p}% of the passes in the five minutes before.",
        "numbers": "Possession: {home} {hp}%, {away} {ap}%. Shots: {hsh} to {ash}, on target {hot} to {aot}.",
    },
    "it": {
        "final": "Finale: {home} {hs}, {away} {as_}.",
        "after": "Dopo {m} minuti: {home} {hs}, {away} {as_}.",
        "goal": "Minuto {m}: gol di {scorer} per {team}",
        "assist": ", assist di {assister}",
        "pressing": " {team} aveva il {p}% dei passaggi nei cinque minuti prima.",
        "against": " È arrivato controcorrente: {team} aveva il {p}% dei passaggi nei cinque minuti prima.",
        "numbers": "Possesso: {home} {hp}%, {away} {ap}%. Tiri: {hsh} a {ash}, nello specchio {hot} a {aot}.",
    },
}


def _name(team: TeamInfo, shirt: int | None) -> str:
    return next(p.name for p in team.players if p.shirt == shirt)


def _goal_line(match: Match, goal: Event, phrases: dict[str, str]) -> str:
    team = match.home if goal.team == "home" else match.away
    line = phrases["goal"].format(m=goal.minute, scorer=_name(team, goal.player), team=team.short)
    before = [e for e in match.events if e.id < goal.id]
    passer = before[-1] if before else None
    if passer and passer.kind == "pass" and passer.team == goal.team and passer.target == goal.player:
        line += phrases["assist"].format(assister=_name(team, passer.player))
    line += "."
    home, away = count(before)
    share = (home if goal.team == "home" else away).recent_possession
    if share >= PRESSING:
        line += phrases["pressing"].format(team=team.short, p=share)
    elif share <= AGAINST_THE_RUN:
        line += phrases["against"].format(team=team.short, p=share)
    return line


def build(match: Match, preset: Preset, lang: Lang) -> Recap:
    """The score, each goal so far with its assist and the pressure before it, and the numbers (SPEC §19)."""
    phrases = PHRASES[lang]
    events = [e for e in match.events if e.t <= preset.to_s]
    last = events[-1]
    names = {"home": match.home.short, "away": match.away.short}
    score = {"home": names["home"], "away": names["away"], "hs": last.home_score, "as_": last.away_score}
    finished = any(e.kind == "fulltime" for e in events if e.t >= preset.from_s)
    lines = [phrases["final"].format(**score) if finished else phrases["after"].format(m=last.minute, **score)]
    lines += [_goal_line(match, e, phrases) for e in events if e.kind == "goal"]
    home, away = count(events)
    lines.append(phrases["numbers"].format(
        home=names["home"], away=names["away"], hp=home.possession, ap=away.possession,
        hsh=home.shots, ash=away.shots, hot=home.shots_on_target, aot=away.shots_on_target,
    ))
    return Recap(preset=preset.id, lang=lang, minute=last.minute, lines=lines)
