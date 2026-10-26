# Foundry run

Date: 2026-10-26. Model deployment: `soundpitch-mini`. Written by `python -m app.foundry_run`.

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
| `en` | 81 | 23 (28.4%) |
| `it` | 81 | 24 (29.6%) |

Model calls: 26 (0 raised). Median latency 3.40 s, p95 5.29 s, slowest 8.27 s.

## Why moments were rejected (first issue, all attempts)

**`en`**
- none
- words outside the vocabulary: none

**`it`**
- none
- words outside the vocabulary: none

Review those words before the vocabulary grows (SPEC §5): a word may join only if it cannot change a fact or a relation. A rejected sentence is not an error of the product: the verified template speaks instead.
