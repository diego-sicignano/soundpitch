"""S16 (offline part): the smoke check passes on a healthy server and names what is wrong otherwise."""

from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app import smoke
from app.main import app


def test_a_healthy_server_passes_in_every_mode(monkeypatch):
    for mode in ("scripted", "replay"):
        monkeypatch.setenv("SOUNDPITCH_LLM", mode)
        assert smoke.check(TestClient(app)) == []


def test_a_server_that_is_down_is_reported_not_raised():
    def refuse(request):
        raise httpx.ConnectError("down")

    client = httpx.Client(transport=httpx.MockTransport(refuse), base_url="http://server")
    assert smoke.check(client) == ["the server could not be read (ConnectError)"]


def test_an_unhealthy_server_and_a_broken_session_are_named():
    def unhealthy(request):
        return httpx.Response(503)

    bad = httpx.Client(transport=httpx.MockTransport(unhealthy), base_url="http://server")
    assert smoke.check(bad) == ["/api/health answered 503"]

    real = TestClient(app)

    def broken_session(request):
        if request.url.path == "/api/session":
            return httpx.Response(200, json={"preset": "x"})
        return httpx.Response(200, content=real.get(request.url.path).content)

    client = httpx.Client(transport=httpx.MockTransport(broken_session), base_url="http://server")
    problems = smoke.check(client)
    assert problems and all("unreadable session" in p for p in problems)


def test_the_command_exits_non_zero_when_something_is_wrong(capsys):
    assert smoke.main(["smoke"]) == 2
    assert smoke.main(["smoke", "http://127.0.0.1:9"]) == 1  # nothing listens on the discard port
    assert "FAIL" in capsys.readouterr().out


# ---- the files that publish the image (S16, offline part) ------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]


def job(name: str) -> str:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    start = text.index(f"\n  {name}:")
    rest = text[start + 1 :]
    following = [rest.index(f"\n  {other}:") for other in ("backend", "sdk", "e2e", "docker", "publish") if other != name and f"\n  {other}:" in rest]
    return rest[: min(following)] if following else rest


def test_the_workflow_token_is_read_only_unless_a_job_asks_for_more():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    top = ci.split("\njobs:")[0]  # the part before any job: it applies to all of them
    assert "\npermissions:\n  contents: read\n" in top.replace("\r\n", "\n")


def test_the_image_is_linked_to_the_repository_so_ghcr_can_show_it_public():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert 'LABEL org.opencontainers.image.source="https://github.com/diego-sicignano/soundpitch"' in dockerfile


def test_a_push_never_publishes_an_image_only_a_deliberate_manual_run_on_main_does():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    on = ci.split("jobs:")[0]
    assert "push:" in on and "pull_request:" in on and "workflow_dispatch:" in on  # ordinary CI is kept, a manual run is added
    publish = job("publish")
    condition = publish.split("if:")[1].splitlines()[0]
    assert "github.event_name == 'workflow_dispatch'" in condition and "github.ref == 'refs/heads/main'" in condition
    assert "'push'" not in condition and "pull_request" not in condition


def test_only_a_tested_main_commit_is_published_and_only_with_the_built_in_token():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    publish = job("publish")
    for needed in ("backend", "sdk", "e2e", "docker"):
        assert needed in publish.split("needs:")[1].split("\n")[0]
    assert "github.ref == 'refs/heads/main'" in publish
    assert "packages: write" in publish and "contents: read" in publish
    assert "packages: write" not in ci.replace(publish, "")  # no other job may write packages
    assert ci.count("secrets.") == 1 and "secrets.GITHUB_TOKEN" in publish  # no other secret anywhere
    assert "--password-stdin" in publish and "ghcr.io" in publish
    assert ":latest" not in publish and "${GITHUB_SHA}" in publish  # an immutable tag, never a moving one
    assert "azure/login" not in ci and "AZURE_" not in ci  # CI holds no Azure identity


def test_the_judges_image_runs_the_agent_framework_workflow_on_recorded_replies():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "SOUNDPITCH_LLM=replay" in dockerfile and "SOUNDPITCH_ORCHESTRATOR=workflow" in dockerfile
    assert "pip install -r requirements-workflow.txt -r requirements-mcp.txt" in dockerfile  # the MCP server too (D32)
    workflow = (ROOT / "backend" / "requirements-workflow.txt").read_text(encoding="utf-8")
    agents = (ROOT / "backend" / "requirements-agents.txt").read_text(encoding="utf-8")
    assert "agent-framework-core==" in workflow and "-r requirements.txt" in workflow
    assert "-r requirements-workflow.txt" in agents and "agent-framework-core" not in agents  # one pin, one place

