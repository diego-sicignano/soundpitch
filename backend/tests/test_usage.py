"""S21: the usage ledger decides every model call, and its limits hold across threads, processes and restarts."""

import logging
import multiprocessing
import threading

import pytest

from app import usage
from app.usage import (
    BudgetExceeded,
    LedgerUnavailable,
    UsageLedger,
    cost_micro_eur,
)

START = 1_785_000_000.0  # 2026-07-25 18:40 UTC, far from a day or month boundary
DAY = 86_400.0


class Clock:
    def __init__(self, now=START):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make(path, clock=None, **limits):
    base = {"per_minute": 1000, "per_day": 1000, "tokens_per_day": 10**9, "eur_per_month": 100.0}
    return UsageLedger(path, clock=clock or Clock(), **{**base, **limits})


@pytest.fixture
def db(tmp_path):
    return tmp_path / "usage.sqlite"


# ---- reserving, settling, failing -----------------------------------------------------------------


def test_a_reservation_counts_until_it_is_settled_with_the_providers_usage(db):
    ledger = make(db)
    held = ledger.reserve(4000, 1000)
    now = ledger.totals()
    assert now["in_flight"] == 1 and now["day_tokens"] == 5000
    assert now["month_micro_eur"] == cost_micro_eur(4000, 1000, attempts=3)  # worst case, three SDK attempts
    ledger.settle(held, 1500, 300)
    after = ledger.totals()
    assert after["in_flight"] == 0 and after["day_tokens"] == 1800
    assert after["month_micro_eur"] == cost_micro_eur(1500, 300) < now["month_micro_eur"] / 5
    assert after["day_calls"] == 1


def test_a_call_that_failed_keeps_its_worst_case_and_only_a_call_never_sent_is_released(db):
    ledger = make(db)
    failed = ledger.reserve(4000, 1000)  # timed out, raised or was cancelled: nobody settles it
    never_sent = ledger.reserve(4000, 1000)
    ledger.release(never_sent)
    totals = ledger.totals()
    assert totals["day_calls"] == 1 and totals["in_flight"] == 1
    assert totals["month_micro_eur"] == cost_micro_eur(4000, 1000, attempts=3)
    assert failed.id != never_sent.id


def test_a_reservation_over_the_prompt_ceiling_is_refused_before_anything_is_recorded(db):
    ledger = make(db)
    with pytest.raises(BudgetExceeded, match="too large"):
        ledger.reserve(50_000, 1000)
    assert ledger.totals()["day_calls"] == 0


# ---- the caps ------------------------------------------------------------------------------------


def test_the_minute_cap_lifts_after_sixty_seconds(db):
    clock = Clock()
    ledger = make(db, clock, per_minute=2)
    ledger.reserve(100, 100)
    ledger.reserve(100, 100)
    with pytest.raises(BudgetExceeded, match="minute"):
        ledger.reserve(100, 100)
    clock.advance(61)
    ledger.reserve(100, 100)


def test_the_daily_cap_turns_with_the_utc_day(db):
    clock = Clock()
    ledger = make(db, clock, per_day=3)
    for _ in range(3):
        ledger.reserve(100, 100)
        clock.advance(61)
    with pytest.raises(BudgetExceeded, match="day"):
        ledger.reserve(100, 100)
    clock.advance(DAY)
    ledger.reserve(100, 100)


def test_the_daily_token_cap_counts_estimated_and_then_actual_tokens(db):
    ledger = make(db, tokens_per_day=6000)
    first = ledger.reserve(4000, 1000)  # 5000 held
    with pytest.raises(BudgetExceeded, match="tokens"):
        ledger.reserve(1000, 1000)  # 2000 more would be 7000
    ledger.settle(first, 1500, 300)  # now 1800
    ledger.reserve(1000, 1000)


def test_the_monthly_cost_ceiling_counts_reservations_in_flight_and_frees_the_margin_when_settled(db):
    worst = cost_micro_eur(4000, 1000, attempts=3)
    ledger = make(db, eur_per_month=1.5 * worst / 1e6)
    first = ledger.reserve(4000, 1000)
    with pytest.raises(BudgetExceeded, match="month"):  # the first call is still in flight
        ledger.reserve(4000, 1000)
    ledger.settle(first, 1500, 300)
    ledger.reserve(4000, 1000)


def test_the_monthly_ceiling_turns_with_the_month_and_not_with_the_day(db):
    clock = Clock()
    worst = cost_micro_eur(4000, 1000, attempts=3)
    ledger = make(db, clock, eur_per_month=1.5 * worst / 1e6)
    ledger.reserve(4000, 1000)
    clock.advance(2 * DAY)  # a new day, the same month: still refused
    with pytest.raises(BudgetExceeded, match="month"):
        ledger.reserve(4000, 1000)
    clock.advance(40 * DAY)
    ledger.reserve(4000, 1000)


# ---- concurrency, processes, restarts ---------------------------------------------------------------


def test_forty_concurrent_threads_cannot_overshoot_a_cap_of_ten(db):
    ledger = make(db, per_day=10)
    granted, refused = [], []

    def go():
        try:
            granted.append(ledger.reserve(100, 100))
        except BudgetExceeded:
            refused.append(1)

    workers = [threading.Thread(target=go) for _ in range(40)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    assert len(granted) == 10 and len(refused) == 30
    assert ledger.totals()["day_calls"] == 10


def _try_many(args):
    path, tries = args
    ledger = UsageLedger(
        path, per_minute=1000, per_day=15, tokens_per_day=10**9, eur_per_month=100.0, clock=lambda: START
    )
    won = 0
    for _ in range(tries):
        try:
            ledger.reserve(100, 100)
            won += 1
        except BudgetExceeded:
            pass
    return won


def test_four_processes_on_one_file_cannot_overshoot_a_cap_of_fifteen(db):
    make(db).totals()  # create the schema once
    with multiprocessing.get_context("spawn").Pool(4) as pool:
        won = pool.map(_try_many, [(db, 10)] * 4)
    assert sum(won) == 15


def test_a_new_ledger_on_the_same_file_continues_the_counts_after_a_restart(db):
    clock = Clock()
    first = make(db, clock, per_day=2)
    first.reserve(100, 100)
    clock.advance(61)
    first.reserve(100, 100)
    del first
    second = make(db, clock, per_day=2)  # "the process restarted"
    clock.advance(61)
    with pytest.raises(BudgetExceeded, match="day"):
        second.reserve(100, 100)
    assert second.totals()["day_calls"] == 2


# ---- unavailable persistence fails closed -----------------------------------------------------------------


def test_a_path_that_cannot_be_created_refuses_the_call(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    with pytest.raises(LedgerUnavailable):
        make(blocker / "usage.sqlite").reserve(100, 100)


def test_a_corrupt_database_refuses_the_call(db):
    db.write_bytes(b"this is not a sqlite database" * 100)
    with pytest.raises(LedgerUnavailable):
        make(db).reserve(100, 100)


def test_a_database_locked_by_another_writer_refuses_instead_of_waiting_forever(db):
    import sqlite3
    import time

    ledger = make(db, busy_timeout_s=0.2)
    ledger.totals()
    holder = sqlite3.connect(db, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        with pytest.raises(LedgerUnavailable):
            ledger.reserve(100, 100)
        assert time.monotonic() - started < 3
    finally:
        holder.execute("ROLLBACK")
        holder.close()


def test_a_refusal_is_logged_with_the_reason_and_nothing_else(db, caplog):
    clock = Clock()
    ledger = make(db, clock, per_day=1)
    ledger.reserve(100, 100)
    clock.advance(61)
    with caplog.at_level(logging.WARNING, logger="soundpitch.usage"), pytest.raises(BudgetExceeded):
        ledger.reserve(100, 100)
    lines = [r.getMessage() for r in caplog.records]
    assert len(lines) == 1 and "day" in lines[0]
    assert "http" not in lines[0] and "key" not in lines[0].lower()


# ---- the reply cache --------------------------------------------------------------------------------


def test_replies_survive_a_restart_and_are_bounded(db):
    first = make(db, max_replies=3)
    for n in range(5):
        first.cache_put(f"key{n}", f"reply {n}")
    del first
    second = make(db, max_replies=3)
    assert second.cache_size() == 3
    assert second.cache_get("key4") == "reply 4" and second.cache_get("key0") is None


def test_a_cache_that_cannot_be_read_is_a_miss_not_an_error(db):
    db.write_bytes(b"garbage" * 200)
    assert make(db).cache_get("k") is None


def test_cost_is_integer_micro_euros_at_the_assumed_prices():
    assert cost_micro_eur(1_000_000, 0) == 500_000  # 0.50 EUR per million input tokens
    assert cost_micro_eur(0, 1_000_000) == 2_000_000  # 2.00 EUR per million output tokens
    assert cost_micro_eur(1000, 1000, attempts=3) == 3 * cost_micro_eur(1000, 1000)


# ---- units: the list price is in USD, the ledger counts euros at a stated, conservative rate ------------


def test_the_prices_are_derived_from_the_usd_list_price_a_stated_fx_policy_and_the_margin():
    assert (usage.LIST_USD_PER_MILLION_IN, usage.LIST_USD_PER_MILLION_OUT) == (0.40, 1.60)
    assert usage.EUR_PER_USD == 1.0  # 1 USD is counted as 1 EUR: above the market rate, so it over-counts
    assert usage.SAFETY_MARGIN == 1.25
    assert usage.PRICE_IN_DECIMICRO == round(usage.LIST_USD_PER_MILLION_IN * usage.EUR_PER_USD * usage.SAFETY_MARGIN * 10)
    assert usage.PRICE_OUT_DECIMICRO == round(usage.LIST_USD_PER_MILLION_OUT * usage.EUR_PER_USD * usage.SAFETY_MARGIN * 10)


def test_the_measured_call_of_the_smoke_test_costs_its_list_price_in_usd_plus_the_margin():
    list_usd = (686 * 0.40 + 34 * 1.60) / 1_000_000
    assert round(list_usd, 7) == 0.0003288
    assert cost_micro_eur(686, 34) == 411  # 0.000411 = list price in USD x 1.25, counted 1:1 as euros


@pytest.mark.parametrize("tokens_in,tokens_out", [(1, 0), (0, 1), (686, 34), (2000, 300), (12_000, 1000), (999_999, 1)])
def test_the_ledger_never_counts_less_than_the_list_price_converted_at_the_stated_rate_with_the_margin(tokens_in, tokens_out):
    list_micro = (tokens_in * usage.LIST_USD_PER_MILLION_IN + tokens_out * usage.LIST_USD_PER_MILLION_OUT) * usage.EUR_PER_USD
    assert cost_micro_eur(tokens_in, tokens_out) >= list_micro * usage.SAFETY_MARGIN - 1e-6


def test_one_reservation_holds_three_attempts_of_cost_but_one_attempt_of_tokens(db):
    ledger = make(db)
    ledger.reserve(4000, 1000)
    held = ledger.totals()
    assert held["month_micro_eur"] == 3 * cost_micro_eur(4000, 1000)
    assert held["day_tokens"] == 5000  # the daily token cap counts one attempt: documented in D11


def test_the_largest_allowed_call_fits_many_times_in_the_default_monthly_ceiling_and_never_past_it(db):
    worst = cost_micro_eur(usage.MAX_INPUT_TOKENS, 1000, usage.SDK_ATTEMPTS)
    ledger = make(db, eur_per_month=2.0)
    held = 0
    while True:
        try:
            ledger.reserve(usage.MAX_INPUT_TOKENS, 1000)
        except BudgetExceeded as exc:
            assert str(exc) == "month"
            break
        held += 1
    assert held == 2_000_000 // worst and ledger.totals()["month_micro_eur"] <= 2_000_000
