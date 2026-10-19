# SoundPitch

**Follow a football match by ear.** SoundPitch turns a stream of match events into a timed audio description, a ball sound that moves left and right with the play, and large captions, for blind, low-vision, deaf and hard-of-hearing fans. Every sentence is checked against the match events before anyone hears it.

Built for the [Microsoft x Premier League "Inside the Game" hackathon](docs/hackathon/SUMMARY.md). All data is synthetic: the teams (Northgate Red, Harbour Blue) and players are invented.

> **Status (19 Oct 2026):** the offline pipeline, the player page and the tests are done. Real Microsoft Foundry, Microsoft Agent Framework, a tested Azure AI Speech key and the Azure deployment are **not done yet**. The plan and the deadline are in [`ROADMAP.md`](ROADMAP.md).

## Why

Audio-described football is rare and mostly done by volunteers; broadcasters have only just started (Sky Sports began live descriptive audio on 10 Oct 2026). Good description *describes the action* like a radio commentator, says who has the ball and where it is going, and has to fit into the gaps of play. A model that invents a player or a score is worse than no description, because a listener cannot see that it is wrong. More in [`docs/research/accessibility.md`](docs/research/accessibility.md).

## What it does

- **Audio description** in English or Italian, at three detail levels: essential (goals and chances), standard (plus build-up and turnovers), full (every phase of play).
- **Ball sound**: one short sound per event. Stereo position follows the ball across the pitch, pitch rises towards the opponent's goal. Different sounds for a pass, a shot, a save, a goal, a whistle.
- **Captions** in large type, and a transcript that fills as the match plays.
- **Calm mode**: only goals and whistles make a sound, and the voice slows down.
- **Three outputs**: the browser's voice, an Azure neural voice, or plain text into an `aria-live` region for people who use their own screen reader.
- **A visible plan**: the page draws the pitch and a timeline of when the voice speaks and when it is silent, and a report of what was checked.

Try it: open the page, choose "Goal 1: Northgate, minute 16", press **Play** (or the space bar).

## How it works

```
 synthetic match ──> moments ──> describer ──> verifier ──> timing planner ──> cues, earcons, captions
 (1 event / 3-9 s)   (priority)   (templates      (names,       (fits speech into
                                   or a model)    numbers,       the silence)
                                                  facts)
                                      ^              |
                                      └── 2 retries ─┘  then the verified template fallback
```

| Stage (hackathon wording) | Module | Kind |
|---|---|---|
| Ingest | `backend/app/match_gen.py` | seeded possession simulation with a pinned storyline: goals at 16', 52', 78', final score 2-1 |
| Interpret | `moments.py` | groups events into moments with priority 0 to 3; goals, kick-off, half-time and full-time are must-say |
| Explain | `describer.py` | English and Italian templates today; a model on Foundry is planned |
| Verify | `verifier.py` | every `(event, field, value)` claim must match; only players in the moment may be named; only scores and minutes may appear as numbers; length limits |
| Render | `timing.py`, `render.py` | speech fitted into gaps in priority order, never overlapping; earcons; WebVTT |
| Personalize | `Profile` in `contracts.py` | detail, language, ball sound, calm mode, speech rate, output |

Only code decides **what is true** and **when it is said**; a model, when added, only chooses words. If a description fails verification it is sent back (two retries); after that the deterministic template, which always verifies, is used and the cue is marked `template`.

The rules for every piece are in [`SPEC.md`](SPEC.md), with acceptance rows `S1` to `S10`.

## Run it

Needs Windows with PowerShell, Python 3.13 and Node.js. Chrome is used by the end-to-end tests.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Open <http://localhost:8000>. The same server serves the page and the API, and works offline.

URL options for demos: `?preset=goal_2`, `?speed=10` (run the clock 10 times faster), `?speech=off` (no sound, for recording or tests).

## Configuration

The backend reads environment variables. Copy `backend/.env.example` to `backend/.env` (git-ignored) and load it into the shell that starts the server:

```powershell
cd backend
Get-Content .env | ForEach-Object { if ($_ -match '^\s*([^#=\s][^=]*?)\s*=\s*(.*)$') { Set-Item ("env:" + $matches[1]) $matches[2] } }
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

| Variable | Meaning |
|---|---|
| `SOUNDPITCH_LLM` | `scripted` (default); `bad_then_good` and `always_bad` plant errors to show the retry and the fallback; `foundry` is planned and raises `NotImplementedError` today |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Enable `POST /api/tts` and the "Azure neural voice" output. Without them the page falls back to the browser voice |
| `SOUNDPITCH_TTS_PER_MINUTE` | Cost guard for the voice endpoint, default 120 per process |

Voices: `en-GB-RyanNeural`, `it-IT-DiegoNeural`. The Azure Speech client is tested against a stub; it has **not** been run with a real key yet.

## API

| Method | Path | Result |
|---|---|---|
| `GET` | `/api/match` | teams, rosters, final score, goals |
| `GET` | `/api/presets` | `kickoff`, `goal_1`, `goal_2`, `goal_3`, `final_whistle` |
| `GET` | `/api/session?preset=goal_1&detail=standard&lang=en&earcons=true&calm=false&rate=1` | cues with millisecond timings, earcons, ball track, trace, report |
| `GET` | `/api/session.vtt?...` | the same cues as WebVTT captions |
| `POST` | `/api/tts` | `audio/mpeg` from Azure AI Speech |
| `GET` | `/api/health` | status and describer mode |

## Tests

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q; cd ..          # 67 tests
cd backend; .\.venv\Scripts\python.exe -m ruff check .; cd ..
npm install; npm run e2e                                             # 11 browser tests, with axe-core
```

`npm run e2e` starts three servers itself (ports 8100 to 8102: normal, `always_bad`, `bad_then_good`) and checks that the page has no accessibility violations before and after playback.

### Evaluation

`python -m app.evaluate --seeds 20` counts, over 600 generated sessions (20 matches, 5 windows, 3 detail levels, 2 languages), see [`docs/evaluation.md`](docs/evaluation.md):

- **0 overlapping cues**; **960 of 960** must-say moments spoken.
- Priority 1 and 0 moments (turnovers, build-ups, routine passing) are spoken 98.8% of the time; the rest could not fit before they went stale and are dropped on purpose.
- Speech takes 18.9% of the window; the rest is silence left for the crowd and the ball sound.
- The verifier rejects 100% of planted errors (a wrong player, a stray number, a wrong fact, an unrelated event, over-long text), and the retry and fallback paths behave as specified in 200 of 200 runs each.

Be careful with that last line: the planted errors are the kinds the verifier was built to catch, so it shows the checks work, not how accurate a real model will be. That measurement needs the Foundry describer (ROADMAP R2).

## Docker

```powershell
docker build -t soundpitch .
docker run -p 8000:8000 --env-file backend/.env soundpitch
```

The `Dockerfile` has **not been built or run** yet. Hosting on Azure Container Apps is ROADMAP R6.

## Honest limits

- No blind or low-vision listener has tested it. The style follows public guidance (RNIB, Sky Sports' radio-style description) and is unvalidated.
- The match is generated, so pitch positions are plausible, not measured.
- Foundry, Agent Framework, MCP and Azure hosting are planned, not built.
- The browser voice varies by browser and operating system.

## Hackathon files

| | |
|---|---|
| [`docs/hackathon/OFFICIAL_RULES.md`](docs/hackathon/OFFICIAL_RULES.md) | the Official Rules, verbatim |
| [`docs/submission/`](docs/submission/) | drafts of the pitch and of the under-two-minute demo video script |
| [`docs/tickets/`](docs/tickets/) | the work items T01 to T10 left before the deadline |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | why the project is built the way it is |
| [`docs/hackathon/SUMMARY.md`](docs/hackathon/SUMMARY.md) | dates, what to submit, prizes, judging, and how SoundPitch maps to them |
| [`docs/hackathon/SUBMISSION_CHECKLIST.md`](docs/hackathon/SUBMISSION_CHECKLIST.md) | the list to finish before 27 Oct 2026, 23:59 Pacific |
| [`docs/research/competitors.md`](docs/research/competitors.md) | the other public entries we looked at |
| [`docs/research/accessibility.md`](docs/research/accessibility.md) | sources on audio description and the design rules we derived |

## Repository map

```
SPEC.md            behaviour, test ids, acceptance rows S1-S18
CONTEXT.md         glossary and the map of the data contracts
ROADMAP.md         done, tickets T01-T10, schedule
CLAUDE.md          instructions for the coding assistant used on this repo
backend/app/       match_gen, moments, describer, verifier, timing, render, pipeline, tts, evaluate, main
backend/tests/     pytest suite
frontend/          index.html, app.js, styles.css (no build step)
e2e/               Playwright tests with axe-core
docs/              hackathon rules and summary, research, tickets, decisions, submission drafts, evaluation
.github/           CI: backend tests, end-to-end tests, Docker build
```

## Licence

[MIT](LICENSE). The hackathon rules grant Microsoft and the Premier League a licence to use submissions; see section 7 of the rules.
