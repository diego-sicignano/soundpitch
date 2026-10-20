# Pitch (draft)

Status: a draft. Replace every `[confirm]` before submitting, and delete any technology that is not really used (rules 4.4: name the Microsoft and Azure technologies *used*). Ticket: [T07](../tickets/T07-video-and-pitch.md).

## One sentence

SoundPitch lets a blind or low-vision fan follow a football match by ear: a timed audio description, a ball sound that moves left and right with the play, and captions, with every sentence checked against the match events before it is spoken.

## Pitch (about 150 words)

For a blind fan, football commentary assumes you can see the pitch. Audio description exists, but it is rare and mostly done by volunteers. SoundPitch generates it from match events.

It works in five steps. A synthetic match streams events. Code turns them into prioritised moments. A describer, a model on **Microsoft Foundry** [confirm], writes each sentence. A verifier lets a sentence state only facts that the code takes from the events (players, teams, score, minute, position) and words from a reviewed list; wrong sentences are sent back, and after two retries a verified template takes over, so a listener never hears an invented player or score. A timing planner fits the speech into the gaps so it never talks over a goal. Voices come from **Azure AI Speech** [confirm].

Listeners choose detail level, English or Italian, a calm mode, large captions, or plain text for their own screen reader. The output is also a machine-readable, versioned cue sheet with a JSON Schema.

## Technologies named

Every row must be true on the day of submission and point to real code.

| Technology | Used for | Where in the repository | Status |
|---|---|---|---|
| Microsoft Foundry | The describer model; the demo replays its recorded replies | `backend/app/foundry.py`, `replay.py` | run live once (`docs/evidence/foundry-run.md`); state plainly that it writes within a verified vocabulary and often repeats the template wording; [confirm] the replay file is recorded (T11) before saying the demo shows model words |
| Microsoft Agent Framework | `FoundryChatClient`; a workflow with a retry edge and a fallback | `backend/app/foundry.py`, `workflow.py` | built and tested (T03); say it orchestrates one model and deterministic code, not autonomous agents |
| Azure AI Speech | Neural voices | `backend/app/tts.py` | [confirm] after T04 |
| Azure Container Apps | Public demo | `Dockerfile`, `docs/DEPLOY.md` | [confirm] after T06 |
| GitHub Actions | Tests, SDK tests, image build and smoke | `.github/workflows/ci.yml` | in the repository; green after the first push |
| MCP | Match tools for the agent | `backend/app/mcp_server.py` | [confirm] only if T08 is done |

## What problem it solves, for whom

Blind and low-vision football fans, who today get either nothing or a commentator talking as if everyone could see. Deaf and hard-of-hearing fans get the same cues as captions. Broadcasters get a verified, machine-readable description track instead of hand-written scripts.

## Honest limits to state if asked

- No blind or low-vision listener has tested it yet; the style follows public guidance.
- The match is synthetic, as the rules require.
- The verifier checks where facts and words come from, not the meaning of the sentence; its closed vocabulary rejects most free wording, and the template speaks instead.
