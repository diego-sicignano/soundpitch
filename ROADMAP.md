# Roadmap

Deadline: **27 Oct 2026, 23:59 Pacific** (28 Oct, 07:59 in Italy). Judges need access to the working project **until 10 Nov, 23:59 Pacific** (11 Nov, 08:59 in Italy); rule 4.8 accepts a test build, so a hosted copy is optional (D26).

Each ticket lives in [`docs/tickets/`](docs/tickets/), cites the acceptance rows of [`SPEC.md`](SPEC.md) it satisfies, and is done only when its verification commands exit 0.

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
| S11 | Foundry describer against a fake client; S12 two live runs on 20 Oct (the second, 26 calls, is the recorded one) |
| S13 | Agent Framework workflow builds the same session as the plain pipeline (D13) |
| S13 in the demo | The judges' image builds every session through the Agent Framework workflow; the page names each executor (D31) |
| S15 | Cue sheet JSON and its committed JSON Schema (D15) |
| S17 | MCP server: read-only tools (presets, match, events, moments, verified commentary, stats, recap) and a `match_report` prompt for GitHub Copilot agent mode or any MCP client, in the judges' image (D32) |
| S18 | Club and player focus: the followed club's or player's moments go up one priority and their ball sounds are louder; a "Follow" select (D29) |
| S19, S20 | Grounded verifier (D9): facts and words must come from the moment; adversarial and false-rejection tests |
| S21 | Model cost ledger (D11): durable limits, reserved before each call, fail closed |
| S22 | `/api/tts` speaks only issued text and is limited (D14) |
| S23 | The commentary is marked with its own `lang` |
| S24 | Replay of recorded Foundry replies, re-verified on every session (D12) |
| S25 | Security headers and a content security policy (D16) |
| S26, S27, S28 | Stored voice clips (200, made on 26 Oct 2026) and their generation tool, defensive `X-Forwarded-For`, `playbackRate` and the synthetic-voice note (D17) |
| S29, S30 | The page offers the Azure voice only where the server has clips or a key, and says so when the browser has no voice for the language |
| S31 | Why the moment matters: a goal, half-time and full-time end with a sentence on what the score now means, written by code from the score state, kept apart in `Cue.context` and shown as "score context" (D18) |
| S32 | A mistyped `SOUNDPITCH_LLM` or `SOUNDPITCH_ORCHESTRATOR` is a clear `503 llm_not_configured` (also on `/api/health`) that never echoes the value, not a generic 500 (D19) |
| S33 | Match statistics counted by code from the events, including possession over the last five minutes, shown as a table that follows the clock (D29) |
| S34 | Match recap written by code: score, goals with assists, the pressure before each goal; shown and read aloud at the end of a clip, and over MCP (D33) |
| S35 | The Analyst agent: an Agent Framework agent on Foundry with the SoundPitch MCP tools writes studio points, each citing one recap line or the statistics of a minute; code rejects a point whose names or numbers are not in that line, retries once, and falls back to code points; a workflow step with its own retry edge (D34) |

**Not done:** S14 (a real Azure Speech key; optional) and S16 (a hosted URL; optional, D26).

## Tickets

| ID | Ticket | Depends on | Acceptance | Status |
|---|---|---|---|---|
| T02a | [Grounded verifier](docs/tickets/T02a-grounded-verifier.md) | none | S3, S19, S20 | **done** |
| T02b | [Foundry describer](docs/tickets/T02-foundry-describer.md) | T02a | S11, S12 | **done**: S11 offline, S12 live on 2026-10-20 and recorded again on 2026-10-26 with a prompt that asks for its own wording within the vocabulary: 100% verified at attempt 1, about 29% in its own words |
| T03 | [Agent Framework workflow](docs/tickets/T03-agent-framework-workflow.md) | T02b | S13 | **done**; S13 verified on Python 3.13 with the pinned packages |
| T04 | [Azure AI Speech with a real key](docs/tickets/T04-azure-speech.md) | an Azure Speech resource | S14 | **done** (2026-10-26, D35): 200 clips made with `clips_build`; its first clip was the one-clip test that S14's planned `check_speech` would have run |
| T05 | [Cue sheet and JSON Schema](docs/tickets/T05-cue-sheet.md) | none | S15 | **done** |
| T06 | [Deploy to Azure Container Apps](docs/tickets/T06-deploy.md) | T11, T04 optional | S16 | deployed and verified once on 2026-10-21, **deleted to stop costs**; optional now (D26): the public image is the test build rule 4.8 accepts (`docs/DEPLOY.md`); no Speech clips (T04 todo) |
| T11 | [Record the replay file](docs/tickets/T11-record-replay.md) | T02b, prompt frozen (model calls) | S24 | **done**: recorded again 2026-10-26, 26 replies covering 30 of 30 first-attempt requests (5 windows x 3 detail levels x 2 languages), about 0.03 USD |
| T08 | [MCP server](docs/tickets/T08-mcp-server.md) | T03 | S17 | **done** (2026-10-26, D32) |
| T09 | [Player focus](docs/tickets/T09-player-focus.md) | none | S18 | **done** (2026-10-26, D29) |
| T12 | [Match statistics](docs/tickets/T12-match-stats.md) | none | S33 | **done** (2026-10-26, D29) |
| T13 | Match recap and MCP prompt | T12 | S34, S17 | **done** (2026-10-26, D33) |
| T14 | Analyst agent | T13, T03 | S35 | **done** (2026-10-26, D34) |

Status values: `todo`, `in progress`, `done`. Change the row in the same commit that finishes the ticket.

## Known limits

- No blind or low-vision listener has tested it; the style follows public guidance (`docs/research/accessibility.md`).
- Planted-error figures in `docs/evaluation.md` test the verifier on the error types it was built for. They show the checks work; they are not a measure of a real model's accuracy. The hand-written corpora are small.
- The verifier proves where facts and words come from (grounding, SPEC §5). It does not prove that prose built from allowed words means what it should, and its closed vocabulary rejects most natural wording: the template fallback speaks instead.
- The describer writes within the verifier's vocabulary: in the recording of 2026-10-26 28.4% of the English and 29.6% of the Italian cues are in its own words, the rest match a template. The verifier does not check meaning.
- Model spending is limited by the application's ledger (one SQLite file per host), not by Azure: the 5 EUR budget only alerts. The judges' path makes no model call (D12).
- Speech spending has no hard cap until a pricing tier is chosen; the application's limits restart with the process (D14).
- The pitch positions are generated, not measured, and so are the match statistics computed from them (possession is a share of passes, D29).
- A session with a followed player asks about a different set of moments, which has no recorded reply: in replay mode the templates describe it, verified, and the trace says so (D29).
- Known, not fixed (found by a code review on 2026-10-20, all low): two identical concurrent voice requests both call Azure and both count characters (no single flight); the per-client voice limit reads only the last `X-Forwarded-For` header line and its port suffix is parsed in the forms of SPEC §8 but was not checked against a real Container Apps proxy; `markLanguage` is not reset after a failed load; the replay key hashes the system prompt but not the per-moment payload, so a changed template can leave a stale recorded reply that the verifier still checks (only the share of fallbacks would change); a recorded file with one invalid entry is ignored as a whole (`/api/health` then shows `replies: 0`).
- Italian wording (D20): the templates agree with a club name; the recording of 2026-10-26 follows the corrected vocabulary, so every Italian session verifies at attempt 1. The author, a native speaker, reviewed the Italian.
