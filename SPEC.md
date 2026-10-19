# SoundPitch — Specification

**SoundPitch lets a blind or low-vision fan follow a football match by ear.** It turns a stream of synthetic match events into a timed audio-description track, a spatial "ball sound", and captions. Built for the Microsoft x Premier League "Inside the Game" hackathon. The spec is the authority; code follows it.

## §1 Why

- Live audio description of football is rare and mostly volunteer-run; broadcasters have only just started (Sky Sports, 10 Oct 2026: about 109 Premier League games a season).
- Good description *describes the action* in a radio style, without opinions (RNIB guidance), and must fit into the gaps of play.
- Fans also want to know where the ball is and who is attacking.

## §2 Pipeline (the five hackathon stages)

| Stage | Component | Kind |
|---|---|---|
| Ingest | `match_gen` synthetic match, 1 event every 3–9 s | code |
| Interpret | `moments` groups events into prioritised **moments** | code |
| Explain | `Describer` writes a `full` and a `short` sentence per moment | LLM (Foundry) or templates |
| Verify | `verifier` checks every name, number and attribution against the events; 2 retries, then the template fallback | code |
| Render | `timing` plans cues into the silence between moments; `render` emits cues, earcons and WebVTT | code |
| Personalize | `Profile`: detail, language, sonification, calm mode, speech rate, output channel | code |

Only code decides **what is true** and **when it is said**. The model only chooses words.

## §3 Data

- Pitch: `x` 0–100 along the length as the TV camera sees it (0 = left goal), `y` 0–100 across. Home attacks left to right in the first half, right to left in the second.
- `lane` is team-relative: `left`, `centre`, `right` from the point of view of the team attacking.
- `progress` of a team = `x` if it attacks left to right, else `100 - x` (0 = own goal line, 100 = opponent's goal line).
- Teams: `Northgate Red` (`home`), `Harbour Blue` (`away`), 11 fictional players each. Minutes are `t // 60 + 1` (1..90); no stoppage time.
- Storyline for `SEED = 424242`: goals by home at 16', away at 52', home at 78'; final score `Northgate Red 2 - 1 Harbour Blue`. Random play never scores.

## §4 Moments and detail levels

| Priority | Moments |
|---|---|
| 3 (must say) | kickoff, goal, half-time, full-time |
| 2 | shot (on, off, blocked), save, corner, dangerous free kick (`progress >= 70`), score reminder every 10 minutes |
| 1 | tackle/interception won in the opposition half or midfield, foul, throw-in, build-up reaching `progress >= 60` |
| 0 | any other run of passes/dribbles |

Detail profile → minimum priority: `essential` 2, `standard` 1, `full` 0. A run of consecutive pass, dribble, long ball and clearance events by one team is one **build-up** moment, described when it ends.

## §5 Describing and verifying

- Style: present tense, factual, no opinions, surnames only, team names, direction words relative to the attacker (`left`, `centre`, `right`).
- A `Description` has `full`, `short` and `refs`: a list of `(event_id, field, value)` claims.
- The verifier rejects a description when: a ref differs from the event; the text names a player not involved in the moment; the text contains an integer that is not a score, the minute or a score reminder minute; `full` has more than 45 words or `short` more than 15 words or `short` is longer than `full`.
- Attempt 1..3: failed moments get `ValidationFeedback` and are described again (max 2 retries); then the deterministic template description is used and the cue is marked `fallback`.
- Languages: `en` and `it`. The verifier is language-independent.

## §6 Timing

- Speech duration estimate: `words * 60000 / wpm + 300` ms, `wpm = 165 * rate` (`en`) or `155 * rate` (`it`).
- A cue may start no earlier than its moment time plus 300 ms, and not later than moment time plus the **max lag**: priority 3 → 10 s, 2 → 6 s, 1 → 5 s, 0 → 4 s.
- Cues never overlap; gap between cues at least 250 ms.
- Planning order: priority high to low, then time. For each moment try `full`, then `short`; if neither fits it is **dropped** with a reason. Priority 3 is never dropped: it takes the first free gap after its earliest start, even past the max lag.
- The result is deterministic.

## §7 Earcons (ball sound) and calm mode

One short sound per event, `pan = (x - 50) / 50` (left to right), `pitch = progress / 100` (higher near the opponent's goal). Kinds: `tick` (pass, dribble, long ball, clearance), `turnover`, `shot`, `save`, `goal`, `set_piece`, `whistle`, `whistle_long`. **Calm mode** keeps only `goal` and `whistle*` at gain 0.3 and slows speech to rate 0.9 at most.

## §8 API

| Method | Path | Result |
|---|---|---|
| `GET` | `/api/match` | teams, rosters, final score, goal list |
| `GET` | `/api/presets` | windows: `kickoff`, `goal_1`, `goal_2`, `goal_3`, `final_whistle` |
| `GET` | `/api/session?preset&detail&lang&earcons&calm&rate` | `Session` |
| `GET` | `/api/session.vtt?…` | WebVTT captions |
| `POST` | `/api/tts` `{text, lang, rate}` | `audio/mpeg` from Azure AI Speech, `501` when not configured |
| `GET` | `/api/health` | `{status, llm}` |

Errors (`{code, message}`): unknown preset → `404 preset_not_found`; invalid parameter → `422`; `/api/tts` → `501 tts_not_configured`, `502 tts_failed`, `429 rate_limited`. `Session.cues[].start_ms` is relative to the window start.

`SOUNDPITCH_LLM`: `scripted` (default, templates, no network), `bad_then_good`, `always_bad` (test scenarios: a wrong name in the first attempt, or in every attempt), `foundry` (real agents on Microsoft Foundry: **planned**, selecting it raises `NotImplementedError` until ROADMAP R2 is done).

## §9 UI (`frontend/`, plain HTML, one page, keyboard first)

Landmarks `header`, `main`, skip link. All controls are real labelled form elements. Test ids:

| Id | What |
|---|---|
| `preset`, `detail`, `lang`, `rate` | selects / range |
| `toggle-earcons`, `toggle-calm`, `toggle-captions` | checkboxes |
| `output` | select: `browser` voice, `azure` voice, `screenreader` (text into an `aria-live` region) |
| `play` | play / pause button (also `Space`) |
| `scoreline` | current score |
| `pitch` | schematic pitch with ball marker `ball` |
| `timeline` | speech blocks over time; `timeline-cue-{n}` per cue |
| `transcript`, `transcript-cue-{n}` | cues as they are spoken |
| `captions` | large caption line |
| `live-region` | `aria-live="polite"` used by the `screenreader` output |
| `report` | verification and timing figures |
| `status` | `role="status"` line: loading, ready, playing, paused, finished, errors |

Query parameters for automation: `preset` (initial window, default `goal_1`), `speed` (clock multiplier, default 1), `speech=off`.

## §10 Acceptance rows

| ID | Given | Then |
|---|---|---|
| **S1** | seed 424242 | identical output on two runs; ids sequential; times non-decreasing; goals at 16' home, 52' away, 78' home; final score 2-1; coordinates within 0–100 and lanes consistent with direction |
| **S2** | the match | every priority-3 kind is a moment at every detail level; `essential` ⊂ `standard` ⊂ `full`; build-ups are runs of one team's pass-like events |
| **S3** | the verifier | accepts template text; rejects a wrong ref, a foreign player name, a stray number, an over-long text |
| **S4** | scenarios | `bad_then_good`: every cue verified after one retry; `always_bad`: failing moments use the fallback, cues are marked `fallback`, track is complete |
| **S5** | the planner | no overlaps, gaps ≥ 250 ms, all priority-3 moments scheduled, high priority never dropped for low, `short` used when `full` does not fit, deterministic |
| **S6** | profiles | cue count `essential` < `standard` < `full` on one window; `it` text with the same event ids as `en`; calm mode keeps only goal and whistle earcons; pan sign follows `x` |
| **S7** | the API | valid `Session`; `404` for an unknown preset; WebVTT well-formed; `/api/tts` `501` unconfigured and audio bytes with a stubbed Azure |
| **S8** | the page | pressing `play` fills `transcript` in order and `timeline` with one block per cue; captions toggle; `screenreader` output writes into `live-region`; `Space` toggles play |
| **S9** | accessibility | axe-core reports no violations on the page in both states |
| **S10** | evaluation harness | across 20 seeds and all detail levels: no overlap, 100% of priority-3 moments scheduled, 100% of planted errors caught |
| **S11** | a fake Foundry client (§11) | correct JSON: every moment verified at attempt 1 with one call; wrong names on the first call: the retry prompt carries the verifier's issues and succeeds; unparsable JSON or an exception counts as a failed attempt; three bad attempts: template fallback; over the call cap: templates and the budget trace; the prompt holds only the facts listed in §11 |
| **S12** | a real Foundry deployment (manual) | `SOUNDPITCH_LLM=foundry` runs on every preset; first-attempt pass rate, retries, fallbacks and median call latency are written to `docs/evaluation.md` with the date and the model name |
| **S13** | both orchestrators (§12) | same cues, statuses and report for `scripted`, `bad_then_good`, `always_bad`; the trace names the executors; a describer that raises once is retried |
| **S14** | a real Azure Speech key (manual, §14) | `check_speech` writes a playable mp3 for `en` and `it`; the page plays it; evidence in `docs/evidence/` |
| **S15** | the cue sheet (§13) | validates against the committed schema for every preset and detail level; the committed schema equals the generated one; items sorted; descriptions never overlap; a caption has the timing of its description; the schema is served |
| **S16** | the deployed URL (§15) | `scripts/smoke.py` exits 0 against the public URL; the page loads in a clean browser; the service stays up until 10 Nov 2026 |
| **S17** | MCP (§16, optional) | tools return valid contracts; an unknown preset is a tool error |
| **S18** | player focus (§17, optional) | with a focus, moments of that player are raised by one priority up to 2, others are unchanged; earcon gain x1.5 capped at 1.0; no focus: identical to today; an invalid shirt gives `422` |

## §11 Foundry describer (`SOUNDPITCH_LLM=foundry`)

- Settings: `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`. Authentication uses the default Azure credential (`az login` locally, a managed identity in Azure). No key in the code or the image. A missing setting stops the request with a message that names it.
- One model call per attempt covers all pending moments of the window, in chunks of at most 40.
- The prompt holds the style rules of §5, the language, and for each moment only facts from its events (kind, minute, team short name, player surnames, lane, zone, score) and, on a retry, the verifier's issues for that moment. Nothing else about the match.
- The reply is a JSON array of `Description`; anything that does not parse into the contract is a failed attempt for those moments.
- The verifier, the retries (max 2) and the template fallback of §5 do not change: a model can never put an unverified sentence on air.
- A call that takes more than 20 s, or raises, is a failed attempt.
- Cost guard: at most `SOUNDPITCH_LLM_CALLS_PER_MINUTE` model calls per minute per process (default 20). Over the limit the session is built with the template describer and its trace says `llm budget exhausted: templates`. Sessions are cached per parameter set, so a repeated request costs no call.

## §12 Agent Framework workflow (`SOUNDPITCH_ORCHESTRATOR=workflow`)

The describe, verify, retry, fallback and timing flow of §5 and §6 is also expressed as a Microsoft Agent Framework workflow.

| Executor | Kind | Role |
|---|---|---|
| `MomentDetector` | code | events to moments |
| `Describer` | agent on Foundry, or templates | moments and feedback to descriptions |
| `Verifier` | code | accepts, or sends `ValidationFeedback` back |
| `Fallback` | code | template descriptions after the last failed attempt |
| `TimingPlanner` | code | cues, earcons and the report |

Edges: `MomentDetector -> Describer -> Verifier`; `Verifier -> Describer` while moments are rejected and attempts < 3 (a conditional edge carrying the feedback); `Verifier -> Fallback` when the attempts are used up; `Verifier -> TimingPlanner` and `Fallback -> TimingPlanner` when nothing is pending.

- `plain` (default) keeps the dependency-free pipeline. `workflow` needs the optional `requirements-agents.txt`.
- For the same describer both orchestrators return the same cues, statuses and report. The trace names the executors that ran.
- A describer that raises is retried like a rejected attempt; after the last one the `Fallback` runs.

## §13 Cue sheet (machine-readable output)

`GET /api/cuesheet?preset&detail&lang&earcons&calm&rate` returns a `CueSheet`, JSON, for a graphics or captioning system.

- Fields: `schema_version` (1), `preset`, `lang`, `match_clock_from` (`mm:ss` of match time at the window start), `duration_ms`, `items`.
- `items` are sorted by `at_ms` (relative to the window start). Each has `id`, `type` (`audio_description`, `caption`, `ball_sound`), `at_ms`, `duration_ms`, `priority`, `event_ids`; descriptions and captions add `text` and `status`; ball sounds add `sound`, `pan`, `pitch`, `gain`. A `caption` has the same `at_ms` and `duration_ms` as its `audio_description`.
- The JSON Schema is served at `GET /api/cuesheet.schema.json` and committed as `docs/contracts/cuesheet.v1.schema.json`; both are generated from `contracts.py`.
- Compatible changes only add optional fields. Any other change increments `schema_version`.

## §14 Azure AI Speech with a real key

- `python -m app.check_speech "Goal! Marsh scores for Northgate."` calls the synthesis function of §8 directly, writes `out.mp3`, prints its size and exits 0; on error it prints the message and exits 1.
- The page's `azure` output plays the audio of each cue, prefetching with at most 3 requests in flight. On `501` it falls back to the browser voice and says so in `status`.
- Voices: `en-GB-RyanNeural`, `it-IT-DiegoNeural`.

## §15 Hosting and cost guards

- One container image serves the page and the API (`Dockerfile`), runs as a non-root user, listens on 8000 and answers `GET /api/health`.
- Target: Azure Container Apps with public ingress and at least one replica, **until the end of judging (10 Nov 2026, 23:59 Pacific)** (rules 4.8). Settings come from environment variables and secrets; where the service supports it, a managed identity replaces keys.
- Guards: speech requests per minute (§8), model calls per minute (§11), an Azure budget alert, an upper limit on replicas.
- `python scripts/smoke.py <base-url>` checks `/api/health`, `/api/presets` and a session for every preset (valid, no overlap, must-say moments present) and exits non-zero otherwise.
- `docs/DEPLOY.md` lists the commands, the resources created and how to delete them.

## §16 MCP server (optional)

`python -m app.mcp_server` exposes the match as read-only MCP tools: `list_presets`, `get_moments(preset, detail)`, `get_session(preset, detail, lang)`. Results are the contract objects of `contracts.py` as JSON. An unknown preset is a tool error with code `preset_not_found`. The describer agent may call `get_moments` instead of receiving facts in its prompt; that must not change what the verifier accepts.

## §17 Player focus (optional)

`Profile.focus` is a shirt number and `Profile.focus_team` its side. With a focus, moments that involve that player (actor or receiver) have their priority raised by one, up to 2 (priority 3 stays reserved for must-say moments), and their earcons have gain x1.5, capped at 1.0. Descriptions do not change. Without a focus nothing changes. An invalid shirt gives `422`.
