"""S17: the match as read-only MCP tools, through an in-memory MCP client session (SPEC §16)."""

import asyncio

from mcp.shared.memory import create_connected_server_and_client_session

from app.contracts import Commentary, Event, MatchHeader, MatchStats, Moment, Preset, Profile, Recap
from app.main import session_for
from app.match_gen import SEED, generate_match
from app.mcp_server import server
from app.moments import detect_moments
from app.pipeline import build_presets, window_of
from app.recap import build
from app.stats import count

MATCH = generate_match(SEED)
PRESETS = {p.id: p for p in build_presets(MATCH)}
TOOLS = {"list_presets", "get_match", "get_moments", "get_commentary", "get_stats", "get_events", "get_recap"}


def session_call(method, *args):
    async def run():
        async with create_connected_server_and_client_session(server) as client:
            return await getattr(client, method)(*args)

    return asyncio.run(run())


def call(tool, arguments=None):
    return session_call("call_tool", tool, arguments or {})


def error_text(result):
    assert result.isError
    return " ".join(part.text for part in result.content)


def test_the_tools_are_listed_with_input_schemas():
    tools = session_call("list_tools").tools
    assert {t.name for t in tools} == TOOLS
    assert all(t.inputSchema and t.description for t in tools)
    moments = next(t for t in tools if t.name == "get_moments")
    assert moments.inputSchema["properties"]["detail"]["enum"] == ["essential", "standard", "full"]


def test_presets_and_match_are_contracts():
    presets = [Preset.model_validate(p) for p in call("list_presets").structuredContent["result"]]
    assert [p.id for p in presets] == list(PRESETS)
    header = MatchHeader.model_validate(call("get_match").structuredContent)
    assert (header.home_goals, header.away_goals) == (2, 1)


def test_moments_follow_the_detail_and_the_focus():
    result = call("get_moments", {"preset": "goal_1", "detail": "essential"})
    moments = [Moment.model_validate(m) for m in result.structuredContent["result"]]
    assert moments == detect_moments(window_of(MATCH, PRESETS["goal_1"]), "essential")
    focused = call("get_moments", {"preset": "goal_1", "detail": "essential", "focus": 7, "focus_team": "home"})
    assert len(focused.structuredContent["result"]) > len(moments)


def test_the_commentary_is_the_verified_session():
    result = call("get_commentary", {"preset": "goal_2", "lang": "it"})
    commentary = Commentary.model_validate(result.structuredContent)
    session = session_for("goal_2", Profile(lang="it"))
    assert (commentary.cues, commentary.report) == (session.cues, session.report)
    assert commentary.preset == "goal_2" and commentary.lang == "it"


def test_the_stats_of_a_minute_are_the_counts_so_far():
    stats = MatchStats.model_validate(call("get_stats", {"minute": 16}).structuredContent)
    assert (stats.home, stats.away) == count([e for e in MATCH.events if e.minute <= 16])
    assert stats.minute == 16


def test_errors_carry_their_codes():
    assert "preset_not_found" in error_text(call("get_commentary", {"preset": "nope"}))
    assert "preset_not_found" in error_text(call("get_moments", {"preset": "nope"}))
    assert "invalid_parameter" in error_text(call("get_moments", {"preset": "goal_1", "focus": 7}))
    assert "invalid_parameter" in error_text(call("get_commentary", {"preset": "goal_1", "focus": 99, "focus_team": "home"}))
    for minute in (0, 91):
        assert "invalid_parameter" in error_text(call("get_stats", {"minute": minute}))


def test_events_and_recap():
    events = [Event.model_validate(e) for e in call("get_events", {"preset": "goal_1"}).structuredContent["result"]]
    assert events == window_of(MATCH, PRESETS["goal_1"])
    recap = Recap.model_validate(call("get_recap", {"preset": "final_whistle", "lang": "it"}).structuredContent)
    assert recap == build(MATCH, PRESETS["final_whistle"], "it")
    assert "preset_not_found" in error_text(call("get_recap", {"preset": "nope"}))
    assert "preset_not_found" in error_text(call("get_events", {"preset": "nope"}))


def test_the_match_report_prompt_relies_on_the_verified_tools():
    prompts = session_call("list_prompts").prompts
    assert [p.name for p in prompts] == ["match_report"]
    text = " ".join(m.content.text for m in session_call("get_prompt", "match_report", {"preset": "goal_1"}).messages)
    assert all(tool in text for tool in ("get_recap", "get_stats", "get_commentary")) and "goal_1" in text
