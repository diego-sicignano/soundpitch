# Pitch

Status: ready to paste, for the project as it stands. Checked against the repository on 2026-10-21: everything in the sections "One sentence", "Pitch" and "Technologies named" is true of the code and the evidence in it today. Rules 4.4 ask the pitch to name the Microsoft and Azure technologies *used*, so the text below names only those. Two things the rules need are still outside the repository: a public demo URL and a public repository (see "Before submitting"). Ticket: [T07](../tickets/T07-video-and-pitch.md).

## One sentence

SoundPitch lets a blind or low-vision fan follow a football match by ear: a timed audio description, a ball sound that moves left and right with the play, and captions, with every description checked against the match events before it is spoken (the score summary after a goal or a whistle is computed from the score by code).

## Pitch (about 200 words)

For a blind fan, football commentary assumes you can see the pitch. Audio description exists, but coverage is patchy, and at club level it often depends on volunteers. SoundPitch generates it from match events.

A synthetic match supplies the events. Code turns them into prioritised moments. A describer writes each sentence: in the demo, words that a model on **Microsoft Foundry** (`gpt-4.1-mini`) wrote on 20 October 2026 and the project recorded, so the demo makes no model call. A verifier lets a sentence state only facts that code takes from the events (players, teams, score, minute, position), in words from a reviewed list; wrong sentences are sent back, and after two retries a verified template takes over, so a listener never hears an invented player or score. For goals and whistles, code adds one sentence chosen from the score alone, saying what the moment means: the opening goal, the equaliser, the lead, who won. A timing planner fits the speech into the gaps so it never talks over a goal. The page speaks with the listener's own browser voice.

Listeners choose the detail level, English or Italian, a calm mode, large captions, or plain text for their own screen reader. The output is also a versioned, machine-readable cue sheet with a JSON Schema, for captioning or graphics systems.

## Technologies named

Every row is true today and points to real code. Name in the submission only the rows marked **used**.

| Technology | Used for | Where in the repository | Status |
|---|---|---|---|
| Microsoft Foundry | The describer model; the demo replays its recorded replies | `backend/app/foundry.py`, `replay.py` | **used**: run live on 2026-10-20 (details, including a pacing bug that cost one extra invocation, in `docs/evidence/foundry-run.md`). Say plainly that the model writes within a verified vocabulary and often repeats the template wording, and that its words are verified again on every request |
| Microsoft Agent Framework | `FoundryChatClient`; a workflow with a retry edge and a fallback | `backend/app/foundry.py`, `workflow.py` | **used**: `FoundryChatClient` made the recorded calls; the workflow is built and tested (T03, CI job `sdk`). Say it orchestrates one model and deterministic code, not autonomous agents, and that the public image does **not** include the framework (`SOUNDPITCH_LLM=replay`, `requirements.txt` only): the workflow is an option (`SOUNDPITCH_ORCHESTRATOR=workflow`), not what the demo runs |
| GitHub Actions | Tests, SDK tests, image build and smoke | `.github/workflows/ci.yml` | **not named**: the workflow file exists but has never run (no remote). Name it, and say it passes, only after the first push shows a green run |
| Azure AI Speech | Neural voices, pre-generated once as clips | `backend/app/tts.py`, `clips.py`, `clips_build.py` | **not used**: never called, no clip exists. Do not name it |
| Azure Container Apps | Public demo | `Dockerfile`, `docs/DEPLOY.md` | **not used**: nothing is deployed. Do not name it |
| MCP | Match tools for the agent | none | **not used**: `backend/app/mcp_server.py` does not exist (T08 is optional). Do not name it |

## Before submitting

These are outside the repository and are the owner's to do (ROADMAP T06, T10). If one is done before the deadline, add its sentence and tick its row above.

- A public demo URL that works until 10 Nov 2026, 23:59 Pacific. Without Azure Container Apps the pitch names no hosting service; with it, add "hosted on Azure Container Apps".
- A public repository. Then add "open source (MIT)" to the pitch and the video.
- A green first CI run. Then GitHub Actions may be named.
- Azure AI Speech clips committed (G3 of `docs/DEPLOY.md`). Then add "or Azure AI Speech neural voices, pre-generated as clips" after the sentence about the browser voice.

## What problem it solves, for whom

Blind and low-vision football fans, who today get either nothing or a commentator talking as if everyone could see. Deaf and hard-of-hearing fans get the same cues as captions. Broadcasters get a verified, machine-readable description track instead of hand-written scripts.

## Honest limits to state if asked

- No blind or low-vision listener has tested it yet; the style follows public guidance (`docs/research/accessibility.md`).
- The match is synthetic, as the rules require.
- The code was written with an AI coding assistant (Claude Code), directed by the owner through the specification and decision records (README, "Built with AI assistance"); the compliance reading is in `docs/hackathon/COMPLIANCE.md`.
- No native Italian speaker has reviewed the Italian commentary. In the demo, 14 of the 15 Italian sessions are re-described once by the verified templates, because the recorded model sentences used wording the corrected vocabulary no longer accepts; every moment is still verified and none falls back (D20).
- The verifier checks where facts and words come from, not the meaning of the sentence; its closed vocabulary rejects most free wording, and the template speaks instead.
