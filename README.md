# SoundPitch

**Follow a football match by ear.** SoundPitch turns the events of a synthetic match into a timed audio description, a ball sound that moves left and right with the play, captions and live match stats, for blind, low-vision, deaf and hard-of-hearing fans. A model on **Microsoft Foundry** drafts the words; code checks every name, number and score against the match events before anyone hears them.

Built for the [Microsoft x Premier League "Inside the Game" hackathon](https://github.com/microsoft/insidethegamehackathon). All data is synthetic: the teams (Northgate Red, Harbour Blue) and the players are invented. This project is not affiliated with, endorsed by or sponsored by Microsoft or the Premier League.

**Why it matters.** Football commentary assumes you can see the pitch. Live audio description of football exists, but it is rare and often depends on volunteers. SoundPitch generates it from match events, in the gaps of play, in English or Italian.

**What the checks show** (`docs/evaluation.md`, 600 generated sessions, no model involved):

- 0 of about 13,000 planted errors (wrong player, wrong team, wrong score, a stray number, an opinion, an emoji) got past the verifier.
- 0 overlapping cues, and all 960 must-say moments (goals, kick-offs, whistles) spoken.
- The live model run on 20 Oct 2026: every reply checked, and a wrong reply never spoken, because after two retries a template that always passes takes over.

## For judges

Nothing to sign up for and nothing to pay for. Run the tested image, which works offline in replay mode:

```
docker run -p 8000:8000 ghcr.io/diego-sicignano/soundpitch:b404cd2a0342babe32716d8c7aac1203dc981c99@sha256:a478bacd77336714b8538bee36f4e56e86752b810880ea5b623dc0ec50be91cd
```

The image is published for `linux/amd64`; on an Apple Silicon Mac add `--platform linux/amd64` (Docker's emulation, slower start). Its CI run and digest check: [`docs/DEPLOY.md`](docs/DEPLOY.md). Or use GitHub Codespaces or a local clone ("Run it" below). Then, on <http://localhost:8000>:

1. Choose **Goal 1: Northgate, minute 16** and press **Play** (or the space bar). The window runs about 2 minutes 15 seconds; the goal comes at about 1 minute 40, and the gaps are silence by design. Use headphones: the ball sound moves with the play. The goal ends with what it means ("The opening goal of the match."), and when the clip ends a summary written by code is shown and read aloud.
2. Watch **Match stats** fill in as the clock runs: possession, passes completed, pass accuracy, average pass length, shots, balls won.
3. Under **Follow**, pick **Marsh** with **Essential** detail: that player's moments are described too (4 descriptions become 7) and his ball sounds are louder.
4. Open **How it was checked**: how many sentences were verified, how many fell back to a template, and the pipeline steps, each named by its Microsoft Agent Framework executor.
5. Try **Italiano**, **calm mode** and the "My own screen reader" output.
6. **From an AI agent (MCP):** open the repository in VS Code, start the `soundpitch` server from `.vscode/mcp.json` (it runs the same image with `python -m app.mcp_server`), and ask GitHub Copilot in agent mode, for example "Using soundpitch, who had more possession at half-time?". It calls the read-only tools `get_stats` and `get_commentary` and gets only verified sentences and numbers counted by code. (The server was checked with the MCP SDK's own stdio client.)
7. The same session as JSON for a graphics or captioning system: <http://localhost:8000/api/cuesheet?preset=goal_1> and its [JSON Schema](docs/contracts/cuesheet.v1.schema.json).
8. To see the safety net, start a second container with `-e SOUNDPITCH_LLM=always_bad -p 8001:8000` and open <http://localhost:8001>: every model sentence is wrong, the verifier rejects it three times and a verified template speaks.

The image runs `SOUNDPITCH_LLM=replay`: words that the Foundry model wrote on 20 Oct 2026, recorded and checked again by the verifier each time a session is built. It needs no key and makes no model call, so it costs nothing however many people use it (D12). A hosted copy on Azure Container Apps was deployed and verified once, then deleted to stop costs ([`docs/DEPLOY.md`](docs/DEPLOY.md)).

## What it does

- **Audio description** in English or Italian, at three detail levels: essential (goals and chances), standard (plus build-up and turnovers), full (every phase of play).
- **Ball sound**: one short sound per event. Stereo position follows the ball across the pitch, pitch rises towards the opponent's goal. Different sounds for a pass, a shot, a save, a goal, a whistle.
- **Why the moment matters**: a goal, half-time and full-time end with one sentence on what the score now means ("That makes it level.", "Northgate take the lead.", "Northgate win."), written by code from the score and never by a model; the page marks it as "score context" (`SPEC.md` §5, D18).
- **A match summary**, written by code, when the clip ends: the score, each goal with its assist and how much of the ball the scoring side had in the five minutes before ("Northgate had 68% of the passes in the five minutes before."); it is shown and read aloud (`SPEC.md` §19).
- **Match stats** for the listener who wants numbers: possession (share of passes, since kick-off and over the last five minutes, so you can tell who is pressing now), passes completed, pass accuracy, average pass length in metres, shots, shots on target and balls won, counted by code from the events and updated as the match plays (`SPEC.md` §18).
- **Follow a club or a player**: their moments are described more often and their ball sounds are louder (`SPEC.md` §17).
- **Captions** in large type, and a transcript that fills as the match plays. The commentary is marked with its own `lang`, so a screen reader switches voice for Italian.
- **Calm mode**: only goals and whistles get a ball sound, and the voice slows down.
- **Your choice of voice**: an Azure neural voice (the default: 200 stored clips made once with Azure AI Speech neural voices (`en-GB-RyanNeural`, `it-IT-DiegoNeural`) on 26 Oct 2026, so the judges' image speaks it offline with no key), the browser's own voice, or plain text into an `aria-live` region for people who use their own screen reader. The page says the neural voice is synthetic.
- **A visible plan**: the page draws the pitch and a timeline of when the voice speaks and when it is silent, and a report of what was checked.
- **A machine-readable cue sheet** (`/api/cuesheet`) with a versioned JSON Schema, and WebVTT captions.
- **Tools for AI agents** over the Model Context Protocol: an assistant such as GitHub Copilot in agent mode can ask for the raw events, the verified commentary, the moments, the statistics and the summary, and the `match_report` prompt asks it to write a report from those alone (`SPEC.md` §16).

## Screenshots

Local run in replay mode (recorded Foundry replies, no network), window "Goal 3: Northgate, minute 78", after playback. The goal sentence is verified; the italic closing sentence with the "score context" badge is written by code from the score and is not covered by the verifier.

![The SoundPitch player after Goal 3, in English: the large caption, the listening settings, the pitch with the timeline of speech and silence, the match stats table, the transcript with the "checked" and "score context" badges, and the report "How it was checked".](docs/images/player-goal-en.png)

![The same window in Italian: the commentary is marked with its own language, and the score-context sentence is in Italian.](docs/images/player-goal-it.png)

## How it works

```
 synthetic match ──> moments ──> describer ──> verifier ──> timing planner ──> cues, earcons, captions
 (1 event / 3-9 s)   (priority)   templates,     names,       fits speech into    WebVTT, cue sheet
                                  recorded or    numbers,     the silence
                                  live model     facts
                                      ^              |
                                      └── 2 retries ─┘  then the verified template fallback
```

Only code decides **what is true** and **when it is said**; a model only chooses words. A sentence that fails verification is sent back twice, then the deterministic template (which always verifies) speaks and the cue is marked `fallback`. After verification, code appends to a goal, half-time or full-time sentence one more, chosen from the score alone, on what the moment means ("That makes it level.", "Northgate take the lead.", "Northgate win."). It is kept apart in `Cue.context` and is not checked by the verifier (S31, D18). A longer walk through the code, with a reading order: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

| Stage (hackathon wording) | Module |
|---|---|
| Ingest | `backend/app/match_gen.py`: a seeded possession simulation with a pinned storyline (goals at 16', 52', 78'; final score 2-1) |
| Interpret | `moments.py`: events grouped into moments with priority 0 to 3; `stats.py`: the match statistics |
| Explain | `describer.py` (templates), `foundry.py` (a model on Microsoft Foundry), `replay.py` (its recorded replies) |
| Verify | `verifier.py`: refs equal the facts the code derives; relations only as code-built phrases; every other word from a closed vocabulary; names and phrases only where a template puts them |
| Context | `stakes.py`, applied by `pipeline.apply_context`: one fixed sentence on what the score now means, for goals, half-time and full-time; not model output |
| Render | `timing.py`, `render.py`, `cuesheet.py` |
| Personalize | `Profile` in `contracts.py`: detail, language, ball sound, calm mode, speech rate, a player to follow, output |
| Orchestrate | `pipeline.py` (plain), `workflow.py` (the same steps as a Microsoft Agent Framework graph) |

**What the verifier proves, and what it does not.** Every name, team, number, score, minute and position in a sentence comes from the moment's own facts, and every other word comes from a reviewed list. It does **not** prove that prose built from allowed words means what it should: "Foul of Harbour." is accepted, for example (`SPEC.md` §5, D9). Natural wording written without the list is mostly rejected and the template speaks instead (`docs/evaluation.md`).

## Microsoft technologies actually used

| Technology | Where | State |
|---|---|---|
| Microsoft Foundry (`gpt-4.1-mini`, Global Standard) | `foundry.py` writes the words; evidence in [`docs/evidence/foundry-run.md`](docs/evidence/foundry-run.md) | the describer was recorded on 26 Oct 2026 (26 replies, about 0.03 USD): about 29% of the spoken cues are in its own words, every one verified at the first attempt; the Analyst agent's replies were recorded the same day ([`docs/evidence/analyst-run.md`](docs/evidence/analyst-run.md)) |
| Microsoft Agent Framework | `FoundryChatClient` in `foundry.py`; the workflow graph in `workflow.py` | **the judges' image runs every session through the workflow** (MomentDetector, Describer, Verifier, Fallback, TimingPlanner, with a conditional retry edge; D31); one executor uses a model, the others are code |
| Azure AI Speech | `tts.py`, `clips.py`, `clips_build.py` | **used**: 200 stored clips made once with Azure AI Speech neural voices (`en-GB-RyanNeural`, `it-IT-DiegoNeural`) on 26 Oct 2026, about USD 0.20; served from the image with no Speech key, only for text the server issued (S22, S26) |
| Azure Container Apps | `Dockerfile`, [`docs/DEPLOY.md`](docs/DEPLOY.md) | deployed and verified once on 2026-10-21 (Consumption only, scale to zero, one replica at most, replay mode, no secret), then deleted to stop costs; **not hosted now** |
| Model Context Protocol | `mcp_server.py` (official MCP Python SDK), `.vscode/mcp.json` | read-only tools for GitHub Copilot agent mode or any MCP client, served by the judges' image (D32) |
| GitHub Actions | `.github/workflows/ci.yml` | backend, SDK, end-to-end and Docker jobs green on `b404cd2` ([run](https://github.com/diego-sicignano/soundpitch/actions/runs/40340935978)); the same run published the image to GHCR |

## Run it

Python 3.13 or later and Node.js (only for the end-to-end tests). Windows PowerShell shown; on macOS or Linux use `.venv/bin/python`.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Open <http://localhost:8000>. The same server serves the page and the API, offline.

**In a browser, with no install: GitHub Codespaces.** On the repository page choose Code, Codespaces, Create codespace on main. The dev container (`.devcontainer/devcontainer.json`) builds the Python 3.13 environment, installs the backend and test dependencies and Playwright's Chromium (a few minutes). Then, in its terminal: `cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000` and open the forwarded port 8000. Tests: `cd backend && .venv/bin/python -m pytest -q`, and from the root `npm run e2e`. Verified by building the container locally and running the tests in it; a Codespace itself has not been started. URL options for demos: `?preset=goal_2`, `?speed=10` (run the clock 10 times faster; the browser voice does not speed up, so speech queues: use it to look at the pitch and the timeline, not to listen), `?speech=off` (no sound).

Optional, for the Foundry describer and the workflow: `.\.venv\Scripts\python.exe -m pip install -r requirements-agents.txt` (Python 3.13), `az login`, set `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL`. Settings are environment variables; copy `backend/.env.example` to `backend/.env` (git-ignored) and load it into the shell that starts the server:

```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^\s*([^#=\s][^=]*?)\s*=\s*(.*)$') { Set-Item ("env:" + $matches[1]) $matches[2] } }
```

| Variable | Meaning |
|---|---|
| `SOUNDPITCH_LLM` | `scripted` (default, templates); `replay` (recorded Foundry replies, no network; `/api/health` shows how many are held); `foundry` (a live model, needs the packages, the two settings below and the cost ledger); `bad_then_good`, `always_bad` plant errors to show the retry and the fallback; any other value is a `503 llm_not_configured` that names the setting and never the value (also on `/api/health`) |
| `SOUNDPITCH_ORCHESTRATOR` | `plain` (default) or `workflow` (Agent Framework graph; needs `requirements-workflow.txt`; the image uses it) |
| `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL` | The Foundry project and the deployment for `SOUNDPITCH_LLM=foundry`. `az login`; no key is used |
| `SOUNDPITCH_LLM_CALLS_PER_MINUTE`, `..._PER_DAY`, `SOUNDPITCH_LLM_TOKENS_PER_DAY`, `SOUNDPITCH_LLM_EUR_PER_MONTH`, `SOUNDPITCH_USAGE_DB` | Cost limits of the live model, kept in one SQLite file: default 2 a minute, 20 a day, 120,000 tokens a day, 2.00 EUR a month of estimated spend (never above 4.00). Over a limit, or if the file cannot be used, the call is not made and the template speaks (D11) |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Enable the live path of `POST /api/tts`; the "Azure neural voice" output is offered when these are set or when stored clips exist for the language (`GET /api/voice`); otherwise the page uses the browser voice |
| `SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE`, `SOUNDPITCH_TTS_PER_MINUTE`, `SOUNDPITCH_TTS_CHARS_PER_DAY`, `SOUNDPITCH_TTS_CHARS_PER_MONTH`, `SOUNDPITCH_TRUST_PROXY` | Brakes on the voice endpoint (defaults 30, 120, 60,000, 300,000); `SOUNDPITCH_TRUST_PROXY=1` only behind exactly one trusted proxy (SPEC §8); `SOUNDPITCH_LOG_FORWARDED=1` logs the shape of `X-Forwarded-For`, never an address |

## API

| Method | Path | Result |
|---|---|---|
| `GET` | `/api/match`, `/api/presets` | teams and final score; the windows `kickoff`, `goal_1`, `goal_2`, `goal_3`, `final_whistle` |
| `GET` | `/api/session?preset=goal_1&detail=standard&lang=en&earcons=true&calm=false&rate=1` (optional: `focus_team=home` follows a club, plus `focus=7` one player) | cues with millisecond timings, earcons, ball track, match stats, trace, report |
| `GET` | `/api/session.vtt?...` | the same cues as WebVTT captions |
| `GET` | `/api/cuesheet?...`, `/api/cuesheet.schema.json` | the session as a versioned cue sheet, and its JSON Schema |
| `GET` | `/api/voice` | What the Azure voice can do on this server: stored clips per language, and whether Speech is configured |
| `POST` | `/api/tts` | `audio/mpeg`, a stored clip or Azure AI Speech, only for text a session returned (`403` otherwise); `X-Audio-Rate` says the speed the audio already has |
| `GET` | `/api/health` | status and describer mode |
| MCP (stdio) | `python -m app.mcp_server` | tools `list_presets`, `get_match`, `get_moments`, `get_events`, `get_commentary`, `get_stats`, `get_recap`, and the prompt `match_report` (SPEC §16) |

Errors are `{code, message}`; the full contract is `SPEC.md` §8 and `backend/app/contracts.py`.

## Tests and evaluation

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q; cd ..        # the offline suite
cd backend; .\.venv\Scripts\python.exe -m ruff check .; cd ..
npm install; npm run e2e                                           # browser tests with axe-core
cd backend; .\.venv\Scripts\python.exe -m app.smoke http://localhost:8000; cd ..   # checks a running server
```

Tests that need the optional Agent Framework packages (the workflow and the SDK adapter) are skipped unless `requirements-agents.txt` is installed; CI runs them in a separate job. `npm run e2e` starts three servers itself (ports 8100 to 8102).

`python -m app.evaluate --seeds 20` counts, over 600 generated sessions, and writes [`docs/evaluation.md`](docs/evaluation.md): 0 overlapping cues, every must-say moment spoken, and the verifier's behaviour on planted errors and on hand-written commentary. **Read the limits there:** the planted errors are the kinds the verifier was built to catch, so they show the checks work, not how accurate a model is; the hand-written corpora are small (24 to 44 sentences).

## Docker

```powershell
docker build -t soundpitch .
docker run -p 8000:8000 soundpitch
```

The image runs `SOUNDPITCH_LLM=replay` and `SOUNDPITCH_ORCHESTRATOR=workflow` as a non-root user, read-only, with no key and no network needed; CI repeats the read-only, no-capability and smoke checks. No Azure voice clips exist yet, so the page speaks with the browser voice. Each tested commit's image is published on GHCR (`ghcr.io/diego-sicignano/soundpitch:<commit sha>`, public, `linux/amd64`). Deployment: [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Honest limits

- No blind or low-vision listener has tested it yet. The style follows public guidance (RNIB, Sky Sports' radio-style description).
- Not real-time: the match is generated and a whole window is planned before it plays; no model is called while it runs.
- The verifier proves where facts and words come from, not that a sentence reads well: "Foul of Harbour." is accepted (`SPEC.md` §5). The score-context sentence and the match stats are written by code and covered by tests, not by the verifier.
- The Foundry model writes within the verifier's vocabulary, so about 71% of its sentences still match a template (`docs/evidence/foundry-run.md`). The author, a native speaker, reviewed the Italian.
- The voice clips cover every sentence the demo can say; a new sentence (a changed template or recording) falls back to the browser voice until its clip is made. Model spending is capped by the application's ledger, not by Azure (D11).

## Built with AI assistance

This project was built with an AI coding assistant (Claude Code). I directed the work through the specification and its acceptance rows ([`SPEC.md`](SPEC.md)), the plan ([`ROADMAP.md`](ROADMAP.md)) and the design decisions ([`docs/DECISIONS.md`](docs/DECISIONS.md)), set the rules the assistant works by ([`CLAUDE.md`](CLAUDE.md)), made every design and spending decision, and reviewed the results.

## Repository map

```
SPEC.md            behaviour, test ids, acceptance rows S1-S33
CONTEXT.md         glossary and the map of the data contracts
ROADMAP.md         done, tickets, known limits
CLAUDE.md          instructions for the coding assistant used on this repo
backend/app/       the pipeline, the API, the verifier, the describers, the workflow
backend/tests/     pytest suite
frontend/          index.html, app.js, styles.css (no build step)
e2e/               Playwright tests with axe-core
docs/              architecture, deploy, decisions, evaluation, evidence, contracts, screenshots, tickets, the submission text
.github/           CI: backend tests, SDK tests, end-to-end tests, Docker build and smoke
```

## Licence and third-party software

[MIT](LICENSE). Under the hackathon rules (section 7) Microsoft and the Premier League receive a licence to use submissions. The Official Rules are not redistributed here; they are published at <https://github.com/microsoft/insidethegamehackathon>. All match data is synthetic and the page carries no club or league mark. Every recorded model reply was paid on the author's pay-as-you-go Azure subscription; about USD 0.05 of earlier tests used an Azure for Students credit (D23). No grant, sponsorship, contract or licence from Microsoft is involved.

Runtime, in the judges' image: FastAPI, Pydantic, Microsoft Agent Framework core and the MCP Python SDK (MIT), Uvicorn and httpx (BSD-3-Clause), and their dependencies, all under MIT, BSD, Apache-2.0, MPL-2.0 or PSF licences. Optional, for a live model: the Agent Framework Foundry package and the Azure SDK for Python (MIT), the OpenAI Python SDK (Apache-2.0). Development and tests: pytest, Ruff (MIT), Playwright (Apache-2.0), axe-core (MPL-2.0, a test tool, not shipped). Versions are pinned in `backend/requirements*.txt` and `package-lock.json`. Licences were read from the installed package metadata, and `pip-audit` and `npm audit` reported no known vulnerability, on 2026-10-26. The page uses no external script, font, image or sound: the ball sounds are synthesised in the browser.
