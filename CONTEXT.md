# SoundPitch: context

Glossary and the map of the data contracts. Behaviour is in [`SPEC.md`](SPEC.md); the field-level contracts are the Pydantic models in [`backend/app/contracts.py`](backend/app/contracts.py), which is their single source of truth.

**Contract change protocol:** change `SPEC.md` first, then `backend/app/contracts.py`, then the tests, then the implementation. Update the JSON Schema in `docs/contracts/` with `python -m app.cuesheet --write ../docs/contracts/cuesheet.v1.schema.json` (a test fails if it is out of date).

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
| **Verifier** | Code that checks a description against the events: identity, refs, names, numbers, length, and grounding (below). |
| **Facts** | What the code knows about a moment: its template key, the values a sentence may use and the refs that go with them (`describer.facts`). The verifier derives its expectations from it. |
| **Canonical phrase** | A fact that carries a relation, built by code and copied verbatim: the score, the assist clause, the build-up chain, the lane, zone, direction and minute phrases. |
| **Vocabulary** | The words a sentence of one template key may use besides facts and the moment's own player and team: the words of that key's templates plus articles and "and". Growing it is a review decision. |
| **Position rule** | A name or a canonical phrase stands only between the neighbour words that some template of its kind of event gives it; the start, the end and another canonical phrase count as one edge (SPEC §5, rule 6). |
| **Grounding** | The verifier's guarantee that every entity, number, score, minute, lane, zone, direction and outcome comes from the moment's facts and every other word from the vocabulary. It does not verify the meaning of the prose (SPEC §5, D9). |
| **Validation feedback** | The verifier's list of issues, sent back to the describer on a retry. |
| **Fallback** | The deterministic template description used after the retries. It always verifies. |
| **Max lag** | How long after its moment a cue may start before it is stale, by priority. |
| **Timing planner** | Fits descriptions into the silence between moments, in priority order. |
| **Cue** | A planned sentence: text, start and end in milliseconds, priority, status (`verified` or `fallback`). |
| **Earcon** | A short ball sound for one event. Stereo position and pitch follow the ball. |
| **Calm mode** | Only goals and whistles make a sound, at low volume; the voice is slower. |
| **Session** | Everything the player needs for one window and one profile: cues, earcons, ball track, trace, report. |
| **Profile** | The listener's settings: detail, language, ball sound, calm mode, speech rate (and, later, a player to follow). |
| **Cue sheet** | The machine-readable, versioned export of a session for graphics and captioning systems (SPEC §13). Items are an audio description, its caption, or a ball sound. |
| **Replay** | The describer mode `replay`: a reply a Foundry model gave earlier to the same request, read from a JSON file, checked again by the verifier on every session. No model call (SPEC §11, D12). |
| **Recorded reply** | The model's text stored under a key made of the match seed, language, attempt, moments, issues and instructions. A changed prompt changes the key. |
| **Workflow, executor** | The pipeline as a Microsoft Agent Framework graph: `MomentDetector`, `Describer`, `Verifier`, `Fallback`, `TimingPlanner`, a conditional retry edge (SPEC §12, D13). |
| **Issued text** | The text of a cue the server has returned in a session. Only issued text can be spoken by `/api/tts` (SPEC §8, D14). |
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

Every model rejects unknown fields and is frozen. `CueSheet`, `CueSheetDescription`, `CueSheetCaption` and `CueSheetBallSound` are the cue sheet (HTTP group). Coming with the tickets: `Profile.focus` and `Profile.focus_team` (T09).
