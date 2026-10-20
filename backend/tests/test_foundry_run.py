"""S12 tooling: the live-run script, exercised with a fake client (no network, no Azure)."""

import pytest

from app import foundry_run
from app.usage import UsageLedger
from tests.test_foundry import Fake, examples, reply


@pytest.fixture
def led(tmp_path):
    return fresh(tmp_path, "usage")


def fresh(tmp_path, name):
    return UsageLedger(
        tmp_path / f"{name}.sqlite", per_minute=10_000, per_day=10_000, tokens_per_day=10**9, eur_per_month=100.0
    )


def test_without_settings_it_exits_2_and_names_what_is_missing(monkeypatch, capsys):
    for key in ("FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_MODEL"):
        monkeypatch.delenv(key, raising=False)
    assert foundry_run.main([]) == 2
    err = capsys.readouterr().err
    assert "FOUNDRY_PROJECT_ENDPOINT" in err and "cannot run" in err


def test_a_good_model_is_reported_as_verified_at_the_first_attempt(tmp_path, monkeypatch, led):
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://secret-endpoint.example/api/projects/p")
    out = tmp_path / "evidence" / "foundry-run.md"
    assert foundry_run.main(["--write", str(out)], client=Fake(), model="fake-deployment", ledger=led) == 0
    text = out.read_text(encoding="utf-8")
    assert "fake-deployment" in text and "Verified at attempt 1" in text and "p95" in text
    assert "secret-endpoint" not in text
    result = foundry_run.run(Fake(), fresh(tmp_path, "second"))
    for stats in result["stats"].values():
        assert stats["sessions"] == 15 and stats["fallback"] == 0
        assert stats["verified_at_1"] == stats["moments"] == stats["verified"]
    assert 0 < len(result["latency"]) <= 30  # windows that repeat across detail levels are replayed


def test_a_model_that_breaks_the_rules_is_reported_with_its_reasons_and_never_verified(led):
    def script(n, payload):
        return reply(
            {"moment_id": m["moment_id"], "full": "A brilliant strike from Smith!", "short": "Goal!"}
            for m in payload["moments"]
        )

    result = foundry_run.run(Fake(script), led)
    assert result["words"]["en"]["brilliant"] > 0
    for lang, stats in result["stats"].items():
        assert stats["fallback"] == stats["moments"] and stats["verified"] == 0
        assert result["reasons"][lang]["a word outside the vocabulary of the moment"] > 0


def test_first_attempt_retries_and_failed_calls_are_told_apart(led):
    def script(n, payload):
        if n % 3 == 1:
            raise TimeoutError("slow")
        return examples(payload)

    result = foundry_run.run(Fake(script), led)
    stats = result["stats"]
    assert sum(s["failed_calls"] for s in stats.values()) == result["call_errors"] > 0
    assert sum(s["retried_sessions"] for s in stats.values()) > 0
    assert all(s["fallback"] == 0 and s["verified"] == s["moments"] for s in stats.values())
    assert sum(s["verified_at_1"] for s in stats.values()) < sum(s["moments"] for s in stats.values())


def test_the_report_tells_a_copied_template_sentence_from_the_models_own_words(tmp_path):
    copied = foundry_run.run(Fake(), fresh(tmp_path, "copied"))
    for stats in copied["stats"].values():
        assert stats["cues_verified"] > 0 and stats["cues_own_words"] == 0

    def varied(n, payload):
        return reply(
            {
                "moment_id": m["moment_id"],
                "full": m["examples"][0]["full"].replace(".", "!"),
                "short": m["examples"][0]["short"].replace(".", "!"),
            }
            for m in payload["moments"]
        )

    own = foundry_run.run(Fake(varied), fresh(tmp_path, "own"))
    for stats in own["stats"].values():
        assert stats["cues_own_words"] > 0 and stats["fallback"] == 0
    assert "own words" in foundry_run.to_markdown(own, "m", __import__("datetime").date(2026, 10, 20))


def test_a_pause_between_calls_keeps_a_run_under_the_deployments_token_ceiling(tmp_path):
    import time

    started = time.monotonic()
    result = foundry_run.run(Fake(), fresh(tmp_path, "paused"), pause_s=0.05)
    calls = len(result["latency"])
    assert calls > 5 and time.monotonic() - started >= 0.9 * 0.05 * calls
    assert foundry_run.main(["--pause-seconds", "0"], client=Fake(), model="m", ledger=fresh(tmp_path, "main")) == 0


def test_the_pause_comes_before_each_call_and_never_inside_it(tmp_path, monkeypatch):
    """A pause inside the call counts against the describer's 20 s timeout: it made every real call fail."""
    log: list[str] = []
    monkeypatch.setattr(foundry_run.time, "sleep", lambda seconds: log.append("sleep"))

    class Spy(Fake):
        def complete(self, system, user):
            log.append("call")
            return super().complete(system, user)

    foundry_run.run(Spy(), fresh(tmp_path, "spy"), pause_s=31)
    assert "call" in log and all(log[i - 1] == "sleep" for i, entry in enumerate(log) if entry == "call")
    log.clear()
    foundry_run.TimedClient(Spy()).complete("system", '{"moments": []}')  # the timed wrapper itself never sleeps
    assert log == ["call"]


def test_a_request_already_stored_in_the_ledger_is_neither_paused_for_nor_asked_again(tmp_path, monkeypatch):
    """Resuming a run with the same ledger must cost neither calls nor waiting for what is already paid for."""
    ledger = fresh(tmp_path, "resume")
    first = Fake()
    foundry_run.run(first, ledger)
    assert first.calls
    sleeps: list[float] = []
    monkeypatch.setattr(foundry_run.time, "sleep", lambda seconds: sleeps.append(seconds))
    second = Fake()
    foundry_run.run(second, ledger, pause_s=31)
    assert second.calls == [] and sleeps == []
    third = Fake()
    foundry_run.run(third, fresh(tmp_path, "new"), pause_s=31)  # a fresh ledger still waits before each call
    assert third.calls and len(sleeps) >= len(third.calls)
