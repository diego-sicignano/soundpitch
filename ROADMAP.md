# Roadmap

Deadline: **27 Oct 2026, 23:59 Pacific** (about 07:59 on 28 Oct in Italy). Registration closes **20 Oct, 12:00 Pacific**. Judges need the demo online **until 10 Nov**. See [`docs/hackathon/`](docs/hackathon/).

Judging weights five criteria at 20% each and ties go to criterion 1 (technology), so tickets are ordered by what moves the score. Each ticket lives in [`docs/tickets/`](docs/tickets/), cites the acceptance rows of [`SPEC.md`](SPEC.md) it satisfies, and is done only when its verification commands exit 0.

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

## Tickets

| ID | Ticket | Depends on | Acceptance | Status |
|---|---|---|---|---|
| T01 | [Register and confirm eligibility](docs/tickets/T01-register.md) | none | manual | todo, **before 20 Oct 12:00 PT** |
| T02 | [Foundry describer](docs/tickets/T02-foundry-describer.md) | none | S11, S12 | todo |
| T03 | [Agent Framework workflow](docs/tickets/T03-agent-framework-workflow.md) | T02 | S13 | todo |
| T04 | [Azure AI Speech with a real key](docs/tickets/T04-azure-speech.md) | Azure resource | S14 | todo |
| T05 | [Cue sheet and JSON Schema](docs/tickets/T05-cue-sheet.md) | none | S15 | todo |
| T06 | [Deploy to Azure Container Apps](docs/tickets/T06-deploy.md) | T04 | S16 | todo |
| T07 | [Demo video and pitch](docs/tickets/T07-video-and-pitch.md) | T02 to T06 as shown | checklist | todo |
| T08 | [MCP server (optional)](docs/tickets/T08-mcp-server.md) | T03 | S17 | todo |
| T09 | [Player focus (optional)](docs/tickets/T09-player-focus.md) | none | S18 | todo |
| T10 | [Make the repository public and submit](docs/tickets/T10-publish-and-submit.md) | all shown | checklist | todo |

Status values: `todo`, `in progress`, `done`. Change the row in the same commit that finishes the ticket.

## Suggested schedule

| Day | Work |
|---|---|
| 19 Oct (today) | Repo, docs, backend and page done. **T01: register.** |
| 20 to 21 Oct | T02, then T03 |
| 22 Oct | T04 and T05 |
| 23 Oct | T06 |
| 24 to 25 Oct | T07; T08 and T09 only if there is time |
| 26 Oct | Buffer, full test run, rehearse the demo |
| 27 Oct | T10: submit in the morning (Italy), a day early |

## Known limits

- No blind or low-vision listener has tested it; the style follows public guidance (`docs/research/accessibility.md`).
- Planted-error figures in `docs/evaluation.md` test the verifier on the error types it was built for. They show the checks work; they are not a measure of a real model's accuracy (T02 adds that).
- The pitch positions are generated, not measured.
