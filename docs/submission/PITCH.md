# Project description

The text for the hackathon submission (rule 4.4: what was built, which Microsoft and Azure technologies it uses, what it does, what problem it solves). Checked against the repository on 2026-10-26. It names only technologies the project actually uses. The repository is public (<https://github.com/diego-sicignano/soundpitch>). No hosted website is run: judges can run the public container image from the README ("For judges"; rule 4.8 accepts a test build).

## One sentence

SoundPitch lets a blind or low-vision fan follow a football match by ear: a timed audio description drafted by a Microsoft Foundry model, a ball sound that moves left and right with the play, captions and live match stats, with every name, number and score checked by code against the match events before it is spoken.

## Pitch (about 200 words)

For a blind fan, football commentary assumes you can see the pitch. Audio description exists, but coverage is patchy, and at club level it often depends on volunteers. SoundPitch generates it from match events.

A synthetic match supplies the events. Code turns them into prioritised moments. A describer writes each sentence: in the demo, words that a model on **Microsoft Foundry** (`gpt-4.1-mini`) wrote on 26 October 2026 and the project recorded (about 29% in its own words), so the demo makes no model call. A second agent, the Analyst, uses the SoundPitch MCP tools to write studio points, and code rejects any point whose names or numbers are not in the line it cites. A verifier lets a sentence state only facts that code takes from the events (players, teams, score, minute, position), in words from a reviewed list; wrong sentences are sent back, and after two retries a verified template takes over, so a listener never hears an invented player or score. For goals and whistles, code adds one sentence chosen from the score alone, saying what the moment means: the opening goal, the equaliser, the lead, who won. A timing planner fits the speech into the gaps so it does not talk over a goal (the length of speech is estimated; the browser voice is not measured). The page speaks with the listener's own browser voice.

Code also counts the match statistics an analyst expects (possession as a share of passes, also over the last five minutes to show who is pressing, pass accuracy, average pass length, shots, balls won) and the page updates them as the match plays. Listeners choose the detail level, English or Italian, a club or a player to follow (their moments are described more often and sound louder), a calm mode, large captions, or plain text for their own screen reader. The output is also a versioned, machine-readable cue sheet with a JSON Schema, for captioning or graphics systems.

When a clip ends, code also writes a short summary: the score, each goal with its assist, and how much of the ball the scoring side had just before it. An AI agent such as GitHub Copilot in agent mode can use all of this over MCP, and gets only verified sentences and numbers counted by code.

In 600 generated sessions, 0 of about 13,000 planted errors got past the verifier, no two cues overlapped and every goal and whistle was spoken (`docs/evaluation.md`).

## Technologies

Every row is true today and points to real code.

| Technology | Used for | Where in the repository | Status |
|---|---|---|---|
| Microsoft Foundry | The describer model; the demo replays its recorded replies | `backend/app/foundry.py`, `replay.py` | **Used**: the describer and the Analyst agent were recorded live on 2026-10-26 (`docs/evidence/foundry-run.md`, `docs/evidence/analyst-run.md`). The describer writes within a verified vocabulary, about 29% of the spoken cues are in its own words, every one verified at the first attempt; their words are verified again whenever a session is built |
| Microsoft Agent Framework | `FoundryChatClient`; a workflow graph with a retry edge and a fallback | `backend/app/foundry.py`, `workflow.py` | **Used, and the demo runs it**: `FoundryChatClient` made the recorded calls, and the judges' image builds every session through the workflow (`SOUNDPITCH_ORCHESTRATOR=workflow`, D31): MomentDetector, Describer, Verifier, Fallback and TimingPlanner executors with a conditional retry edge, each named in the page's pipeline steps. One executor uses a model; the others are deterministic code |
| Model Context Protocol | The match as read-only tools for an AI agent: presets, match, moments, the verified commentary, statistics | `backend/app/mcp_server.py`, `.vscode/mcp.json` | **Used**: official MCP Python SDK (FastMCP); the judges' image serves it with `docker run -i --rm <image> python -m app.mcp_server`, and `.vscode/mcp.json` connects GitHub Copilot agent mode to it. An agent gets only verified sentences and numbers counted by code (D32) |
| GitHub Actions | Tests, SDK tests, image build and smoke, and the image publish | `.github/workflows/ci.yml` | **Used**: all five jobs (backend, SDK, end-to-end, Docker, publish) green on commit `b404cd2` ([run](https://github.com/diego-sicignano/soundpitch/actions/runs/40340935978)) |

Azure AI Speech: 200 stored clips made once with Azure AI Speech neural voices (`en-GB-RyanNeural`, `it-IT-DiegoNeural`) on 26 Oct 2026, served by the image with no key. Built but not in use today: Azure Container Apps hosting (deployed and verified once on 2026-10-21, then deleted to stop costs; `docs/DEPLOY.md`).

## What problem it solves, for whom

Blind and low-vision football fans, who today get either nothing or a commentator talking as if everyone could see. Deaf and hard-of-hearing fans get the same cues as captions. A captioning or graphics system could read the same machine-readable cue sheet; no broadcaster has used it.

## Limits

- No blind or low-vision listener has tested it yet; the style follows public guidance (`docs/research/accessibility.md`).
- The match is synthetic, as the rules require.
- The code was written with an AI coding assistant (Claude Code), directed by me through the specification and decision records (README, "Built with AI assistance").
- The Italian commentary was reviewed by the author, a native speaker.
- The verifier checks where facts and words come from, not the meaning of the sentence; its closed vocabulary rejects most free wording, and the template speaks instead.
