"""S13: the Microsoft Agent Framework workflow builds the same session as the plain pipeline (SPEC §12)."""

import importlib.util
import json
import sys
import threading

import pytest
from fastapi.testclient import TestClient

from app import main, workflow
from app.contracts import Profile, Session
from app.describer import Describer, FlawedDescriber, TemplateDescriber
from app.foundry import FoundryNotConfigured
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, build_session
from tests.test_foundry import Fake
from tests.test_replay import record

needs_sdk = pytest.mark.skipif(
    importlib.util.find_spec("agent_framework") is None,
    reason="the optional Agent Framework packages are not installed (backend/requirements-agents.txt)",
)
MATCH = generate_match(SEED)
PRESETS = {p.id: p for p in build_presets(MATCH)}
client = TestClient(main.app)


class RaisesOnce(Describer):
    def __init__(self):
        self.calls = 0

    def describe(self, moments, ctx, feedback, attempt):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("the model did not answer")
        return TemplateDescriber().describe(moments, ctx, feedback, attempt)


def without_trace(session: Session) -> Session:
    return session.model_copy(update={"trace": []})


def both(describer_factory, preset="goal_1", profile=None):
    profile = profile or Profile(detail="full")
    plain = build_session(MATCH, PRESETS[preset], profile, describer_factory())
    flow = workflow.build_session(MATCH, PRESETS[preset], profile, describer_factory())
    return plain, flow


@needs_sdk
@pytest.mark.parametrize(
    "factory",
    [TemplateDescriber, lambda: FlawedDescriber(bad_attempts=1), lambda: FlawedDescriber(bad_attempts=3)],
    ids=["scripted", "bad_then_good", "always_bad"],
)
@pytest.mark.parametrize("preset", ["kickoff", "goal_2", "final_whistle"])
@pytest.mark.parametrize("lang", ["en", "it"])
def test_the_workflow_builds_the_same_session_as_the_plain_pipeline(factory, preset, lang):
    plain, flow = both(factory, preset, Profile(detail="standard", lang=lang, calm=(lang == "it")))
    assert without_trace(flow) == without_trace(plain)
    assert flow.cues and flow.report.overlaps == 0


@needs_sdk
def test_the_trace_names_the_executors_and_the_retry_loop_shows():
    clean = workflow.build_session(MATCH, PRESETS["goal_1"], Profile(), TemplateDescriber())
    assert [t.executor for t in clean.trace] == [
        *["MomentDetector", "Describer", "Verifier", "TimingPlanner", "Analyst", "AnalysisChecker"],
    ]
    retried = workflow.build_session(MATCH, PRESETS["goal_1"], Profile(), FlawedDescriber(bad_attempts=1))
    assert [t.executor for t in retried.trace] == [
        *["MomentDetector", "Describer", "Verifier", "Describer", "Verifier", "TimingPlanner"],
        *["Analyst", "AnalysisChecker"],
    ]
    assert [t.attempt for t in retried.trace if t.executor == "Describer"] == [1, 2]
    failed = workflow.build_session(MATCH, PRESETS["goal_1"], Profile(), FlawedDescriber(bad_attempts=3))
    assert [t.executor for t in failed.trace] == [
        *["MomentDetector", "Describer", "Verifier", "Describer", "Verifier", "Describer", "Verifier"],
        *["Fallback", "TimingPlanner", "Analyst", "AnalysisChecker"],
    ]
    assert failed.report.fallback == failed.report.moments and failed.report.attempts == 3
    plain = build_session(MATCH, PRESETS["goal_1"], Profile(), TemplateDescriber())
    assert all(t.executor is None for t in plain.trace)


@needs_sdk
def test_a_describer_that_raises_once_is_retried_like_a_rejected_attempt():
    plain, flow = both(RaisesOnce)
    assert without_trace(flow) == without_trace(plain)
    assert flow.report.attempts == 2 and flow.report.verified == flow.report.moments
    assert [(t.executor, t.status) for t in flow.trace if t.step == "describer"][:2] == [
        ("Describer", "failed"),
        ("Describer", "ok"),
    ]


@needs_sdk
def test_recorded_model_replies_flow_through_the_workflow_and_a_liar_is_rejected(tmp_path):
    from app.replay import ReplayDescriber

    store, _, _, _ = record(tmp_path)
    plain, flow = both(lambda: ReplayDescriber(store))
    assert without_trace(flow) == without_trace(plain) and flow.report.fallback == 0

    def liar(n, payload):
        items = [{"moment_id": m["moment_id"], "full": "Zorro scores.", "short": "Zorro."} for m in payload["moments"]]
        return json.dumps({"items": items})

    liar_dir = tmp_path / "liar"
    liar_dir.mkdir()
    store, _, _, _ = record(liar_dir, fake=Fake(liar))
    lied = workflow.build_session(MATCH, PRESETS["goal_1"], Profile(detail="full"), ReplayDescriber(store))
    assert all("Zorro" not in c.text for c in lied.cues) and lied.report.moments == lied.report.cues


@needs_sdk
def test_a_template_fallback_that_does_not_verify_stops_the_workflow_like_the_pipeline(monkeypatch):
    from app.verifier import Verifier

    monkeypatch.setattr(Verifier, "check", lambda self, moment, description: ["always wrong"])
    with pytest.raises(RuntimeError, match="template fallback must verify"):
        build_session(MATCH, PRESETS["goal_1"], Profile(), TemplateDescriber())
    with pytest.raises(Exception, match="template fallback must verify"):
        workflow.build_session(MATCH, PRESETS["goal_1"], Profile(), TemplateDescriber())


@needs_sdk
def test_concurrent_requests_each_get_their_own_correct_session():
    expected = without_trace(build_session(MATCH, PRESETS["goal_1"], Profile(), TemplateDescriber()))
    results: list[Session] = []

    def go():
        results.append(workflow.build_session(MATCH, PRESETS["goal_1"], Profile(), TemplateDescriber()))

    threads = [threading.Thread(target=go) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 6 and all(without_trace(r) == expected for r in results)


@needs_sdk
def test_the_api_serves_the_workflows_session_when_selected(monkeypatch):
    main.session_for.cache_clear()
    plain = client.get("/api/session", params={"preset": "goal_3", "lang": "it"}).json()
    main.session_for.cache_clear()
    monkeypatch.setenv("SOUNDPITCH_ORCHESTRATOR", "workflow")
    try:
        flow = client.get("/api/session", params={"preset": "goal_3", "lang": "it"}).json()
        sheet = client.get("/api/cuesheet", params={"preset": "goal_3", "lang": "it"})
    finally:
        main.session_for.cache_clear()
    assert sheet.status_code == 200
    assert {k: v for k, v in flow.items() if k != "trace"} == {k: v for k, v in plain.items() if k != "trace"}
    assert next(t["executor"] for t in flow["trace"]) == "MomentDetector"


def test_a_missing_package_is_named_with_the_command_that_installs_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "agent_framework", None)  # an import now fails, installed or not
    with pytest.raises(FoundryNotConfigured, match=r"pip install -r backend/requirements-agents\.txt"):
        workflow.build_session(MATCH, PRESETS["goal_1"], Profile(), TemplateDescriber())
    monkeypatch.setenv("SOUNDPITCH_ORCHESTRATOR", "workflow")
    main.session_for.cache_clear()
    try:
        response = client.get("/api/session")
    finally:
        main.session_for.cache_clear()
    assert response.status_code == 503 and response.json()["code"] == "llm_not_configured"
    assert "requirements-agents.txt" in response.json()["message"]


def test_an_unknown_orchestrator_is_named(monkeypatch):
    monkeypatch.setenv("SOUNDPITCH_ORCHESTRATOR", "crew")
    main.session_for.cache_clear()
    try:
        response = client.get("/api/session")
    finally:
        main.session_for.cache_clear()
    assert response.status_code == 503 and "SOUNDPITCH_ORCHESTRATOR" in response.json()["message"]


def test_the_plain_pipeline_needs_no_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "agent_framework", None)
    monkeypatch.delenv("SOUNDPITCH_ORCHESTRATOR", raising=False)
    main.session_for.cache_clear()
    try:
        assert client.get("/api/session").status_code == 200
    finally:
        main.session_for.cache_clear()


@needs_sdk
def test_the_analyst_retry_runs_as_an_edge_and_matches_the_plain_pipeline():
    from app.analysis import FlawedAnalyst

    flow = workflow.build_session(MATCH, PRESETS["final_whistle"], Profile(), TemplateDescriber(), FlawedAnalyst(1))
    plain = build_session(MATCH, PRESETS["final_whistle"], Profile(), TemplateDescriber(), FlawedAnalyst(1))
    assert without_trace(flow) == without_trace(plain)
    assert [t.executor for t in flow.trace][-4:] == ["Analyst", "AnalysisChecker", "Analyst", "AnalysisChecker"]
    assert flow.analysis.status == "verified" and flow.analysis.attempts == 2 and flow.analysis.rejected > 0
