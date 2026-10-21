"""Stakes: one sentence on what the score now means, written by code from the score state (SPEC §5, S31).

Only a goal, half-time and full-time get one. It is added after verification, so the verifier, the model
prompt and the recorded replies never see it, and nothing here says anything the scores do not hold.
"""

from app.contracts import Event, Lang, Moment, Team
from app.describer import Context

PHRASES: dict[Lang, dict[str, str]] = {
    "en": {
        "opening": "The opening goal of the match.",
        "level": "That makes it level.",
        "lead": "{team} take the lead.",
        "extend": "{team} extend their lead.",
        "pull_back": "{team} pull one back.",
        "break_level": "All square at the break.",
        "break_lead": "{team} lead at the break.",
        "end_level": "The match ends level.",
        "end_win": "{team} win.",
    },
    "it": {
        "opening": "È il primo gol della partita.",
        "level": "Il risultato torna in parità.",
        # a club name is one subject: singular verbs ("Northgate passa"), as in Italian sports prose
        "lead": "{team} passa in vantaggio.",
        "extend": "{team} allunga.",
        "pull_back": "{team} accorcia le distanze.",
        "break_level": "Parità all'intervallo.",
        "break_lead": "{team} avanti all'intervallo.",
        "end_level": "Finisce in parità.",
        "end_win": "Vince {team}.",
    },
}


def _leader(event: Event) -> Team | None:
    if event.home_score == event.away_score:
        return None
    return "home" if event.home_score > event.away_score else "away"


def _goal(goal: Event, ctx: Context) -> tuple[str, Team] | None:
    """(phrase key, scorer) from the score before the goal, or None when that score cannot be trusted."""
    side = goal.team
    if side is None:
        return None
    own, other = (goal.home_score, goal.away_score) if side == "home" else (goal.away_score, goal.home_score)
    own -= 1  # the goal adds one to the scorer: this is the score before it
    if own < 0:
        return None
    before = ctx.by_id.get(goal.id - 1)
    if before is not None:
        held = (before.home_score, before.away_score)
        if held != ((own, other) if side == "home" else (other, own)):
            return None  # the events disagree about the score: say nothing rather than guess
    if own == 0 and other == 0:
        return "opening", side
    trailed = other - own
    if trailed == 1:
        return "level", side
    if trailed == 0:
        return "lead", side
    return ("extend" if trailed < 0 else "pull_back"), side


def context(moment: Moment, ctx: Context) -> str | None:
    """The context sentence of a moment, or None when it has none or the score state cannot be trusted."""
    last = ctx.by_id[moment.event_ids[-1]]
    key: str | None
    side: Team | None
    if moment.kind == "goal":
        key, side = _goal(last, ctx) or (None, None)
    elif moment.kind == "halftime":
        side = _leader(last)
        key = "break_lead" if side else "break_level"
    elif moment.kind == "fulltime":
        side = _leader(last)
        key = "end_win" if side else "end_level"
    else:
        return None
    if key is None:
        return None
    phrase = PHRASES[ctx.lang][key]
    return phrase.format(team=ctx.short(side)) if side else phrase
