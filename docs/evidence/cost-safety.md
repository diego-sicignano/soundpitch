# Cost safety of the model calls (S21)

Date: 2026-10-20. Decision record: [D11](../DECISIONS.md). Rules: [SPEC §11](../../SPEC.md).

The point of this file is to say what is actually enforced, where, and what is not. **No limit here is a guarantee about the Azure bill.**

## What is enforced

| Limit | Value | Where | Survives a restart |
|---|---|---|---|
| Output tokens per request | 1,000 (`max_tokens`) | request sent to Azure, and the reservation | n/a |
| Moments per request | 20 | `foundry.MAX_BATCH` | n/a |
| Estimated prompt per request | 12,000 tokens (one token per two characters), over it nothing is sent | `usage.MAX_INPUT_TOKENS` | n/a |
| Calls in flight | 2, then fail fast without reserving | `foundry.MAX_IN_FLIGHT` | no (memory) |
| Timeout | 20 s | `foundry.TIMEOUT_S` | n/a |
| Calls per minute | 2 | usage ledger | yes |
| Calls per UTC day | 20 | usage ledger | yes |
| Tokens per UTC day | 120,000 (estimate, then provider usage) | usage ledger | yes |
| Estimated spend per UTC month | 2.00 EUR; the setting cannot exceed 4.00 | usage ledger | yes |
| Azure deployment | `gpt-4.1-mini` GlobalStandard, capacity **8** = 8 requests and 8,000 tokens a minute (was 10) | Azure | yes |
| Azure budget | 5 EUR a month, e-mail alerts only | Azure | yes |

The first seven limits stop the call **before** it reaches Azure. The Azure rows do not stop spending: the allocation is a throughput limit (429 above it) and the budget only alerts, 8 to 24 hours late.

## How a call is decided

1. The reply may already be stored (same match, language, moments, issues and instructions): no call, no cost, also after a restart.
2. Otherwise the describer reserves the **worst case** in one SQLite `BEGIN IMMEDIATE` transaction: estimated prompt tokens + 1,000 output tokens, three SDK attempts, at the USD list price counted 1:1 as euros plus 25% (0.50 per million input tokens, 2.00 per million output). If any limit would be passed, nothing is sent, the log gets one line without secrets (`model call refused before contacting Azure: day limit reached`) and the trace says `llm budget exhausted: templates (day)`; the verified templates speak.
3. The call is sent. When it returns, the reservation is replaced by the usage the provider reported (`usage_details`); without a report, by an estimate.
4. A call that raises, times out or is cancelled **keeps its worst case**, because it may have been billed. Only a call that never left the process (the submit failed) is released.
5. If the database cannot be opened, read or written, the call is refused (fail closed). No retry loop: the pipeline's retries each have to reserve again and are refused as soon as a limit is reached.

## Assumptions

- **Currency.** The list price of `gpt-4.1-mini` Global Standard on 2026-10-20 is in **US dollars**: 0.40 per million input tokens and 1.60 per million output tokens. The ledger does not fetch an exchange rate. It counts 1 USD as 1 EUR (`usage.EUR_PER_USD = 1.0`), which over-counts while a dollar is worth less than a euro (the current rate was not checked here), and adds a 25% margin (`usage.SAFETY_MARGIN`), giving 0.50 and 2.00 per million tokens. The unit in the table and in the database (`micro_eur`) is therefore "micro-units of a euro-priced dollar amount". The Azure budget (5) is in the billing currency of the subscription, which was not read; if that currency is not the euro, or EUR/USD falls below 1.0, the policy must be revisited. A price change or a different model invalidates the monthly figure.
- One token per two characters is a deliberate over-estimate for the prompt (English prose is nearer one per four).
- **SDK retries.** The installed `openai` 3.35.1 client inside `FoundryChatClient` has `max_retries = 2` (read offline from the constructed client; the application does not change it), so one call is up to 3 requests. They all run inside the 20 s `asyncio.wait_for` of the adapter. Only the final attempt reports usage, so a retried call may cost more than it reports. The **monthly-cost** reservation covers three attempts (cost x 3); the **daily token** reservation counts one attempt (tokens x 1), because the daily call cap, not the token cap, bounds repeated attempts (20 reservations a day). A request cancelled by the timeout may still be processed and billed by the service; the ledger keeps its worst case, never releasing it.
- **In-flight and failed reservations.** A reservation that is never settled (error, timeout, killed process) stays at its worst case for the rest of the month. With the largest allowed prompt (12,000 estimated tokens) and 1,000 output tokens, one such reservation is 0.024 and 83 of them reach the 2.00 ceiling (a test). Normal calls are 0.0004 to 0.002 once settled.

## Measured

| Check | Result |
|---|---|
| `tests/test_usage.py` (18) and the S21 tests in `tests/test_foundry.py`, with fakes | pass: 40 threads against a cap of 10 grant exactly 10; 4 processes against a cap of 15 grant exactly 15; a new ledger on the same file continues the count; day and month roll over with the UTC clock; failed, timed-out and cancelled calls keep their worst case and a late answer is settled; reservations in flight count; an unusable database refuses before the client is touched; an unusable ledger, an exhausted day, token or month limit all end in verified templates with the reason in the trace |
| Race found by those tests and fixed | the first connection of concurrent threads could hit `database is locked` while switching to WAL; the call was refused (fail closed, the cap was never overshot) but it was an availability bug. Initialisation now runs once per file and process, with a retry until the busy timeout; 8 repeated runs are green |
| Core suite, ruff, e2e (Playwright and axe-core), SDK adapter tests (Python 3.13), evaluation reproducibility | `pytest` 237 passed, 1 skipped (the SDK file); `ruff check` clean; `npm run e2e` 11 passed; SDK tests 11 passed; `docs/evaluation.md` regenerates identical |
| One live smoke call, through the ledger, with an output allowance of 150 tokens (`kickoff`, essential, English: one moment) | 1 call. The provider reported 686 input and 34 output tokens; the ledger settled the call at 720 tokens and 411 micro-units (0.000411): the list price 686 x 0.40 + 34 x 1.60 per million = USD 0.0003288, times 1.25, counted 1:1 as euros) from a reserved worst case several times larger; the moment verified. A second process read the same totals from the file |
| Azure deployment, read-only first | one deployment `soundpitch-mini`, capacity 10, no provisioned throughput, budget 5 EUR with spend 0 |
| Azure deployment, one change | capacity 10 to 8, in place, same model, version and SKU. Reason: the application allows 2 calls a minute and the service counts each at about 3,200 tokens (prompt plus the 1,000 `max_tokens`), so about 6,400 a minute are needed; 8,000 leaves a margin and lowers the burst possible with the credential. Reversible with the same command and `--sku-capacity 10` |

No further live evaluation was run. `docs/evidence/foundry-run.md` predates the ledger.

## What is not covered

- **Persistence in the current configuration.** Local runs: the file `backend/data/usage.sqlite` is on the host disk and survives restarts (checked with a second process). The `Dockerfile` as it was when this file was written gave no writable, persistent path (non-root user, `/srv/backend` owned by root, no volume, `SOUNDPITCH_USAGE_DB` unset), so in a container every model call would have been refused. **Since D12 the image runs `SOUNDPITCH_LLM=replay` and does not use the ledger or the SDK at all**; the live describer and its ledger are for recording replies and experiments on a developer machine. The ledger remains unprotected across deployments, replicas or ephemeral restarts, so a live model must not be served publicly from a container without a different, approved design.
- **The voice endpoint is a separate matter.** Its limits (SPEC §8, S22, D14) live in the memory of one process and are not a spending cap.
- **One host.** The ledger is a file. Two hosts, two replicas or a replaced container disk have independent counters (T06: one replica and a persistent volume, or the file resets at every deployment).
- **Other callers.** Anyone with the Azure credential, or another program using the same deployment, bypasses the ledger: the application-level limits apply only to calls made through `FoundryDescriber`, the single place that calls the client after `reserve` (checked: no other `.complete(` caller in `backend/app`). The deployment allocation is the only limit on them.
- **The bill.** The ledger estimates from the usage the service reports; Azure bills what it processed. Retried requests, a price change and delayed cost data can make the two differ.
- **No cutoff.** Pay-as-you-go has no spending stop. An automatic stop would need a budget action group calling a function that removes the deployment; it is a new paid resource and was not created.
- **Clock.** Days and months are UTC and read from the host clock; a clock set back can reopen a period.
- **Settled usage is trusted.** A provider report that is missing is replaced by an estimate; one that is wrong is not detected.
