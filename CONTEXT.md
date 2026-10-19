# SoundPitch: context

Glossary and the map of the data contracts. Behaviour is in [`SPEC.md`](SPEC.md); the field-level contracts are the Pydantic models in [`backend/app/contracts.py`](backend/app/contracts.py), which is their single source of truth.

**Contract change protocol:** change `SPEC.md` first, then `backend/app/contracts.py`, then the tests, then the implementation. Update the JSON Schema files in `docs/contracts/` with `python -m app.export_schema` (ticket T05).

## Glossary

| Term | Meaning |
|---|---|
| **Match** | The one synthetic match generated from `SEED = 424242`: Northgate Red (home) 2 - 1 Harbour Blue (away). |
| **Event** | One thing that happens, every 3 to 9 seconds: pass, shot, tackle, foul, goal... with time, team, player, position and score after it. |
| **Window** | A stretch of the match, in seconds, that a session covers. |
| **Preset** | A named window: `kickoff`, `goal_1`, `goal_2`, `goal_3`, `final_whistle`. |
| **Progress** | How far a team has moved the ball towards the opponent's goal: 0 is its own goal line, 100 the opponent's. |
| **Lane** | `left`, `centre` or `right`, from the attacking team's point of view. |
| **Moment** | One thing worth describing: a goal, a shot, a build-up. Built from one or more events. |
| **Priority** | 0 to 3. **Must-say** is priority 3: kick-off, goal, half-time, full-time. |
| **Detail level** | `essential`, `standard` or `full`: the minimum priority that gets described. Must-say always is. |
| **Description** | The sentences for one moment: a `full` one and a `short` one, plus the facts it claims. |
| **Fact reference** | A claim `(event, field, value)` inside a description, such as "event 41, player, 9". |
| **Describer** | Whatever writes descriptions: the template describer, or a model on Foundry. |
| **Verifier** | Code that checks a description against the events: refs, names, numbers, length. |
| **Validation feedback** | The verifier's list of issues, sent back to the describer on a retry. |
| **Fallback** | The deterministic template description used after the retries. It always verifies. |
| **Max lag** | How long after its moment a cue may start before it is stale, by priority. |
| **Timing planner** | Fits descriptions into the silence between moments, in priority order. |
| **Cue** | A planned sentence: text, start and end in milliseconds, priority, status (`verified` or `fallback`). |
| **Earcon** | A short ball sound for one event. Stereo position and pitch follow the ball. |
| **Calm mode** | Only goals and whistles make a sound, at low volume; the voice is slower. |
| **Session** | Everything the player needs for one window and one profile: cues, earcons, ball track, trace, report. |
| **Profile** | The listener's settings: detail, language, ball sound, calm mode, speech rate (and, later, a player to follow). |
| **Cue sheet** | The machine-readable, versioned export of a session for graphics and captioning systems (SPEC §13). |
| **Scenario** | A test mode that plants errors: `bad_then_good` (wrong once) and `always_bad` (always wrong). |

## Contract map (`backend/app/contracts.py`)

| Group | Models |
|---|---|
| Match data | `Player`, `TeamInfo`, `Event`, `Match`, `MatchHeader` |
| Interpretation | `Moment` |
| Description | `FactRef`, `Description` |
| Listener | `Profile`, `Preset` |
| Plan | `Cue`, `Earcon`, `Dropped`, `BallPoint`, `TraceStep`, `PriorityStats`, `Report`, `Session` |
| HTTP | `TtsRequest`, `ErrorResponse` |

Every model rejects unknown fields and is frozen. Coming with the tickets: `CueSheet` and its items (T05), `Profile.focus` and `Profile.focus_team` (T09).
