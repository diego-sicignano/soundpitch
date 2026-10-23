# Project description

The text for the hackathon submission (rule 4.4: what was built, which Microsoft and Azure technologies it uses, what it does, what problem it solves). Checked against the repository on 2026-10-23. It names only technologies the project actually uses; the table below also lists what is not used. The repository is public (<https://github.com/diego-sicignano/soundpitch>). No hosted website is run: judges can run the public container image from the README ("For judges"; rule 4.8 accepts a test build). Ticket: [T07](../tickets/T07-video-and-pitch.md).

## One sentence

SoundPitch lets a blind or low-vision fan follow a football match by ear: a timed audio description, a ball sound that moves left and right with the play, and captions, with every description checked against the match events before it is spoken (the score summary after a goal or a whistle is computed from the score by code).

## Pitch (about 200 words)

For a blind fan, football commentary assumes you can see the pitch. Audio description exists, but coverage is patchy, and at club level it often depends on volunteers. SoundPitch generates it from match events.

A synthetic match supplies the events. Code turns them into prioritised moments. A describer writes each sentence: in the demo, words that a model on **Microsoft Foundry** (`gpt-4.1-mini`) wrote on 20 October 2026 and the project recorded (they almost always repeat the template sentences), so the demo makes no model call. A verifier lets a sentence state only facts that code takes from the events (players, teams, score, minute, position), in words from a reviewed list; wrong sentences are sent back, and after two retries a verified template takes over, so a listener never hears an invented player or score. For goals and whistles, code adds one sentence chosen from the score alone, saying what the moment means: the opening goal, the equaliser, the lead, who won. A timing planner fits the speech into the gaps so it does not talk over a goal (the length of speech is estimated; the browser voice is not measured). The page speaks with the listener's own browser voice.

Listeners choose the detail level, English or Italian, a calm mode, large captions, or plain text for their own screen reader. The output is also a versioned, machine-readable cue sheet with a JSON Schema, for captioning or graphics systems.

## Technologies

Every row is true today and points to real code.

| Technology | Used for | Where in the repository | Status |
|---|---|---|---|
| Microsoft Foundry | The describer model; the demo replays its recorded replies | `backend/app/foundry.py`, `replay.py` | **Used**: run live on 2026-10-20 (details, including a pacing bug that cost one extra invocation, in `docs/evidence/foundry-run.md`). The model writes within a verified vocabulary and almost always repeats the template wording; its words are verified again whenever a session is built |
| Microsoft Agent Framework | `FoundryChatClient`; a workflow with a retry edge and a fallback | `backend/app/foundry.py`, `workflow.py` | **Used**: `FoundryChatClient` made the recorded calls; the workflow is built and tested (T03, CI job `sdk`). It orchestrates one model and deterministic code, not autonomous agents. The public image does not include the framework (`SOUNDPITCH_LLM=replay`, `requirements.txt` only): the workflow is an option (`SOUNDPITCH_ORCHESTRATOR=workflow`), not what the demo runs |
| GitHub Actions | Tests, SDK tests, image build and smoke, and the image publish | `.github/workflows/ci.yml` | **Used**: all five jobs (backend, SDK, end-to-end, Docker, publish) green on commit `747e6f0` ([run](https://github.com/diego-sicignano/soundpitch/actions/runs/39846734463)); the workflow is started by hand (`workflow_dispatch`) because push-triggered runs did not start for this repository |
| Azure AI Speech | Neural voices, pre-generated once as clips | `backend/app/tts.py`, `clips.py`, `clips_build.py` | **Not used**: never called, no clip exists; the page uses the browser voice |
| Azure Container Apps | Optional hosting | `Dockerfile`, `docs/DEPLOY.md` | **Not hosted now**: deployed and verified once on 2026-10-21 (Consumption only, scale to zero), then deleted to stop costs; a hosted copy is optional (D26) |
| MCP | Match tools for an agent | none | **Not used**: no MCP server exists in the repository (T08 is optional) |

## What problem it solves, for whom

Blind and low-vision football fans, who today get either nothing or a commentator talking as if everyone could see. Deaf and hard-of-hearing fans get the same cues as captions. A captioning or graphics system could read the same machine-readable cue sheet; no broadcaster has used it.

## Limits

- No blind or low-vision listener has tested it yet; the style follows public guidance (`docs/research/accessibility.md`).
- The match is synthetic, as the rules require.
- The code was written with an AI coding assistant (Claude Code), directed by the owner through the specification and decision records (README, "Built with AI assistance"); the compliance reading is in `docs/hackathon/COMPLIANCE.md`.
- No native Italian speaker has reviewed the Italian commentary. In the demo, 14 of the 15 Italian sessions are re-described once by the verified templates, because the recorded model sentences used wording the corrected vocabulary no longer accepts; every moment is still verified and none falls back (D20).
- The verifier checks where facts and words come from, not the meaning of the sentence; its closed vocabulary rejects most free wording, and the template speaks instead.
