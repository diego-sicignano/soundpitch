"""Pitch geometry shared by the generator, the moment detector and the renderer (SPEC §3)."""

from app.contracts import Event, Lane, Team


def attacks_right(team: Team, half: int) -> bool:
    """Home attacks left to right in the first half, right to left in the second."""
    return (team == "home") == (half == 1)


def progress(team: Team, half: int, x: int) -> int:
    """0 = own goal line, 100 = opponent's goal line."""
    return x if attacks_right(team, half) else 100 - x


def event_progress(event: Event) -> int:
    assert event.team is not None
    return progress(event.team, event.half, event.x)


def lane_of(y: int, team: Team, half: int) -> Lane:
    """Team-relative lane: attacking left to right, the team's left is the top of the picture."""
    top, bottom = ("left", "right") if attacks_right(team, half) else ("right", "left")
    if y < 35:
        return top
    if y > 65:
        return bottom
    return "centre"
