"""S34: the code-written summary of the match up to the end of a window (SPEC §19)."""

from app.contracts import Profile
from app.describer import TemplateDescriber
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, build_session
from app.recap import build
from app.stats import count

MATCH = generate_match(SEED)
PRESETS = {p.id: p for p in build_presets(MATCH)}
GOALS = [e for e in MATCH.events if e.kind == "goal"]


def goal_lines(recap):
    return [line for line in recap.lines if line.startswith(("Minute ", "Minuto "))]


def test_the_final_whistle_recap_gives_the_result_and_every_goal():
    recap = build(MATCH, PRESETS["final_whistle"], "en")
    assert recap.lines[0] == "Full-time: Northgate 2, Harbour 1."
    assert [line.split(":")[0] for line in goal_lines(recap)] == ["Minute 16", "Minute 52", "Minute 78"]
    assert goal_lines(recap)[0].startswith("Minute 16: Marsh scores for Northgate, set up by Adeyemi.")
    assert recap.minute == 90 and recap.lines[-1].startswith("Possession: ")


def test_a_window_lists_only_the_goals_up_to_its_end():
    first = build(MATCH, PRESETS["goal_1"], "en")
    assert first.lines[0] == "After 16 minutes: Northgate 1, Harbour 0."
    assert len(goal_lines(first)) == 1
    kickoff = build(MATCH, PRESETS["kickoff"], "en")
    assert kickoff.lines[0] == "After 2 minutes: Northgate 0, Harbour 0." and not goal_lines(kickoff)


def test_the_pressure_clause_follows_the_thresholds():
    for goal, line in zip(GOALS, goal_lines(build(MATCH, PRESETS["final_whistle"], "en")), strict=True):
        home, away = count([e for e in MATCH.events if e.id < goal.id])
        share = (home if goal.team == "home" else away).recent_possession
        if share >= 60:
            assert line.endswith(f"had {share}% of the passes in the five minutes before.") and "run of play" not in line
        elif share <= 40:
            assert "It came against the run of play: " in line and f"had {share}% of the passes" in line
        else:
            assert "% of the passes" not in line


def test_the_numbers_line_is_the_statistics_at_the_window_end():
    preset = PRESETS["goal_2"]
    home, away = count([e for e in MATCH.events if e.t <= preset.to_s])
    line = build(MATCH, preset, "en").lines[-1]
    assert line == (
        f"Possession: Northgate {home.possession}%, Harbour {away.possession}%. "
        f"Shots: {home.shots} to {away.shots}, on target {home.shots_on_target} to {away.shots_on_target}."
    )


def test_italian():
    recap = build(MATCH, PRESETS["final_whistle"], "it")
    assert recap.lines[0] == "Finale: Northgate 2, Harbour 1."
    assert goal_lines(recap)[0].startswith("Minuto 16: gol di Marsh per Northgate, assist di Adeyemi.")
    assert recap.lines[-1].startswith("Possesso: ") and " nello specchio " in recap.lines[-1]
    assert build(MATCH, PRESETS["goal_1"], "it").lines[0] == "Dopo 16 minuti: Northgate 1, Harbour 0."


def test_the_session_carries_its_recap():
    preset = PRESETS["goal_3"]
    session = build_session(MATCH, preset, Profile(lang="it"), TemplateDescriber())
    assert session.recap == build(MATCH, preset, "it")
