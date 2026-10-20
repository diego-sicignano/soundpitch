"""A durable ledger that decides every model call before it is made (SPEC §11, D11).

One SQLite file (standard library): `reserve` runs in a single `BEGIN IMMEDIATE` transaction that counts
the calls of the last minute and of the UTC day, the tokens of the day and the estimated euros of the
month, refuses if the worst case of this call does not fit, and otherwise records the reservation. That
is what stops concurrent threads and processes on one host from overshooting; process memory could not.
`settle` replaces the estimate with the usage the provider reports. A call that failed, timed out or
was cancelled keeps its worst case, because it may have been billed. If the file cannot be used, the
call is refused: the ledger fails closed.

What it is not: shared between hosts (one file), nor a promise about what Azure bills.
"""

import datetime
import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("soundpitch.usage")
_INIT_LOCK = threading.Lock()
_READY: set[str] = set()  # database files this process has already put in WAL mode with the schema

# Prices. The list price of gpt-4.1-mini Global Standard is in US dollars (checked 2026-10-20): 0.40 per
# million input tokens and 1.60 per million output tokens. The ledger counts euros, converted at a stated
# policy and not at a market rate: 1 USD is counted as 1 EUR. That over-counts while a dollar is worth less
# than a euro (the rate was not fetched: check it); if EUR/USD falls below 1.0, or the subscription is billed
# in another currency, revisit it. On top comes a 25% margin. Amounts are integer tenths of a micro-unit per token.
LIST_USD_PER_MILLION_IN = 0.40
LIST_USD_PER_MILLION_OUT = 1.60
EUR_PER_USD = 1.0
SAFETY_MARGIN = 1.25
PRICE_IN_DECIMICRO = round(LIST_USD_PER_MILLION_IN * EUR_PER_USD * SAFETY_MARGIN * 10)  # 0.50 per million
PRICE_OUT_DECIMICRO = round(LIST_USD_PER_MILLION_OUT * EUR_PER_USD * SAFETY_MARGIN * 10)  # 2.00 per million
SDK_ATTEMPTS = 3  # the SDK may retry a failed request twice; each retry could be billed
MAX_INPUT_TOKENS = 12_000  # a prompt estimated above this is refused
MAX_EUR_PER_MONTH = 4.0  # the Azure budget is 5; the application ceiling can never be set above 4
RETENTION_DAYS = 70

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        day TEXT NOT NULL,
        month TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('reserved', 'settled', 'released')),
        tokens INTEGER NOT NULL,
        micro_eur INTEGER NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS calls_ts ON calls (ts)",
    "CREATE INDEX IF NOT EXISTS calls_day ON calls (day)",
    "CREATE INDEX IF NOT EXISTS calls_month ON calls (month)",
    "CREATE TABLE IF NOT EXISTS replies (key TEXT PRIMARY KEY, ts REAL NOT NULL, reply TEXT NOT NULL)",
)


class BudgetExceeded(Exception):
    """A limit would be passed; the message is the reason (minute, day, tokens, month, prompt too large)."""


class LedgerUnavailable(Exception):
    """The database cannot be opened, read or written: nothing may be spent."""


@dataclass(frozen=True)
class Reservation:
    id: int
    tokens: int
    micro_eur: int


def cost_micro_eur(input_tokens: int, output_tokens: int, attempts: int = 1) -> int:
    """Integer micro-euros at the list price in USD, counted 1:1 as euros, plus the margin, rounded up."""
    decimicro = input_tokens * PRICE_IN_DECIMICRO + output_tokens * PRICE_OUT_DECIMICRO
    return attempts * -(-decimicro // 10)


def estimate_input_tokens(*texts: str) -> int:
    """Worst case: one token per two characters (English prose is nearer one per four)."""
    return -(-sum(len(t) for t in texts) // 2)


class UsageLedger:
    def __init__(
        self,
        path: Path | str,
        *,
        per_minute: int,
        per_day: int,
        tokens_per_day: int,
        eur_per_month: float,
        clock: Callable[[], float] = time.time,
        busy_timeout_s: float = 5.0,
        max_replies: int = 500,
    ):
        self.path = Path(path)
        self.per_minute, self.per_day, self.tokens_per_day = per_minute, per_day, tokens_per_day
        self.micro_per_month = round(eur_per_month * 1_000_000)
        self.clock, self.busy_timeout_s, self.max_replies = clock, busy_timeout_s, max_replies

    # ---- the database --------------------------------------------------------------------------

    def _initialise(self, con: sqlite3.Connection) -> None:
        """WAL and the schema, once per file and process. Switching to WAL ignores the busy timeout, so a
        second connection racing the first (another thread or process) is retried until the deadline."""
        deadline = time.monotonic() + self.busy_timeout_s
        while True:
            try:
                con.execute("PRAGMA journal_mode=WAL")
                for statement in SCHEMA:
                    con.execute(statement)
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)

    def _connect(self) -> sqlite3.Connection:
        key = str(self.path.absolute())
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            existed = self.path.exists()
            con = sqlite3.connect(self.path, timeout=self.busy_timeout_s, isolation_level=None)
            if key not in _READY or not existed:  # a deleted file needs its schema again
                try:
                    with _INIT_LOCK:
                        self._initialise(con)
                        _READY.add(key)
                except BaseException:
                    con.close()
                    raise
            return con
        except (sqlite3.Error, OSError) as exc:
            log.error("usage ledger unavailable (%s): model calls are refused", type(exc).__name__)
            raise LedgerUnavailable(type(exc).__name__) from exc

    def _periods(self) -> tuple[float, str, str]:
        now = self.clock()
        moment = datetime.datetime.fromtimestamp(now, datetime.UTC)
        return now, moment.strftime("%Y-%m-%d"), moment.strftime("%Y-%m")

    # ---- the decision ---------------------------------------------------------------------------

    def reserve(self, est_input_tokens: int, max_output_tokens: int) -> Reservation:
        """Hold the worst case of one call, or raise BudgetExceeded / LedgerUnavailable."""
        if est_input_tokens > MAX_INPUT_TOKENS:
            self._refuse("prompt too large")
        tokens = est_input_tokens + max_output_tokens
        micro = cost_micro_eur(est_input_tokens, max_output_tokens, SDK_ATTEMPTS)
        con = self._connect()
        try:
            now, day, month = self._periods()
            con.execute("BEGIN IMMEDIATE")
            try:
                minute_calls = con.execute(
                    "SELECT COUNT(*) FROM calls WHERE ts > ? AND state != 'released'", (now - 60,)
                ).fetchone()[0]
                day_calls, day_tokens = con.execute(
                    "SELECT COUNT(*), COALESCE(SUM(tokens), 0) FROM calls WHERE day = ? AND state != 'released'",
                    (day,),
                ).fetchone()
                month_micro = con.execute(
                    "SELECT COALESCE(SUM(micro_eur), 0) FROM calls WHERE month = ? AND state != 'released'",
                    (month,),
                ).fetchone()[0]
                if minute_calls >= self.per_minute:
                    reason = "minute"
                elif day_calls >= self.per_day:
                    reason = "day"
                elif day_tokens + tokens > self.tokens_per_day:
                    reason = "tokens"
                elif month_micro + micro > self.micro_per_month:
                    reason = "month"
                else:
                    reason = ""
                if reason:
                    con.execute("ROLLBACK")
                else:
                    cursor = con.execute(
                        "INSERT INTO calls (ts, day, month, state, tokens, micro_eur) VALUES (?, ?, ?, 'reserved', ?, ?)",
                        (now, day, month, tokens, micro),
                    )
                    con.execute("DELETE FROM calls WHERE ts < ?", (now - RETENTION_DAYS * 86_400,))
                    con.execute("COMMIT")
            except BaseException:
                if con.in_transaction:
                    con.execute("ROLLBACK")
                raise
        except sqlite3.Error as exc:
            log.error("usage ledger unavailable (%s): model calls are refused", type(exc).__name__)
            raise LedgerUnavailable(type(exc).__name__) from exc
        finally:
            con.close()
        if reason:
            self._refuse(reason)
        return Reservation(cursor.lastrowid, tokens, micro)

    def _refuse(self, reason: str):
        log.warning("model call refused before contacting Azure: %s limit reached", reason)
        raise BudgetExceeded(reason)

    def settle(self, reservation: Reservation, input_tokens: int, output_tokens: int) -> None:
        """Replace the estimate with what the provider reported."""
        self._update(
            reservation, "settled", input_tokens + output_tokens, cost_micro_eur(input_tokens, output_tokens)
        )

    def release(self, reservation: Reservation) -> None:
        """The call never left the process: give the reservation back."""
        self._update(reservation, "released", 0, 0)

    def _update(self, reservation: Reservation, state: str, tokens: int, micro: int) -> None:
        con = self._connect()
        try:
            con.execute(
                "UPDATE calls SET state = ?, tokens = ?, micro_eur = ? WHERE id = ?",
                (state, tokens, micro, reservation.id),
            )
        except sqlite3.Error as exc:
            log.error("usage ledger could not record a call (%s): its worst case stays held", type(exc).__name__)
            raise LedgerUnavailable(type(exc).__name__) from exc
        finally:
            con.close()

    def totals(self) -> dict[str, int]:
        now, day, month = self._periods()
        con = self._connect()
        try:
            minute_calls = con.execute(
                "SELECT COUNT(*) FROM calls WHERE ts > ? AND state != 'released'", (now - 60,)
            ).fetchone()[0]
            day_calls, day_tokens = con.execute(
                "SELECT COUNT(*), COALESCE(SUM(tokens), 0) FROM calls WHERE day = ? AND state != 'released'", (day,)
            ).fetchone()
            month_micro = con.execute(
                "SELECT COALESCE(SUM(micro_eur), 0) FROM calls WHERE month = ? AND state != 'released'", (month,)
            ).fetchone()[0]
            in_flight = con.execute("SELECT COUNT(*) FROM calls WHERE state = 'reserved'").fetchone()[0]
        except sqlite3.Error as exc:
            raise LedgerUnavailable(type(exc).__name__) from exc
        finally:
            con.close()
        return {
            "minute_calls": minute_calls,
            "day_calls": day_calls,
            "day_tokens": day_tokens,
            "month_micro_eur": month_micro,
            "in_flight": in_flight,
        }

    # ---- replies that parsed: a window asked once is not paid for twice ---------------------------

    def cache_get(self, key: str) -> str | None:
        try:
            con = self._connect()
            try:
                row = con.execute("SELECT reply FROM replies WHERE key = ?", (key,)).fetchone()
            finally:
                con.close()
        except (LedgerUnavailable, sqlite3.Error):
            return None  # a cache that cannot be read is a miss; the call itself is then refused by `reserve`
        return row[0] if row else None

    def cache_put(self, key: str, reply: str) -> None:
        try:
            con = self._connect()
            try:
                con.execute("INSERT OR REPLACE INTO replies (key, ts, reply) VALUES (?, ?, ?)", (key, self.clock(), reply))
                con.execute(
                    "DELETE FROM replies WHERE key NOT IN "
                    "(SELECT key FROM replies ORDER BY ts DESC, rowid DESC LIMIT ?)",
                    (self.max_replies,),
                )
            finally:
                con.close()
        except (LedgerUnavailable, sqlite3.Error):
            log.warning("a model reply could not be stored; it will be paid for again if asked again")

    def cache_size(self) -> int:
        con = self._connect()
        try:
            return con.execute("SELECT COUNT(*) FROM replies").fetchone()[0]
        finally:
            con.close()
