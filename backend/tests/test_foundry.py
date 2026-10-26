"""S11: the Foundry describer against a fake model client.

The fake plays the model. It reads the prompt exactly as a model would (a JSON document of moments),
so these tests check what the prompt holds as well as what happens to the answers. Nothing here needs
the Foundry SDK or a network.
"""

import importlib.util
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import foundry
from app.contracts import Profile
from app.describer import Context, TemplateDescriber, facts
from app.foundry import FoundryDescriber, FoundryNotConfigured, Reply, build_prompt
from app.match_gen import SEED, generate_match
from app.moments import detect_moments
from app.pipeline import build_presets, build_session
from app.usage import UsageLedger, cost_micro_eur, estimate_input_tokens

MATCH = generate_match(SEED)
PRESET = next(p for p in build_presets(MATCH) if p.id == "goal_1")
PROFILE = Profile(detail="full", lang="en")


DB = {}  # the database file of the running test


@pytest.fixture(autouse=True)
def _database(tmp_path):
    DB["path"] = tmp_path / "usage.sqlite"
    yield
    DB.clear()


class Clock:
    def __init__(self, now=1_785_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def ledger_for(clock=None, **limits):
    base = {"per_minute": 1000, "per_day": 1000, "tokens_per_day": 10**9, "eur_per_month": 100.0}
    return UsageLedger(DB["path"], clock=clock or time.time, **{**base, **limits})


def describer_for(client, timeout_s=foundry.TIMEOUT_S, clock=None, **limits):
    return FoundryDescriber(client, ledger_for(clock, **limits), timeout_s=timeout_s)


def window(preset=PRESET):
    return [e for e in MATCH.events if preset.from_s <= e.t <= preset.to_s]


def reply(items) -> str:
    return json.dumps({"items": list(items)})


def examples(payload, pick=0):
    """A correct reply: the first example sentence of every moment asked about."""
    return reply(
        {
            "moment_id": m["moment_id"],
            "full": m["examples"][pick % len(m["examples"])]["full"],
            "short": m["examples"][pick % len(m["examples"])]["short"],
        }
        for m in payload["moments"]
    )


class Fake:
    """A model client that records every call and answers with `script(call_number, payload)`."""

    def __init__(self, script=None):
        self.script = script or (lambda n, payload: examples(payload))
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.script(len(self.calls), json.loads(user))


def session(client, profile=PROFILE, preset=PRESET, **kw):
    describer = describer_for(client, **kw)
    return build_session(MATCH, preset, profile, describer), describer


def n_moments(profile=PROFILE, preset=PRESET):
    return len(detect_moments(window(preset), profile.detail))


# ---- the happy path and the pipeline's own guarantees ----------------------------------------------


def test_correct_replies_are_verified_at_the_first_attempt_with_one_call_per_chunk():
    fake = Fake()
    s, _ = session(fake)
    total = n_moments()
    assert s.report.moments == total > 0
    assert s.report.verified == total and s.report.fallback == 0 and s.report.attempts == 1
    assert len(fake.calls) == -(-total // foundry.MAX_BATCH)
    assert all(c.status == "verified" for c in s.cues)


def test_wrong_names_are_rejected_and_the_retry_carries_the_verifiers_issues():
    def script(n, payload):
        if n > 1:
            return examples(payload)
        out = []
        for m in payload["moments"]:
            base = m["examples"][0]
            player = m.get("player")

            def swap(text, p=player):
                return text.replace(p, "Rossi" if p != "Rossi" else "Silva") if p else text

            out.append({"moment_id": m["moment_id"], "full": swap(base["full"]), "short": swap(base["short"])})
        return reply(out)

    fake = Fake(script)
    s, _ = session(fake)
    assert s.report.attempts == 2 and s.report.fallback == 0
    assert s.report.verified == s.report.moments
    retry = json.loads(fake.calls[1][1])
    assert retry["moments"] and all(m["issues"] for m in retry["moments"])
    assert len(retry["moments"]) < s.report.moments  # only the moments that were rejected
    assert any("not allowed" in i or "not in this moment" in i for m in retry["moments"] for i in m["issues"])


@pytest.mark.parametrize(
    "bad",
    ["not json at all", "", "[]", '{"items": "no"}', '{"items": [{"moment_id": 1}]}', "null"],
)
def test_a_reply_that_does_not_parse_into_the_contract_is_a_failed_attempt(bad):
    fake = Fake(lambda n, payload: bad if n == 1 else examples(payload))
    s, _ = session(fake)
    assert s.report.attempts == 2 and s.report.fallback == 0 and s.report.verified == s.report.moments
    assert any(t.step == "describer" and t.status == "failed" and t.attempt == 1 for t in s.trace)


def test_a_json_reply_in_a_markdown_fence_is_read():
    fake = Fake(lambda n, payload: "```json\n" + examples(payload) + "\n```")
    s, _ = session(fake)
    assert s.report.attempts == 1 and s.report.verified == s.report.moments


def test_an_exception_from_the_client_is_a_failed_attempt_not_a_failed_session():
    def script(n, payload):
        if n == 1:
            raise ConnectionError("network down")
        return examples(payload)

    s, _ = session(Fake(script))
    assert s.report.attempts == 2 and s.report.verified == s.report.moments
    assert any(t.detail == "ConnectionError" and t.status == "failed" for t in s.trace)


def test_a_call_that_is_too_slow_is_a_failed_attempt():
    def script(n, payload):
        if n == 1:
            time.sleep(0.6)
        return examples(payload)

    started = time.monotonic()
    s, _ = session(Fake(script), timeout_s=0.3)  # wide enough for a slow CI runner's second, fast call
    assert time.monotonic() - started < 5
    assert s.report.attempts == 2 and s.report.verified == s.report.moments
    assert any(t.detail == "TimeoutError" and t.status == "failed" for t in s.trace)


def test_three_bad_attempts_end_in_the_verified_template_fallback():
    fake = Fake(lambda n, payload: "nonsense")
    s, _ = session(fake)
    clean = build_session(MATCH, PRESET, PROFILE, TemplateDescriber())
    assert len(fake.calls) == 3 * -(-s.report.moments // foundry.MAX_BATCH)
    assert s.report.attempts == 3 and s.report.fallback == s.report.moments and s.report.verified == 0
    assert [c.text for c in s.cues] == [c.text for c in clean.cues]
    assert all(c.status == "fallback" for c in s.cues)


def test_a_model_that_answers_for_only_some_moments_is_retried_for_the_rest():
    def script(n, payload):
        moments = payload["moments"]
        if n == 1:
            moments = moments[: len(moments) // 2]
        return reply(
            {"moment_id": m["moment_id"], "full": m["examples"][0]["full"], "short": m["examples"][0]["short"]}
            for m in moments
        )

    fake = Fake(script)
    s, _ = session(fake)
    assert s.report.attempts == 2 and s.report.verified == s.report.moments and s.report.fallback == 0
    assert len(json.loads(fake.calls[1][1])["moments"]) == s.report.moments - s.report.moments // 2


def test_unknown_moments_duplicates_and_extra_fields_are_ignored_and_refs_are_the_codes():
    def script(n, payload):
        items = []
        for m in payload["moments"]:
            ex = m["examples"][0]
            items.append(
                {
                    "moment_id": m["moment_id"],
                    "full": ex["full"],
                    "short": ex["short"],
                    "refs": [{"event_id": 1, "field": "kind", "value": "goal"}],
                    "lang": "it",
                    "team": "x",
                }
            )
            items.append({"moment_id": m["moment_id"], "full": "Goal! Smith scores.", "short": "Goal!"})
        items.append({"moment_id": 99999, "full": "Goal!", "short": "Goal!"})  # unknown moment
        return reply(items)

    describer = describer_for(Fake(script))
    ctx = Context(MATCH, "en")
    moments = detect_moments(window(), "full")
    described = describer.describe(moments, ctx, {}, 1)
    assert set(described) == {m.id for m in moments}
    for m in moments:
        d = described[m.id]
        assert d.refs == facts(m, ctx).refs and d.lang == "en" and d.moment_id == m.id
        assert "Smith" not in d.full
    s = build_session(MATCH, PRESET, PROFILE, describer_for(Fake(script)))
    assert s.report.verified == s.report.moments


# ---- hostile replies never become verified --------------------------------------------------------


def test_the_adversarial_alterations_of_s19_never_become_verified():
    from app.verifier import Verifier
    from tests.test_grounding import MUTATIONS, Case, variants

    ctx = Context(MATCH, "en")
    moments = {m.id: m for m in detect_moments(window(), "full")}
    templates = TemplateDescriber().describe(list(moments.values()), ctx, {}, 1)
    cases = {mid: Case(SEED, ctx, Verifier(ctx), m, templates[mid]) for mid, m in moments.items()}
    checked = verified_somewhere = 0
    for name, mutate in MUTATIONS.items():
        altered = {}
        for mid, case in cases.items():
            made = [d for d in mutate(case) if d != case.desc and d.moment_id == mid and d.lang == "en"]
            if made:
                altered[mid] = made[0]

        def script(n, payload, altered=altered):
            items = []
            for m in payload["moments"]:
                d = altered.get(m["moment_id"])
                ex = m["examples"][0]
                items.append(
                    {
                        "moment_id": m["moment_id"],
                        "full": d.full if d else ex["full"],
                        "short": d.short if d else ex["short"],
                    }
                )
            return reply(items)

        DB["path"] = DB["path"].with_name(f"{name}.sqlite")  # a stored reply for the same window would be replayed
        s = build_session(MATCH, PRESET, PROFILE, describer_for(Fake(script)))
        verified_somewhere += s.report.verified
        for cue in s.cues:
            if cue.moment_id in altered and cue.status == "verified":
                full_ok, short_ok = variants(moments[cue.moment_id], ctx)
                assert (cue.text.removesuffix(" " + cue.context) if cue.context else cue.text) in (full_ok if cue.variant == "full" else short_ok), (name, cue)
            checked += cue.moment_id in altered
    assert checked > 50 and verified_somewhere > 0  # unaltered moments do pass: the test is not vacuous


def test_valid_json_alone_never_makes_a_sentence_verified():
    def script(n, payload):
        return reply(
            {"moment_id": m["moment_id"], "full": "Penalty! Smith scores for Nowhere.", "short": "Goal!"}
            for m in payload["moments"]
        )

    s, _ = session(Fake(script))
    assert s.report.verified == 0 and s.report.fallback == s.report.moments
    assert not any("Smith" in c.text for c in s.cues)


# ---- the prompt ------------------------------------------------------------------------------------


def test_the_prompt_holds_the_facts_of_the_moments_and_nothing_else():
    ctx = Context(MATCH, "en")
    moments = detect_moments(window(), "full")
    system, user = build_prompt(moments, ctx, {})
    payload = json.loads(user)
    assert [m["moment_id"] for m in payload["moments"]] == [m.id for m in moments]
    involved = set().union(*(ctx.involved(m) for m in moments))
    outsiders = set(ctx.all_names) - involved
    assert outsiders  # the window does not involve everybody
    text = system + user
    assert not any(name in text for name in outsiders)
    assert "refs" not in text and "event_id" not in text and "shirt" not in text.lower()
    first = payload["moments"][0]
    assert {"moment_id", "kind", "phrases", "words", "positions", "examples"} <= set(first)
    goal = next(m for m in payload["moments"] if m["kind"].startswith("goal"))
    f = facts(next(m for m in moments if m.id == goal["moment_id"]), ctx)
    assert goal["phrases"]["score"] == f.fields["score"] and goal["player"] == f.fields["p"]
    assert payload["language"] == "English"
    assert "English" in system and "JSON" in system
    assert payload["items_expected"] == len(moments)  # a real model answered for 1 moment of 10 without this
    assert "EVERY moment" in system


def test_the_italian_prompt_speaks_italian_and_offers_italian_examples():
    ctx = Context(MATCH, "it")
    moments = detect_moments(window(), "full")
    _, user = build_prompt(moments, ctx, {})
    payload = json.loads(user)
    assert payload["language"] == "Italian"
    goal = next(m for m in payload["moments"] if m["kind"].startswith("goal"))
    assert any("Gol!" in e["full"] or "Rete!" in e["full"] for e in goal["examples"])


def test_the_retry_prompt_lists_only_the_rejected_moments_with_their_issues():
    ctx = Context(MATCH, "en")
    moments = detect_moments(window(), "full")[:3]
    feedback = {moments[1].id: ["'x' is not allowed"], moments[2].id: ["bad"]}
    _, user = build_prompt(moments[1:], ctx, feedback)
    payload = json.loads(user)
    assert [m["moment_id"] for m in payload["moments"]] == [moments[1].id, moments[2].id]
    assert payload["moments"][0]["issues"] == ["'x' is not allowed"]


# ---- cost: chunks, the cap and the cache ------------------------------------------------------------


def test_a_long_window_is_asked_in_chunks_of_at_most_twenty_moments():
    ctx = Context(MATCH, "en")
    moments = detect_moments(MATCH.events, "full")[:100]
    fake = Fake()
    described = describer_for(fake).describe(moments, ctx, {}, 1)
    sizes = [len(json.loads(u)["moments"]) for _, u in fake.calls]
    assert sizes == [20] * 5 and len(described) == 100


def test_over_the_cap_the_window_is_described_by_templates_and_the_trace_says_so():
    goal_2 = next(p for p in build_presets(MATCH) if p.id == "goal_2")
    goal_3 = next(p for p in build_presets(MATCH) if p.id == "goal_3")
    fake, clock = Fake(), Clock()
    describer = describer_for(fake, clock=clock, per_minute=1)
    first = build_session(MATCH, PRESET, PROFILE, describer)
    second = build_session(MATCH, goal_2, PROFILE, describer)
    assert len(fake.calls) == 1
    assert first.report.verified == first.report.moments
    assert second.report.fallback == 0 and second.report.verified == second.report.moments
    assert any("llm budget exhausted: templates (minute)" in t.detail for t in second.trace)
    assert not any("budget" in t.detail for t in first.trace)
    clean = build_session(MATCH, goal_2, PROFILE, TemplateDescriber())
    assert [c.text for c in second.cues] == [c.text for c in clean.cues]
    clock.now += 61  # a minute later
    third = build_session(MATCH, goal_3, PROFILE, describer)
    assert len(fake.calls) == 2 and not any("budget" in t.detail for t in third.trace)


def test_speech_rate_ball_sound_and_calm_mode_never_cost_a_second_call():
    fake = Fake()
    describer = describer_for(fake)
    build_session(MATCH, PRESET, PROFILE, describer)
    calls = len(fake.calls)
    for profile in (
        Profile(detail="full", lang="en", rate=1.5),
        Profile(detail="full", lang="en", calm=True),
        Profile(detail="full", lang="en", earcons=False, rate=0.7),
    ):
        again = build_session(MATCH, PRESET, profile, describer)
        assert again.report.verified == again.report.moments
    assert len(fake.calls) == calls


def test_a_rejected_but_parsable_window_is_replayed_and_an_unparsable_one_is_asked_again():
    def hostile(n, payload):
        return reply(
            {"moment_id": m["moment_id"], "full": "A brilliant strike from Smith!", "short": "Goal!"}
            for m in payload["moments"]
        )

    fake = Fake(hostile)
    describer = describer_for(fake)
    build_session(MATCH, PRESET, PROFILE, describer)
    first = len(fake.calls)
    again = build_session(MATCH, PRESET, Profile(detail="full", lang="en", rate=1.3), describer)
    assert len(fake.calls) == first and again.report.fallback == again.report.moments

    DB["path"] = DB["path"].with_name("garbage.sqlite")  # the first window is already stored in the other file
    garbage = Fake(lambda n, payload: "nonsense")
    describer = describer_for(garbage)
    build_session(MATCH, PRESET, PROFILE, describer)
    first = len(garbage.calls)
    build_session(MATCH, PRESET, Profile(detail="full", lang="en", rate=1.3), describer)
    assert len(garbage.calls) > first  # garbage is not pinned for the life of the process


def test_a_failed_call_is_not_cached():
    def script(n, payload):
        if n == 1:
            raise RuntimeError("boom")
        return examples(payload)

    fake = Fake(script)
    describer = describer_for(fake)
    first = build_session(MATCH, PRESET, PROFILE, describer)
    assert first.report.attempts == 2 and len(fake.calls) == 2
    second = build_session(MATCH, PRESET, Profile(detail="full", lang="en", rate=1.4), describer)
    # attempt 1 was never cached (it raised), so it is asked again, and this time it works
    assert second.report.attempts == 1 and len(fake.calls) == 3 and second.report.verified == second.report.moments


# ---- configuration and the HTTP surface -----------------------------------------------------------


BACKEND = Path(__file__).resolve().parents[1]


def run_isolated(code: str) -> None:
    """Run `code` in a fresh interpreter from the backend folder: what earlier tests imported does not count."""
    done = subprocess.run(
        [sys.executable, "-I", "-c", "\n".join(["import sys", f"sys.path.insert(0, {str(BACKEND)!r})", code])],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]


def test_the_module_needs_no_sdk_to_import_or_to_run_with_a_fake(tmp_path):
    run_isolated(
        f"""
import json, sys
from app.contracts import Profile
from app.foundry import FoundryDescriber
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, build_session
from app.usage import UsageLedger
from tests.test_foundry import Fake

match = generate_match(SEED)
ledger = UsageLedger({str(tmp_path / "usage.sqlite")!r}, per_minute=1000, per_day=1000, tokens_per_day=10**9, eur_per_month=100.0)
build_session(match, build_presets(match)[1], Profile(detail="full"), FoundryDescriber(Fake(), ledger))
assert "agent_framework" not in sys.modules and "azure.identity" not in sys.modules
"""
    )


SETTINGS = ("FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_MODEL", "SOUNDPITCH_LLM_CALLS_PER_MINUTE")


@pytest.mark.parametrize(
    "env,missing",
    [
        ({}, "FOUNDRY_PROJECT_ENDPOINT"),
        ({"FOUNDRY_PROJECT_ENDPOINT": "https://x.services.ai.azure.com/api/projects/p"}, "FOUNDRY_MODEL"),
        (
            {
                "FOUNDRY_PROJECT_ENDPOINT": "https://x",
                "FOUNDRY_MODEL": "m",
                "SOUNDPITCH_LLM_CALLS_PER_MINUTE": "many",
            },
            "SOUNDPITCH_LLM_CALLS_PER_MINUTE",
        ),
    ],
)
def test_a_missing_or_invalid_setting_is_named(monkeypatch, env, missing):
    for key in SETTINGS:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    foundry.reset_shared()
    with pytest.raises(FoundryNotConfigured, match=missing):
        foundry.shared_describer()


def test_the_api_answers_503_with_the_name_of_the_missing_setting(monkeypatch):
    from app import main

    for key in SETTINGS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SOUNDPITCH_LLM", "foundry")
    foundry.reset_shared()
    main.session_for.cache_clear()
    client = TestClient(main.app)
    for path in ("/api/session?preset=goal_1", "/api/session.vtt?preset=goal_1"):
        response = client.get(path)
        assert response.status_code == 503, path
        body = response.json()
        assert body["code"] == "llm_not_configured" and "FOUNDRY_PROJECT_ENDPOINT" in body["message"]
    assert client.get("/api/health").json() == {"status": "ok", "llm": "foundry"}
    main.session_for.cache_clear()


def test_the_api_serves_a_foundry_session_and_counts_calls_per_window_not_per_request(monkeypatch):
    from app import main

    fake = Fake()
    monkeypatch.setenv("SOUNDPITCH_LLM", "foundry")
    monkeypatch.setattr(foundry, "_SHARED", describer_for(fake))
    main.session_for.cache_clear()
    client = TestClient(main.app)
    one = client.get("/api/session?preset=goal_1&detail=full&rate=1.0")
    two = client.get("/api/session?preset=goal_1&detail=full&rate=1.7&calm=true")
    assert one.status_code == two.status_code == 200
    assert one.json()["report"]["verified"] == one.json()["report"]["moments"]
    assert len(fake.calls) == 1
    main.session_for.cache_clear()


@pytest.mark.skipif(importlib.util.find_spec("agent_framework") is not None, reason="the SDK is installed here")
def test_a_missing_package_is_named_with_the_command_that_installs_it(monkeypatch):
    from app import main

    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://x.services.ai.azure.com/api/projects/p")
    monkeypatch.setenv("FOUNDRY_MODEL", "deployment")
    monkeypatch.setenv("SOUNDPITCH_LLM", "foundry")
    foundry.reset_shared()
    main.session_for.cache_clear()
    response = TestClient(main.app).get("/api/session?preset=goal_1")
    assert response.status_code == 503
    assert response.json()["code"] == "llm_not_configured"
    assert "requirements-agents.txt" in response.json()["message"]
    assert "x.services.ai.azure.com" not in response.text  # the endpoint is never echoed
    main.session_for.cache_clear()


# ---- adversarial replies: parser, size limits and failure paths -----------------------------------


def test_a_fence_with_runaway_whitespace_cannot_stall_the_process():
    started = time.monotonic()
    nl = chr(10)
    for text in ("```json" + nl * 100_000 + "x", "```" + " " * 100_000, "```json" + nl + "{" + " " * 100_000):
        with pytest.raises((ValueError, TypeError)):
            foundry.parse_reply(text, {1})
    assert time.monotonic() - started < 1.0
    good = "```json" + nl + '{"items": [{"moment_id": 1, "full": "a", "short": "b"}]}' + nl + "```"
    assert foundry.parse_reply(good, {1})[1].full == "a"


def test_a_huge_reply_is_refused_before_it_is_cached():
    huge = '{"items": []}' + " " * 5_000_000
    describer = describer_for(Fake(lambda n, payload: huge))
    with pytest.raises(ValueError, match="too long"):
        describer.describe(detect_moments(window(), "full"), Context(MATCH, "en"), {}, 1)
    assert describer.ledger.cache_size() == 0


def test_a_session_built_during_an_outage_is_not_kept_by_the_api(monkeypatch):
    from app import main

    state = {"down": True}

    def script(n, payload):
        if state["down"]:
            raise ConnectionError("down")
        return examples(payload)

    monkeypatch.setenv("SOUNDPITCH_LLM", "foundry")
    monkeypatch.setattr(foundry, "_SHARED", describer_for(Fake(script)))
    main.session_for.cache_clear()
    client = TestClient(main.app)
    down = client.get("/api/session?preset=goal_1&detail=full").json()
    assert down["report"]["fallback"] == down["report"]["moments"]
    state["down"] = False
    up = client.get("/api/session?preset=goal_1&detail=full").json()
    assert up["report"]["verified"] == up["report"]["moments"] and up["report"]["attempts"] == 1
    main.session_for.cache_clear()


def test_a_session_built_over_the_cap_is_not_kept_by_the_api(monkeypatch):
    from app import main

    clock = Clock()
    describer = describer_for(Fake(), clock=clock, per_minute=1)
    monkeypatch.setenv("SOUNDPITCH_LLM", "foundry")
    monkeypatch.setattr(foundry, "_SHARED", describer)
    main.session_for.cache_clear()
    client = TestClient(main.app)
    assert client.get("/api/session?preset=goal_1&detail=full").status_code == 200
    capped = client.get("/api/session?preset=goal_2&detail=full").json()
    assert any("budget" in t["detail"] for t in capped["trace"])
    clock.now += 61  # the minute is over
    again = client.get("/api/session?preset=goal_2&detail=full").json()
    assert not any("budget" in t["detail"] for t in again["trace"])
    main.session_for.cache_clear()


def test_concurrent_identical_requests_make_one_call():
    def script(n, payload):
        time.sleep(0.3)
        return examples(payload)

    fake = Fake(script)
    describer = describer_for(fake)
    ctx = Context(MATCH, "en")
    moments = detect_moments(window(), "full")
    results = []
    workers = [threading.Thread(target=lambda: results.append(describer.describe(moments, ctx, {}, 1))) for _ in range(12)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    assert len(fake.calls) == 1 and len(results) == 12 and all(r == results[0] for r in results)


def test_a_saturated_pool_fails_fast_and_reserves_nothing_more():
    release = threading.Event()

    def script(n, payload):
        release.wait(10)
        return examples(payload)

    describer = describer_for(Fake(script), timeout_s=0.05)
    ctx = Context(MATCH, "en")
    moments = detect_moments(window(), "full")
    try:
        for attempt in range(1, foundry.MAX_IN_FLIGHT + 1):  # hung calls fill the pool
            with pytest.raises(TimeoutError):
                describer.describe(moments, ctx, {}, attempt)
        held = describer.ledger.totals()
        assert held["day_calls"] == held["in_flight"] == foundry.MAX_IN_FLIGHT  # worst case stays held
        started = time.monotonic()
        for attempt in range(10, 20):
            with pytest.raises(RuntimeError, match="busy"):
                describer.describe(moments, ctx, {}, attempt)
        assert time.monotonic() - started < 1.0
        assert describer.ledger.totals() == held
    finally:
        release.set()


# ---- a daily cap and an output cap, on top of the per-minute cap ----------------------------------


def test_over_the_daily_cap_the_window_is_described_by_templates_until_the_day_turns():
    goal_2 = next(p for p in build_presets(MATCH) if p.id == "goal_2")
    goal_3 = next(p for p in build_presets(MATCH) if p.id == "goal_3")
    fake, clock = Fake(), Clock()
    describer = describer_for(fake, clock=clock, per_day=1)
    build_session(MATCH, PRESET, PROFILE, describer)
    second = build_session(MATCH, goal_2, PROFILE, describer)
    assert len(fake.calls) == 1
    assert any("llm budget exhausted: templates (day)" in t.detail for t in second.trace)
    assert second.report.verified == second.report.moments and second.report.fallback == 0
    clock.now += 61  # the minute cap alone is not what holds it
    assert any("(day)" in t.detail for t in build_session(MATCH, goal_3, PROFILE, describer).trace)
    assert len(fake.calls) == 1
    clock.now += 86_400  # a day later
    assert not any("budget" in t.detail for t in build_session(MATCH, goal_3, PROFILE, describer).trace)
    assert len(fake.calls) == 2


# ---- the usage ledger decides every call (S21) -------------------------------------------------------


def worst_case(call):
    system, user = call
    return cost_micro_eur(estimate_input_tokens(system, user), foundry.MAX_OUTPUT_TOKENS, attempts=3)


def test_a_call_that_raises_keeps_its_worst_case_and_every_retry_reserves_again():
    def script(n, payload):
        raise ConnectionError("down")

    fake = Fake(script)
    s, describer = session(fake)
    assert len(fake.calls) == 3 * -(-s.report.moments // foundry.MAX_BATCH)
    held = describer.ledger.totals()
    assert held["day_calls"] == held["in_flight"] == len(fake.calls)
    assert held["month_micro_eur"] >= worst_case(fake.calls[0])
    assert s.report.fallback == s.report.moments  # the templates still speak


def test_a_successful_call_is_settled_with_the_usage_the_provider_reports():
    fake = Fake(lambda n, payload: Reply(examples(payload), input_tokens=2100, output_tokens=310))
    s, describer = session(fake)
    assert s.report.verified == s.report.moments and len(fake.calls) == 1
    totals = describer.ledger.totals()
    assert totals["in_flight"] == 0 and totals["day_tokens"] == 2410
    assert totals["month_micro_eur"] == cost_micro_eur(2100, 310) < worst_case(fake.calls[0]) / 5


def test_usage_above_the_output_allowance_is_recorded_as_reported_and_never_clamped():
    fake = Fake(lambda n, payload: Reply(examples(payload), input_tokens=100, output_tokens=50_000))
    _, describer = session(fake)
    assert describer.ledger.totals()["day_tokens"] == 50_100


def test_an_unexpected_error_from_the_ledger_stops_the_call_before_the_client():
    class Broken(UsageLedger):
        def reserve(self, *a, **k):
            raise RuntimeError("boom")

    fake = Fake()
    broken = Broken(DB["path"], per_minute=9, per_day=9, tokens_per_day=10**9, eur_per_month=1.0)
    s = build_session(MATCH, PRESET, PROFILE, FoundryDescriber(fake, broken))
    assert fake.calls == []
    assert s.report.fallback == s.report.moments and s.report.attempts == 3  # failed attempts, then templates


def test_a_reply_without_usage_is_settled_with_an_estimate_not_with_zero():
    fake = Fake()
    _, describer = session(fake)
    totals = describer.ledger.totals()
    assert totals["in_flight"] == 0 and totals["day_tokens"] > 0 and totals["month_micro_eur"] > 0


def test_the_request_asks_for_at_most_1000_output_tokens_and_reserves_that_worst_case():
    assert foundry.MAX_OUTPUT_TOKENS <= 1000 and foundry.MAX_BATCH <= 20
    seen = {}

    def script(n, payload):
        seen["held"] = describer.ledger.totals()  # the reservation exists while the call runs
        return examples(payload)

    fake = Fake(script)
    describer = describer_for(fake)
    build_session(MATCH, PRESET, PROFILE, describer)
    assert seen["held"]["in_flight"] == 1
    assert seen["held"]["month_micro_eur"] == worst_case(fake.calls[0])


def test_a_call_that_times_out_keeps_its_worst_case_until_it_ends_and_then_settles():
    release = threading.Event()

    def script(n, payload):
        release.wait(5)
        return examples(payload)

    describer = describer_for(Fake(script), timeout_s=0.05)
    ctx = Context(MATCH, "en")
    with pytest.raises(TimeoutError):
        describer.describe(detect_moments(window(), "full"), ctx, {}, 1)
    assert describer.ledger.totals()["in_flight"] == 1
    release.set()
    for _ in range(100):
        if describer.ledger.totals()["in_flight"] == 0:
            break
        time.sleep(0.05)
    assert describer.ledger.totals()["in_flight"] == 0  # the late answer was paid for, so it is counted


def test_a_call_that_never_left_the_process_is_released():
    describer = describer_for(Fake())
    describer._pool.shutdown()  # submit now raises: nothing is sent
    with pytest.raises(RuntimeError):
        describer.describe(detect_moments(window(), "full"), Context(MATCH, "en"), {}, 1)
    assert describer.ledger.totals()["day_calls"] == 0


@pytest.mark.parametrize(
    "limit,reason",
    [({"per_day": 0}, "day"), ({"tokens_per_day": 10}, "tokens"), ({"eur_per_month": 0.0001}, "month")],
)
def test_an_exhausted_quota_never_contacts_the_model_and_the_templates_speak(limit, reason):
    fake = Fake()
    s, _ = session(fake, **limit)
    clean = build_session(MATCH, PRESET, PROFILE, TemplateDescriber())
    assert fake.calls == []
    assert s.report.verified == s.report.moments and s.report.fallback == 0
    assert [c.text for c in s.cues] == [c.text for c in clean.cues]
    assert any(f"templates ({reason})" in t.detail for t in s.trace)


def test_an_unusable_ledger_never_contacts_the_model_and_the_templates_speak(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    DB["path"] = blocker / "usage.sqlite"
    fake = Fake()
    s, _ = session(fake)
    assert fake.calls == []
    assert s.report.verified == s.report.moments and s.report.fallback == 0
    assert any("templates (ledger unavailable)" in t.detail for t in s.trace)


def test_a_restart_keeps_the_day_count_and_the_replies_already_paid_for():
    clock = Clock()
    first = Fake()
    build_session(MATCH, PRESET, PROFILE, describer_for(first, clock=clock, per_day=1))
    assert len(first.calls) == 1
    second = Fake()  # "the process restarted": a new describer and a new ledger on the same file
    later = Profile(detail="full", lang="en", rate=1.2)
    again = build_session(MATCH, PRESET, later, describer_for(second, clock=clock, per_day=1))
    assert second.calls == [] and again.report.verified == again.report.moments  # replayed from the stored reply
    goal_2 = next(p for p in build_presets(MATCH) if p.id == "goal_2")
    other = build_session(MATCH, goal_2, PROFILE, describer_for(second, clock=clock, per_day=1))
    assert second.calls == [] and any("(day)" in t.detail for t in other.trace)


def test_concurrent_windows_cannot_spend_more_calls_than_the_daily_cap(monkeypatch):
    monkeypatch.setattr(foundry, "MAX_IN_FLIGHT", 12)  # the in-flight guard is tested elsewhere
    def script(n, payload):
        time.sleep(0.1)
        return examples(payload)

    fake = Fake(script)
    describer = describer_for(fake, per_day=3)
    ctx = Context(MATCH, "en")
    moments = detect_moments(MATCH.events, "full")
    notes = []

    def go(offset):
        describer.describe(moments[offset : offset + 5], ctx, {}, 1)
        notes.append(describer.note)

    workers = [threading.Thread(target=go, args=(i * 5,)) for i in range(12)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    assert len(fake.calls) == 3
    assert sum("(day)" in n for n in notes) == 9
    assert describer.ledger.totals()["day_calls"] == 3


def test_over_the_prompt_ceiling_nothing_is_sent():
    fake = Fake()
    describer = describer_for(fake)
    ctx = Context(MATCH, "en")
    moments = detect_moments(window(), "full")
    big = {m.id: ["x" * 1000] * 40 for m in moments}
    described = describer.describe(moments, ctx, big, 2)
    assert fake.calls == [] and "prompt too large" in describer.note
    assert set(described) == {m.id for m in moments}  # the templates answered


# ---- limits from the environment ---------------------------------------------------------------------

LIMIT_SETTINGS = (
    "SOUNDPITCH_LLM_CALLS_PER_MINUTE",
    "SOUNDPITCH_LLM_CALLS_PER_DAY",
    "SOUNDPITCH_LLM_TOKENS_PER_DAY",
    "SOUNDPITCH_LLM_EUR_PER_MONTH",
    "SOUNDPITCH_USAGE_DB",
)


def test_the_default_limits_are_the_strict_ones_and_the_database_sits_in_the_ignored_data_folder(monkeypatch):
    for key in LIMIT_SETTINGS:
        monkeypatch.delenv(key, raising=False)
    ledger = foundry.ledger_from_env()
    assert (ledger.per_minute, ledger.per_day, ledger.tokens_per_day) == (2, 20, 120_000)
    assert ledger.micro_per_month == 2_000_000
    assert ledger.path.name == "usage.sqlite" and ledger.path.parent.name == "data"


def test_limits_can_be_lowered_and_the_database_moved_from_the_environment(monkeypatch, tmp_path):
    for key in LIMIT_SETTINGS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SOUNDPITCH_LLM_CALLS_PER_DAY", "5")
    monkeypatch.setenv("SOUNDPITCH_LLM_EUR_PER_MONTH", "0.5")
    monkeypatch.setenv("SOUNDPITCH_USAGE_DB", str(tmp_path / "elsewhere.sqlite"))
    ledger = foundry.ledger_from_env()
    assert ledger.per_day == 5 and ledger.micro_per_month == 500_000
    assert ledger.path == tmp_path / "elsewhere.sqlite"


@pytest.mark.parametrize(
    "name,value",
    [
        ("SOUNDPITCH_LLM_CALLS_PER_MINUTE", "0"),
        ("SOUNDPITCH_LLM_CALLS_PER_DAY", "-3"),
        ("SOUNDPITCH_LLM_TOKENS_PER_DAY", "many"),
        ("SOUNDPITCH_LLM_EUR_PER_MONTH", "free"),
        ("SOUNDPITCH_LLM_EUR_PER_MONTH", "0"),
        ("SOUNDPITCH_LLM_EUR_PER_MONTH", "nan"),
        ("SOUNDPITCH_LLM_EUR_PER_MONTH", "4.01"),
        ("SOUNDPITCH_LLM_EUR_PER_MONTH", "5"),
    ],
)
def test_a_bad_limit_or_one_above_the_ceiling_is_refused_and_named(monkeypatch, name, value):
    for key in LIMIT_SETTINGS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(name, value)
    with pytest.raises(FoundryNotConfigured, match=name):
        foundry.ledger_from_env()
