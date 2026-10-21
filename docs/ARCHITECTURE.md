# Architecture

How a synthetic football match becomes a verified, timed audio description. Behaviour is specified in [`SPEC.md`](../SPEC.md); this guide shows how the pieces fit and where to start reading. The reasons for the choices are in [`DECISIONS.md`](DECISIONS.md). The field-level contracts are the Pydantic models in `backend/app/contracts.py`.

## The idea in one paragraph

A blind listener cannot see that a description is wrong, so an invented player or score is worse than silence. SoundPitch therefore splits the work: **code decides what is true** (which event happened, who was involved, the score, the minute, where the ball is) **and when it is said**; a model, when there is one, **only chooses words** inside a vocabulary the code derived from the facts of that moment. Every description is checked before it can be spoken (the one sentence code adds after the check, the score context of S31, is computed from the score and covered by tests instead), and when a model's sentence is not good enough a deterministic template, which always passes the same check, speaks instead.

## Data flow, with one goal

The window `goal_1` (match seconds 815 to 950, "Goal 1: Northgate, minute 16") at detail `essential`:

| Step | Module | What happens | Example |
|---|---|---|---|
| Ingest | `match_gen.py` | `generate_match(424242)` returns the whole match, 896 events, one every 3 to 9 seconds, goals pinned at 16', 52', 78' | event 159: Adeyemi passes to Marsh; event 160: Marsh scores, score 1-0 |
| Interpret | `moments.py` | consecutive events become **moments** with a priority 0 to 3; a goal is priority 3 (must say) | moment 3, `goal`, events `[159, 160]` |
| Facts | `describer.facts` | the code derives what a sentence about this moment may state, as **refs** `(event, field, value)` and as ready-made **phrases** | key `goal_assist`; `Marsh`, `Northgate`, `set up by Adeyemi`, `Northgate 1, Harbour 0` |
| Explain | `describer.py` / `foundry.py` / `replay.py` | a describer returns a `full` and a `short` sentence per moment; **its refs are replaced by the code's** | "It's in! Marsh finishes for Northgate, set up by Adeyemi. Northgate 1, Harbour 0." |
| Verify | `verifier.py` | grounding checks (below); a failure goes back with its issues, at most twice more | accepted |
| Fallback | `describer.TemplateDescriber` | for moments still rejected after three attempts; it must itself verify or the session fails | status `fallback` on the cue |
| Context | `stakes.py`, `pipeline.apply_context` | after verification, code appends one sentence on what the score now means (goal, half-time, full-time only) to the `full` text and keeps it in `Cue.context` | "The opening goal of the match." |
| Render | `timing.py`, `render.py` | speech is planned into the silences by priority, never overlapping; one earcon per event; WebVTT | cue 3 at 100.3 s to 107.9 s |
| Serve | `main.py`, `cuesheet.py` | `/api/session`, `/api/session.vtt`, `/api/cuesheet`, the static page | |

## Reading order

1. `contracts.py`: the vocabulary of the whole system, in about 250 lines.
2. `match_gen.py`, `pitch.py`: the synthetic match and the geometry (lanes, progress).
3. `moments.py`: events to moments, priorities and detail levels.
4. `describer.py`: the English and Italian templates (`LEX`), `facts`, and the test describers.
5. `verifier.py`: the heart of the safety argument. Read `Verifier.check`, `_grounding`, `_position`.
6. `pipeline.py`: `describe_step`, `verify_step`, `fallback_step`, `assemble_session`; the retry loop is nine lines. `stakes.py` is the score-context sentence (about 80 lines).
7. `timing.py`, `render.py`: planning speech into silence; the ball sound; captions.
8. `foundry.py`, `usage.py`: the live model behind its prompt, its parser and its cost ledger. `replay.py`: recorded replies.
9. `workflow.py`: the same steps as a Microsoft Agent Framework graph.
10. `main.py`, `tts.py`, `cuesheet.py`, then `frontend/app.js`.

## The model boundary

```
facts of one moment ──> prompt ──> model ──> JSON reply ──> parse ──> Description ──> VERIFIER ──> cue
(code)                  (code)    (words)                   (code)    (refs = code's)  (code)
```

- **What the model sees** (`foundry.build_prompt`): for each moment only its template key, the player's surname, the team's short name, the canonical phrases, the vocabulary of that key, the places a name or a phrase may stand, one or two example sentences made of the same facts, and, on a retry, the verifier's issues. No other player, no other event, nothing a client sent.
- **What it cannot change**: the refs (the code attaches its own), the timing, the choice of moments, the order, whether a sentence is spoken.
- **What the verifier proves** (`SPEC.md` §5): ids and language match; refs equal the code's facts; every name is the moment's own; every number is a score, the minute or a reminder minute; relations (score, assist, build-up chain, lane, zone, direction) appear only as exact code-built phrases; every other word is in the closed vocabulary of the moment's template key; no symbol, emoji or control character; the sentence says what happened; names and phrases stand only where a template stands them; the required facts are there; lengths are capped. A check that raises rejects.
- **What it does not prove**: that prose built from allowed words means what it should. "Foul of Harbour." is accepted (a foul *by* a Harbour player, worded like a foul *against* Harbour) because the position rule looks one word to each side; looking two words back closes it but rejects a third of the sentences a careful human writes. This is a recorded trade-off (D9), and the reason the safe side is the template.
- **Caches never skip the check.** A model reply may be stored (by the ledger) or recorded (for replay), but a stored reply is data: it becomes `Description`s and the pipeline verifies them on every session like any other.

## The score context (S31)

A goal says who scored and the score; a listener should also hear what it means. `stakes.context` reads only the score state: the scorer and the score after the goal on the goal event, the score before it on the event before, and the score at the whistle. It picks one fixed phrase per situation (opening goal, level, take the lead, extend, pull one back; who leads at the break; who won or drew), in English or Italian. `pipeline.apply_context` appends it to the `full` text after the verifier has accepted the description, and `Cue.context` keeps it apart so the page can mark it "score context". Both orchestrators and the clip tool call it from the same place, so a spoken text and a clip text cannot differ. It touches no prompt, no recorded reply and no replay key. The verifier does not check it: its correctness is the tests in `backend/tests/test_stakes.py` and a short list of phrases. If the events disagree about the score, there is no sentence. See SPEC §5 and D18.

## Describers and modes

| `SOUNDPITCH_LLM` | Describer | Needs | Use |
|---|---|---|---|
| `scripted` (default) | `TemplateDescriber` | nothing | tests, offline, the fallback itself |
| `bad_then_good`, `always_bad` | `FlawedDescriber` | nothing | show the retry and the fallback |
| `replay` | `ReplayDescriber`: a Foundry reply recorded earlier for the same request, else the templates | the JSON file in `backend/app/replay_data/` | the judges' demo: no key, no network, no cost |
| `foundry` | `FoundryDescriber` through Agent Framework's `FoundryChatClient` | the optional packages, `az login`, the ledger | recording replies, live experiments |

`SOUNDPITCH_ORCHESTRATOR=workflow` runs the same steps as an Agent Framework graph (`workflow.py`): executors `MomentDetector`, `Describer`, `Verifier`, `Fallback`, `TimingPlanner`; the retry is a conditional edge from `Verifier` back to `Describer`; messages are immutable. It returns the same cues, statuses and report as the plain loop (test S13) and names each step's executor in `Session.trace`. Only the `Describer` touches a model.

## Controls on cost and abuse

| Surface | Control | Limit of the control |
|---|---|---|
| Live model | `usage.py`: one SQLite file; each call reserves its worst case in one `BEGIN IMMEDIATE` transaction against per-minute, per-day, token and monthly-estimate limits; fail closed | one host; estimates, not the bill; Azure's budget only alerts |
| Judges' path | `replay` mode makes no model call | the words are those of one recorded run |
| Voice (`/api/tts`) | only text a session returned; audio cache; per-client, per-process, per-day and per-month limits (SPEC §8, S22) | in memory, restart at zero; the pricing tier of the Speech resource is the only hard cap |
| Sessions | at most 256 kept; one built during an outage or over the model cap is not kept | `rate` is part of the key, so many rates rebuild sessions (cheap with templates, a cost with a live model) |

## Frontend and accessibility

`frontend/` is one page, no build step, no external request. Semantic landmarks, a skip link, labelled controls, keyboard operation (`Space` toggles play), visible focus, `prefers-reduced-motion`. The transcript, captions and live region carry the session's `lang`. The ball sound is synthesised with the Web Audio API (stereo pan = `x`, pitch = progress). Output channels: browser voice, Azure voice (prefetching three clips at a time; offered only where `GET /api/voice` says the server has clips or a key, S29), or plain text into an `aria-live` region. When the browser has no voice for the language, the status line says so (S30). The transcript marks the score-context sentence apart from the description (S31). Tested with axe-core before and after playback (`e2e/soundpitch.spec.ts`). Not tested with real screen-reader users.

## Where each guarantee is tested

| Claim | Tests |
|---|---|
| The match is deterministic with the pinned storyline | `test_match.py` (S1) |
| Moments and detail levels | `test_moments.py` (S2) |
| Timing never overlaps, never drops a must-say moment | `test_timing.py` (S5), `evaluate.py` over 600 sessions (S10) |
| The verifier rejects altered descriptions, and what it wrongly rejects | `test_verifier.py` (S3), `test_grounding.py` (S19, S20), `docs/evaluation.md` |
| Retry and fallback | `test_pipeline.py` (S4), e2e scenarios |
| The model adapter, cost ledger and caches | `test_foundry.py` (S11), `test_usage.py` (S21), `test_foundry_sdk.py` (needs the packages) |
| Replay | `test_replay.py` (S24) |
| Workflow equals plain pipeline | `test_workflow.py` (S13, needs the packages) |
| Cue sheet and its schema | `test_cuesheet.py` (S15) |
| Score context | `test_stakes.py`, the S31 test in `e2e/soundpitch.spec.ts` |
| Voice guard | `test_tts_guard.py`, `test_api.py` (S22, S7) |
| Page behaviour, language marking and axe | `e2e/soundpitch.spec.ts` (S8, S9, S23) |

What the evaluation cannot show is spelled out in `docs/evaluation.md` and in the README's "Honest limits": the planted errors were written knowing the verifier, the hand-written corpora are small, and no independent human has judged whether accepted sentences are true to the play.
