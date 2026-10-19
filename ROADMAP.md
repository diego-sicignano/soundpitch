# Roadmap

Deadline: **27 Oct 2026, 23:59 Pacific** (about 07:59 on 28 Oct in Italy). Registration closes **20 Oct, 12:00 Pacific**. Judges need the demo online **until 10 Nov**. See [`docs/hackathon/`](docs/hackathon/).

Judging weights five criteria at 20% each, and ties go to criterion 1 (technology), so the items are ordered by what moves the score.

## Done (with tests)

| Row | What |
|---|---|
| S1 | Deterministic synthetic match, pinned storyline (goals 16', 52', 78'; 2-1) |
| S2 | Moments with priorities and three nested detail levels |
| S3 | Template describer (English, Italian) and the verifier |
| S4 | Retry (2) and verified template fallback; scenarios `bad_then_good`, `always_bad` |
| S5 | Timing planner: no overlaps, must-say never dropped, short variant when full does not fit |
| S6 | Profiles: detail, language, ball sound, calm mode, speech rate |
| S7 | HTTP API, WebVTT, Azure AI Speech client (tested against a stub only) |
| S8 | One-page player: speech, ball sound, captions, pitch, timeline, transcript, screen-reader output |
| S9 | axe-core clean before and after playback |
| S10 | Evaluation harness with published counts (`docs/evaluation.md`) |

## To do, in order

| # | Task | Why it matters | Done when |
|---|---|---|---|
| R1 | **Register** on the hackathon site (before 20 Oct 12:00 Pacific) | Without it you cannot submit | Confirmation seen |
| R2 | **Foundry describer** (`app/foundry.py`, `SOUNDPITCH_LLM=foundry`): one batched call per window, structured output (`full`, `short`, `refs`), prompt with the style rules | Criterion 1 and the Foundry prize; today the model is only a stand-in | Unit tests with a fake client; one real run, first-attempt pass rate written to `docs/evaluation.md` |
| R3 | **Microsoft Agent Framework workflow**: detector -> describer agent -> verifier -> conditional retry edge (max 2) -> fallback -> timing. Check the installed API with Context7 first | Criteria 1 and 2, Multi-Agent prize | Same acceptance rows pass through the workflow; trace shows the agents |
| R4 | **Azure AI Speech with a real key**: voices, rate, prefetch, cost guard | A named Azure technology, and the heart of the demo | A real mp3 plays in the page; `curl` recorded in `docs/` |
| R5 | **Cue sheet**: `GET /api/cuesheet` with a versioned JSON Schema (clock, type, text, duration, language) | The rules ask for timed, machine-readable output for overlays | Schema test; cue sheet validates for every preset |
| R6 | **Deploy** to Azure Container Apps (Dockerfile exists, not built here yet), managed identity, budget alert | Judges need a public, free demo until 10 Nov; Cloud Native prize | Public URL works from a clean browser |
| R7 | **Demo video** under 2 minutes, public on YouTube or Vimeo | Criterion 4; judges may only watch this | URL in the README |
| R8 | **Pitch text and README screenshots** | Criteria 3 and 4 | Pasted into the submission form |
| R9 | Optional: **MCP server** exposing the match tools; **player-focus mode** ("follow Marsh") | Criterion 2; a named idea in the rules | Tests; shown in the video only if finished |
| R10 | **Make the repository public** and tick every box in [`SUBMISSION_CHECKLIST.md`](docs/hackathon/SUBMISSION_CHECKLIST.md) | Rules 4.4: the repo must be public | Checklist complete, a day before the deadline |

## Suggested schedule

| Day | Work |
|---|---|
| 19 Oct (today) | Repo, docs, backend and UI done. **Register.** |
| 20 to 21 Oct | R2 and R3: Foundry describer, then the Agent Framework workflow |
| 22 Oct | R4 and R5: real voice, cue sheet |
| 23 Oct | R6: deploy and cost guards |
| 24 to 25 Oct | R7 and R8: video, pitch, screenshots; R9 if there is time |
| 26 Oct | Buffer, full test run, rehearse the demo |
| 27 Oct | Submit in the morning (Italy), before the deadline |

## Known limits

- No blind or low-vision listener has tested it; the style follows public guidance (`docs/research/accessibility.md`).
- Planted-error figures in `docs/evaluation.md` test the verifier on the error types it was built for. They show the checks work; they are not a measure of a real model's accuracy.
- The pitch positions are generated, not measured.
