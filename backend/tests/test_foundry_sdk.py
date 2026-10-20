"""The adapter against the real Microsoft Agent Framework types, with the network call stubbed.

Skipped unless `pip install -r requirements-agents.txt` was done: the core tests never need the SDK.
What this proves: the adapter builds the request the SDK documents (messages, `instructions`,
`response_format`), reads a typed or untyped answer, reuses one client on one loop, and times out.
What it cannot prove: that a real deployment accepts the request. That is `app.foundry_run` (S12).
"""

import asyncio
import json
import threading
from typing import ClassVar

import pytest

pytest.importorskip("agent_framework.foundry")

import agent_framework as af
import agent_framework.foundry as af_foundry

from app.foundry import MAX_OUTPUT_TOKENS, AgentFrameworkClient, Reply, Wordings

REPLY = json.dumps({"items": [{"moment_id": 1, "full": "Foul by Costa of Harbour.", "short": "Foul."}]})


class StubFoundryChatClient:
    """Stands in for FoundryChatClient: records how it was built and called, answers like the SDK."""

    built: ClassVar[list[dict]] = []
    calls: ClassVar[list[dict]] = []
    answer = REPLY
    delay = 0.0
    loops: ClassVar[list[int]] = []
    threads: ClassVar[list[int]] = []

    usage: ClassVar[dict | None] = None

    def __init__(self, **kwargs):
        type(self).built.append(kwargs)

    async def get_response(self, messages, *, options=None, **kwargs):
        type(self).calls.append({"messages": messages, "options": options})
        type(self).loops.append(id(asyncio.get_running_loop()))
        type(self).threads.append(threading.get_ident())
        await asyncio.sleep(type(self).delay)
        return af.ChatResponse(
            messages=[af.Message(role="assistant", contents=[type(self).answer])],
            response_format=(options or {}).get("response_format"),
            usage_details=type(self).usage,
        )


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    for attr in ("built", "calls", "loops", "threads"):
        setattr(StubFoundryChatClient, attr, [])
    StubFoundryChatClient.answer, StubFoundryChatClient.delay = REPLY, 0.0
    StubFoundryChatClient.usage = None
    monkeypatch.setattr(af_foundry, "FoundryChatClient", StubFoundryChatClient)


def client(**kw):
    return AgentFrameworkClient("https://example.services.ai.azure.com/api/projects/demo", "demo-model", **kw)


def test_the_request_is_the_one_the_sdk_documents():
    text = client().complete("SYSTEM RULES", '{"moments": []}').text
    assert json.loads(text)["items"][0]["moment_id"] == 1
    built = StubFoundryChatClient.built[0]
    assert built["project_endpoint"].startswith("https://") and built["model"] == "demo-model"
    assert type(built["credential"]).__module__.startswith("azure.identity.aio")  # async pairs with the async SDK
    sent = StubFoundryChatClient.calls[0]
    assert sent["options"]["instructions"] == "SYSTEM RULES" and sent["options"]["response_format"] is Wordings
    assert sent["options"]["max_tokens"] == MAX_OUTPUT_TOKENS
    (message,) = sent["messages"]
    assert message.role == "user" and message.text == '{"moments": []}'


def test_a_typed_answer_comes_back_as_json_text_the_describer_parses_again():
    text = client().complete("s", "u").text
    assert Wordings.model_validate_json(text).items[0].full == "Foul by Costa of Harbour."


def test_an_answer_that_is_not_the_schema_is_returned_as_text_for_the_verifier_to_reject():
    StubFoundryChatClient.answer = "I cannot help with that."
    assert client().complete("s", "u").text == "I cannot help with that."


def test_the_usage_the_provider_reports_comes_back_with_the_text():
    StubFoundryChatClient.usage = {"input_token_count": 2100, "output_token_count": 310, "total_token_count": 2410}
    answer = client().complete("s", "u")
    assert isinstance(answer, Reply) and (answer.input_tokens, answer.output_tokens) == (2100, 310)
    assert json.loads(answer.text) == json.loads(REPLY)


@pytest.mark.parametrize("usage", [None, {}, {"input_token_count": None}, {"input_token_count": -1, "output_token_count": "many"}])
def test_missing_or_malformed_usage_comes_back_as_unknown_not_as_zero(usage):
    StubFoundryChatClient.usage = usage
    answer = client().complete("s", "u")
    assert answer.input_tokens is None and answer.output_tokens is None


def test_one_client_and_one_loop_serve_every_call_from_any_thread():
    c = client()
    results = []
    workers = [threading.Thread(target=lambda: results.append(c.complete("s", "u"))) for _ in range(4)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    c.complete("s", "u")
    assert len(results) == 4 and len(StubFoundryChatClient.built) == 1
    assert len(set(StubFoundryChatClient.loops)) == 1 and len(set(StubFoundryChatClient.threads)) == 1
    assert StubFoundryChatClient.threads[0] != threading.get_ident()


def test_a_call_that_is_too_slow_raises_timeout_error():
    StubFoundryChatClient.delay = 2.0
    with pytest.raises(TimeoutError):
        client(timeout_s=0.1).complete("s", "u")


def test_without_the_package_the_error_says_how_to_install_it(monkeypatch):
    import builtins

    from app.foundry import FoundryNotConfigured

    real = builtins.__import__

    def refuse(name, *a, **k):
        if name.startswith("agent_framework"):
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(FoundryNotConfigured, match="requirements-agents.txt"):
        client()
