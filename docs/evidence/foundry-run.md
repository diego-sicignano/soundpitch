# Foundry runs

> **Since these runs (2026-10-21, D20):** the Italian templates were corrected (singular verbs with a club name, no article before a name). The tables below describe the runs as they were. Replayed today, the recorded Italian sentences that copied the old plural wording fail the verifier at attempt 1 and are replaced by the templates at attempt 2 (14 of 15 Italian sessions); English is unchanged.

Two runs of `python -m app.foundry_run` on 2026-10-20 against the deployment `soundpitch-mini` (`gpt-4.1-mini`, version 2025-04-14, Global Standard, capacity 8, read from Azure the same day). Run 2 is the one that produced the replay file `backend/app/replay_data/foundry_replies.json` (T11, D12); run 1 is kept as history.

## Run 2: recorded under the cost ledger (the replay file)

Made under the usage ledger (D11) with limits raised for this run only (200 calls a day, 1,000,000 tokens a day, 2 calls a minute, monthly ceiling 2.00), 1,000 output tokens a call, and a 31 s wait before each request to stay under the deployment's 8,000 tokens a minute. A throw-away ledger file held the replies.

**How it went, honestly.** It took three invocations: (1) a pacing bug (the wait was inside the call and exceeded the describer's 20 s timeout) made it fail after one request, whose reply was not stored; the bug was fixed with a test. (2) Seven calls, then stopped by the owner at a spending checkpoint. (3) Resumed with the same ledger: 19 more calls, the seven stored replies were not asked again. Total: 26 stored replies covering the 30 requests of the demo (some windows share a reply), checked with `python -m app.replay_export --check` (30 of 30).

The tables are those printed by invocation 3, which replays the seven stored replies, so they cover all 30 sessions; the latency covers only the 19 calls it made (the ledger does not store latency).

| Language | Sessions | Moments | Verified at attempt 1 | Verified at attempt 2 or 3 | Template fallback |
|---|---|---|---|---|---|
| `en` | 15 | 81 | 81 of 81 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| `it` | 15 | 81 | 81 of 81 (100.0%) | 0 (0.0%) | 0 (0.0%) |

| Language | Spoken cues the model wrote | Of those, in its own words (not a template sentence) |
|---|---|---|
| `en` | 81 | 0 (0.0%) |
| `it` | 81 | 11 (13.6%), 9 distinct sentences |

Model calls in invocation 3: 19 (0 raised). Median latency 3.16 s, p95 7.06 s, slowest 7.06 s.

**Usage and cost.** Ledger: 26 calls, 54,391 tokens, 0.03475 units (the USD list price counted as euros, plus 25%). Provider (Azure Monitor, read the same day): 28 requests and 55,116 tokens for the whole afternoon, i.e. the 26 calls, the single call of the failed first invocation (720 tokens) and one more request that carried no meaningful usage (tokens agree within 5; what it was is not known). At the list price (USD 0.40 and 1.60 per million tokens) that is about **0.028 USD**. The real bill is not known: Azure's cost data arrives 8 to 24 hours late.

**What this does not show.** The model almost always copies the template sentences it is shown; in Italian it used its own words in 9 distinct sentences. The verifier checks where facts and words come from, not the meaning, and it accepted one sentence that is not good Italian: "Reyes tira dalla destra e nello specchio la porta." (it should be "nello specchio della porta"). The owner read the other eight and found them acceptable; the ninth is kept as recorded and documented here. One run of one deployment; nothing here measures how often a model's wording is true to the play.

**Reproduce offline.** `python -m app.replay_export --check` (the file covers every request) and the tests in `backend/tests/test_replay.py` replay these exact words through the verifier. Repeating the run needs the owner's approval (it spends model calls).

## Run 1: earlier the same day, before the cost ledger

> This run happened **before** the cost ledger (D11). It used per-process caps raised for the run and 6,000 output tokens a call. With the limits now in force (2 calls a minute, 20 a day) a run of this size is refused after the first calls and the templates speak. Its replies were not kept. The provider counts 27 requests in that hour, one more than the 26 calls reported below.

Every preset (5) at every detail level (3) in English and Italian, through the real pipeline. Nothing was loosened for the run. The reasons below are the *first* issue of each rejected moment only.

| Language | Sessions | Moments | Verified at attempt 1 | Verified at attempt 2 or 3 | Template fallback |
|---|---|---|---|---|---|
| `en` | 15 | 81 | 81 of 81 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| `it` | 15 | 81 | 81 of 81 (100.0%) | 0 (0.0%) | 0 (0.0%) |

| Language | Sessions that needed a retry | Failed calls (error, timeout, unusable reply) |
|---|---|---|
| `en` | 0 of 15 | 0 |
| `it` | 0 of 15 | 0 |

| Language | Spoken cues the model wrote | Of those, in its own words (not a template sentence) |
|---|---|---|
| `en` | 81 | 1 (1.2%) |
| `it` | 81 | 13 (16.0%) |

Model calls: 26 (0 raised). Median latency 3.31 s, p95 4.52 s, slowest 4.81 s.

## Why moments were rejected (first issue, all attempts)

**`en`**
- none
- words outside the vocabulary: none

**`it`**
- none
- words outside the vocabulary: none

Review those words before the vocabulary grows (SPEC §5): a word may join only if it cannot change a fact or a relation. A rejected sentence is not an error of the product: the verified template speaks instead.
