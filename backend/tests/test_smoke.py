"""S16 (offline part): the smoke check passes on a healthy server and names what is wrong otherwise."""

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
