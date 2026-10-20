# Foundry run

Date: 2026-10-20. Model deployment: `soundpitch-mini`. Written by `python -m app.foundry_run`.

> This run happened **before** the cost ledger (D11). It used per-process caps raised for the run and 6,000 output tokens a call. With the limits now in force (2 calls a minute, 20 a day) a run of this size is refused after the first calls and the templates speak. It was not repeated.

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
