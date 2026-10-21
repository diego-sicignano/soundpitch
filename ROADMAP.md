# Roadmap

Deadline: **27 Oct 2026, 23:59 Pacific** (28 Oct, 07:59 in Italy). Judges need the demo online **until 10 Nov, 23:59 Pacific** (11 Nov, 08:59 in Italy). See [`docs/hackathon/`](docs/hackathon/).

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
| S11 | Foundry describer against a fake client; S12 one live run (20 Oct, 26 calls) |
| S13 | Agent Framework workflow builds the same session as the plain pipeline (D13) |
| S15 | Cue sheet JSON and its committed JSON Schema (D15) |
| S19, S20 | Grounded verifier (D9): facts and words must come from the moment; adversarial and false-rejection tests |
| S21 | Model cost ledger (D11): durable limits, reserved before each call, fail closed |
| S22 | `/api/tts` speaks only issued text and is limited (D14) |
| S23 | The commentary is marked with its own `lang` |
| S24 | Replay of recorded Foundry replies, re-verified on every session (D12) |
| S25 | Security headers and a content security policy (D16) |
| S26, S27, S28 | Stored voice clips and their generation tool (dry run only: **no clip exists yet**), defensive `X-Forwarded-For`, `playbackRate` and the synthetic-voice note (D17) |
| S31 | Why the moment matters: a goal, half-time and full-time end with a sentence on what the score now means, written by code from the score state, kept apart in `Cue.context` and shown as "score context" (D18) |
| S32 | A mistyped `SOUNDPITCH_LLM` or `SOUNDPITCH_ORCHESTRATOR` is a clear `503 llm_not_configured` (also on `/api/health`) that never echoes the value, not a generic 500 (D19) |
| S29, S30 | The page offers the Azure voice only where the server has clips or a key, and says so when the browser has no voice for the language |

## Tickets

| ID | Ticket | Depends on | Acceptance | Status |
|---|---|---|---|---|
| T01 | [Register and confirm eligibility](docs/tickets/T01-register.md) | none | manual | **done** (registered, individual) |
| T02a | [Grounded verifier](docs/tickets/T02a-grounded-verifier.md) | none | S3, S19, S20 | **done** |
| T02b | [Foundry describer](docs/tickets/T02-foundry-describer.md) | T02a | S11, S12 | **done**: S11 offline, S12 live on 2026-10-20 (two runs); the model mostly copies the templates (D10) |
| T03 | [Agent Framework workflow](docs/tickets/T03-agent-framework-workflow.md) | T02b | S13 | **done**; S13 verified on Python 3.13 with the pinned packages |
| T04 | [Azure AI Speech with a real key](docs/tickets/T04-azure-speech.md) | Azure resource, **owner's approval** | S14 | todo: the client and the clip tool exist and are tested against a stub; no Speech request has ever been sent and no clip exists (`docs/DEPLOY.md`, G3) |
| T05 | [Cue sheet and JSON Schema](docs/tickets/T05-cue-sheet.md) | none | S15 | **done** |
| T06 | [Deploy to Azure Container Apps](docs/tickets/T06-deploy.md) | T11, T04 optional, **owner's approval** | S16 | offline preparation done (image built and run read-only, publish job, stored clips, defensive `X-Forwarded-For`); nothing deployed, no clip generated: each external step waits for approval (`docs/DEPLOY.md`) |
| T11 | [Record the replay file](docs/tickets/T11-record-replay.md) | T02b, prompt frozen, **owner's approval** (model calls) | S24 | **done**: recorded 2026-10-20, 26 replies, 30 of 30 windows, about 0.03 USD; the owner reviewed the Italian wording, one sentence is kept as recorded and documented |
| T07 | [Demo video and pitch](docs/tickets/T07-video-and-pitch.md) | T11, T06 | checklist | todo |
| T08 | [MCP server (optional)](docs/tickets/T08-mcp-server.md) | T03 | S17 | todo, optional |
| T09 | [Player focus (optional)](docs/tickets/T09-player-focus.md) | none | S18 | todo, optional |
| T10 | [Make the repository public and submit](docs/tickets/T10-publish-and-submit.md) | all shown | checklist | todo |

Status values: `todo`, `in progress`, `done`. Change the row in the same commit that finishes the ticket.

## Suggested schedule

| Day | Work |
|---|---|
| 20 Oct (today) | Registered. Audit, hygiene, TTS guard, language marking, replay, cue sheet, workflow, Dockerfile, smoke check, documentation |
| 21 Oct | Review and commit; start Docker Desktop and build the image; freeze the prompt; **T11** (approval) |
| 22 Oct | **T06** deploy (approval), **T04** if a Speech tier is chosen |
| 23 Oct | Rehearse the demo; fix what the deployed URL shows |
| 24 to 25 Oct | **T07** video and pitch; T08 and T09 only if there is time |
| 26 Oct | **T10**: public repository, first CI run, submit (the history was prepared locally on 21 Oct, D22: noreply address, no copy of the rules; repeat the scan after any later commit) |
| 27 Oct | Buffer. Do not change the deployment while judging runs |

## Known limits

- No blind or low-vision listener has tested it; the style follows public guidance (`docs/research/accessibility.md`).
- Planted-error figures in `docs/evaluation.md` test the verifier on the error types it was built for. They show the checks work; they are not a measure of a real model's accuracy. The hand-written corpora are small.
- The verifier proves where facts and words come from (grounding, SPEC §5). It does not prove that prose built from allowed words means what it should, and its closed vocabulary rejects most natural wording: the template fallback speaks instead.
- The live model mostly copies the template sentences (own wording: 0% in English and 13.6% in Italian in the recorded run, 1.2% and 16.0% in an earlier one). One recorded Italian sentence is not good Italian and passes the verifier, which does not check meaning.
- Model spending is limited by the application's ledger (one SQLite file per host), not by Azure: the 5 EUR budget only alerts. The judges' path makes no model call (D12).
- Speech spending has no hard cap until a pricing tier is chosen; the application's limits restart with the process (D14).
- The pitch positions are generated, not measured.
- Known, not fixed (found by an independent review on 2026-10-20, all low): two identical concurrent voice requests both call Azure and both count characters (no single flight); the per-client voice limit reads only the first `X-Forwarded-For` header line and a port suffix in that header was not checked against Container Apps; `markLanguage` is not reset after a failed load; the replay key hashes the system prompt but not the per-moment payload, so a changed template can leave a stale recorded reply that the verifier still checks (only the share of fallbacks would change); a recorded file with one invalid entry is ignored as a whole (`/api/health` then shows `replies: 0`).
- Italian wording (D20, 2026-10-21): the templates now agree with a club name (singular verbs, no article before a name). The recorded Italian sentences that kept the old wording are rejected by the verifier and replaced by the templates at attempt 2, so 14 of the 15 Italian demo sessions report 2 attempts and the model's own words survive only in the other moments; re-recording would restore them (D20 assesses it: 52 of 81 Italian moments are affected, a full run is about USD 0.03 and also redraws the English, so it was left for the owner's separate authorization). Only the owner has read the Italian; no native-speaker review is recorded.
