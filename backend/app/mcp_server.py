"""The match as read-only MCP tools for any agent: GitHub Copilot agent mode or any other MCP client (SPEC §16).

Run over stdio: `python -m app.mcp_server` (in the judges' image: `docker run -i --rm <image> python -m app.mcp_server`).
Every tool answers from the same pipeline as the HTTP API, so an agent gets only verified sentences and numbers
counted by code; nothing here writes, calls a model of its own or prints to standard output.
"""

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app import main, recap, stats
from app.contracts import (
    Commentary,
    Detail,
    Event,
    Lang,
    MatchHeader,
    MatchStats,
    Moment,
    Preset,
    Profile,
    Recap,
    Team,
)
from app.foundry import FoundryNotConfigured
from app.moments import detect_moments, focus_of
from app.pipeline import window_of

server = FastMCP(
    "soundpitch",
    instructions=(
        "A synthetic football match (Northgate Red v Harbour Blue) as verified audio-description commentary and "
        "match statistics. Use list_presets for the windows; quote get_commentary cues as they are."
    ),
)


def _checked(preset: str, focus: int | None, focus_team: Team | None) -> None:
    if preset not in main.PRESETS:
        raise ToolError(f"preset_not_found: unknown preset {preset!r}; use list_presets")
    problem = main.focus_problem(focus, focus_team)
    if problem:
        raise ToolError(f"invalid_parameter: {problem}")


@server.tool()
def list_presets() -> list[Preset]:
    """The match windows that can be described: kick-off, each goal and the final whistle."""
    return list(main.PRESETS.values())


@server.tool()
def get_match() -> MatchHeader:
    """Teams, squads (shirt, surname, role), the final score and the goals."""
    return main.get_match()


@server.tool()
def get_moments(
    preset: str, detail: Detail = "standard", focus: int | None = None, focus_team: Team | None = None
) -> list[Moment]:
    """The window's moments with their priority (3 must be said). focus_team follows a club, with focus one player."""
    _checked(preset, focus, focus_team)
    followed = focus_of(Profile(detail=detail, focus=focus, focus_team=focus_team))
    return detect_moments(window_of(main.MATCH, main.PRESETS[preset]), detail, followed)


@server.tool()
def get_commentary(
    preset: str,
    detail: Detail = "standard",
    lang: Lang = "en",
    focus: int | None = None,
    focus_team: Team | None = None,
) -> Commentary:
    """The timed commentary of a window: every sentence checked against the match events, and the report."""
    _checked(preset, focus, focus_team)
    try:
        session = main.session_for(preset, Profile(detail=detail, lang=lang, focus=focus, focus_team=focus_team))
    except FoundryNotConfigured as exc:
        raise ToolError(f"llm_not_configured: {exc}") from exc
    return Commentary(preset=session.preset, lang=session.lang, cues=session.cues, report=session.report)


@server.tool()
def get_stats(minute: int) -> MatchStats:
    """Possession (share of passes), passes, pass accuracy and length, shots and balls won, from kick-off to the
    end of a minute (1 to 90)."""
    if not 1 <= minute <= 90:
        raise ToolError("invalid_parameter: minute must be 1 to 90")
    home, away = stats.count([e for e in main.MATCH.events if e.minute <= minute])
    return MatchStats(minute=minute, home=home, away=away)


@server.tool()
def get_events(preset: str) -> list[Event]:
    """The window's synthetic match events as ingested: passes, shots, tackles, set pieces, whistles, with x and y."""
    _checked(preset, None, None)
    return window_of(main.MATCH, main.PRESETS[preset])


@server.tool()
def get_recap(preset: str, lang: Lang = "en") -> Recap:
    """The summary of the match up to the end of a window, written by code: the score, each goal with its assist
    and the pressure before it, and the numbers."""
    _checked(preset, None, None)
    return recap.build(main.MATCH, main.PRESETS[preset], lang)


@server.prompt()
def match_report(preset: str, lang: Lang = "en") -> str:
    """A short match report built only from verified output."""
    return (
        f"Write a short match report for the SoundPitch window '{preset}' in {'Italian' if lang == 'it' else 'English'}. "
        f"Call get_recap(preset='{preset}', lang='{lang}') for the result and the goals, get_stats for the numbers at "
        f"any minute, and get_commentary(preset='{preset}', lang='{lang}') for the moments as they were described. "
        "Quote their sentences and numbers as they are: they are checked against the match events. "
        "Do not add names, minutes or figures that the tools did not return."
    )


if __name__ == "__main__":
    server.run()  # stdio
