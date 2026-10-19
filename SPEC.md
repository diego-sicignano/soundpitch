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

Query parameters for automation: `speed` (clock multiplier, default 1), `speech=off`.

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
