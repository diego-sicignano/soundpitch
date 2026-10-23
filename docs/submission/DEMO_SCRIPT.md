# Demo video plan (under 2 minutes)

Rule 4.4: the video must be **under two minutes**, show the project running on its intended device and platform (a browser), carry a **public URL on YouTube, Vimeo, Facebook Video or Youku** (entered on the project page of the hackathon website), and contain no third-party trademark and no music you lack rights to. Rule 4.9: everything in English or with an English translation. Judges may stop watching at two minutes, so the goal comes first. Target **about 1:50, hard limit 1:58**. Ticket: [T07](../tickets/T07-video-and-pitch.md).

The app is recorded **locally, in replay mode**, the way the judges' image runs it. The rules ask for a link for the video only; no hosted URL is needed (D26). If a hosted copy exists by then, show its address on the last card.

## Facts the plan rests on

Checked on 2026-10-22 against the running replay server (`SOUNDPITCH_LLM=replay`, 26 recorded replies) and the `always_bad` test server. Times are seconds from the start of the window.

| Fact | Value |
|---|---|
| Goal 1 window, standard detail, English | **135 s in real time**, 10 cues, all verified at attempt 1, 0 fallbacks; speech 39 s, silence 96 s |
| The goal cue | starts at **100.3 s**: "Goal! Marsh scores for Northgate, set up by Adeyemi. Northgate 1, Harbour 0. The opening goal of the match." (the last sentence is written by code from the score) |
| Lines before it | 10.3 build down the right; 15.3 "Reyes shoots from the right, on target."; 18.4 "Petrov makes the save."; 24.3; 53.3 Harbour build down the left; 60.3 throw-in; 63.3; 76.3 |
| Ball sound pan | right at 10 to 34 s (+0.92 to +0.76); sweeps to the left 37 to 60 s (-0.24 to -0.76); back to the right 63 to 79 s (-0.10 to +0.64); the goal sound at 100 s is +0.92 |
| `always_bad` test server, goal 1 | 0 of 10 verified, 10 template fallbacks, 3 attempts; trace: "verifier 1 failed, 10 of 10 rejected: Brandt is not in this moment", the same at attempts 2 and 3, then "template fallback for 10"; page sentence: "0 of 10 descriptions passed the check as written; 10 were replaced by a template that always passes."; goal cue: "It's in! Marsh finishes for Northgate, set up by Adeyemi. Northgate 1, Harbour 0. The opening goal of the match." |
| Recorded replay, goal 1, English | report sentence: "All 10 descriptions passed the check as written." |
| Italian goal cue | "Gol! Marsh segna per Northgate, assist di Adeyemi. Northgate 1, Harbour 0. È il primo gol della partita." The Italian sessions report **2 attempts** (D20): if the Italian report is shown, say why (the recorded wording predates the corrected vocabulary and the templates replaced it) |
| Cue sheet | `/api/cuesheet?preset=goal_1`, versioned, with a JSON Schema |

Not verified here: how the sounds and the browser voice **sound** (this environment has no audio device), and the Italian voice (it depends on the voices installed on the recording computer).

## The 135-second problem

A real-time run of goal 1 is longer than the whole video, and 70% of it is silence by design. The video does not use `?speed=`: it speeds the clock but not the browser voice, so lines would queue and the sounds would crowd. It is cut from **one real-time take** to the moments below, and says so on screen ("Edited: silent stretches removed") at the first cut. The page's own clock and timeline stay honest because every cut lands on a cue.

## Scenes

| Time | On screen (source) | Voice-over (your own voice) |
|---|---|---|
| **0:00 to 0:12** | Page at "Goal 1: Northgate, minute 16", score 0 - 0, captions on. Press **Space**. Hard cut to take 100.3 to 107.5 s: the goal sentence is shown in large captions (and heard, if system audio is captured); the score changes to 1 - 0; the yellow goal block on the timeline. | Silent while the goal sentence plays. At about 0:09: "That is a goal, described in words for someone who cannot see the pitch." |
| **0:12 to 0:27** | Full page, scroll slowly past the pitch and the timeline. | "Football commentary assumes you can see. SoundPitch describes the match instead: a voice, a ball sound that moves across your headphones, and captions for deaf and hard-of-hearing fans. The match is synthetic: Northgate Red against Harbour Blue." |
| **0:27 to 0:50** | Take 10.3 to 20.1 s (build down the right, the shot, the save), then cut to 53.3 to 66.5 s (Harbour build down the left, throw-in). Ball moves on the pitch, the playhead moves over the timeline. | During the gaps only: "Each line is planned into the silence between plays, left for the crowd and the ball sound." / "The sound pans with the ball and rises in pitch towards the goal." Let the voice lines play alone. |
| **0:50 to 1:18** | Second browser window, `always_bad` server, goal 1. Press play for a few seconds, then scroll to **How it was checked**: "0 of 10 descriptions passed the check as written; 10 were replaced by a template that always passes." Open **Pipeline steps**: three lines "Brandt is not in this moment", then "template fallback". Transcript badges say "template". Cut back to the recorded window: "All 10 descriptions passed the check as written." | "Every name, team and score in a sentence is checked against the match events before anyone hears it. Here a deliberately faulty test describer keeps naming a player who is not in the moment. The check rejects it three times, then a template that always passes speaks. So a listener never hears a name or a score that is not in the match events." |
| **1:18 to 1:36** | Back on the main server. Switch the language to **Italiano**, press play, and cut to the Italian goal sentence (at 100.3 s) with its caption and transcript line (no report). Say the English meaning in the voice-over ("Goal! Marsh scores for Northgate, set up by Adeyemi. Northgate 1, Harbour 0. The opening goal of the match."): rule 4.9 asks for English or an English translation of the video, and this needs no video editor. Keep the detail at **Standard** for this scene: the one recorded Italian sentence that is not idiomatic ("Reyes tira dalla destra e nello specchio la porta.", disclosed in the README and `docs/evidence/foundry-run.md`) is served only at Essential detail in Goal 1; at Standard the shot line at 15.3 s is the template "Reyes tira dalla destra, nello specchio." Tick **Calm mode**. Choose **My own screen reader (text only)** and show a line appear. Change **How much to describe** once. | "English or Italian, three levels of detail, a calm mode, large captions, or plain text for your own screen reader. Play and pause work from the space bar." |
| **1:36 to 1:52** | Browser tab on `/api/cuesheet?preset=goal_1` (JSON on screen), then the closing card (text only, no logos): "SoundPitch. Microsoft Foundry words, recorded and re-checked by code whenever a session is built. Open source, MIT. Synthetic data." | "It is also a versioned cue sheet for captioning systems. The words come from Microsoft Foundry, recorded in advance and checked again by code. Open source." |

Word count of the quoted voice-over: about 190 words, no scene above 150 words a minute (the scenes are paced so that each fits its seconds), and the goal, the voice lines and the silences carry the rest. Add captions to the video itself (T07 step 3): this project is about accessibility.

## Claims in the video, and their basis

| Claim | Basis |
|---|---|
| Every name, team and score is checked against the match events | the verifier, S4 and S20, `docs/evaluation.md` |
| Foundry wrote the words, recorded in advance, no model call while it runs | `docs/evidence/foundry-run.md`, `SOUNDPITCH_LLM=replay` |
| The Agent Framework workflow exists | `workflow.py`, CI job `sdk`; the demo does **not** run it (`SOUNDPITCH_ORCHESTRATOR=plain`), so the video says "workflow", not "agents" |
| The goal sentence ends with what the score means, written by code | S31; the page marks it "score context" |

## What the video does not claim or show

- That Azure AI Speech, Azure Container Apps or MCP are in use, or that the project is hosted on Azure: none is in use now (a hosted copy was deployed once and deleted).
- That blind or low-vision people tested it: nobody has.
- That the viewer hears the stereo movement of the ball sound or the browser voice, unless system audio is captured in the video.
- That the model writes its own commentary: it mostly repeats the template wording (`docs/evidence/foundry-run.md`); the video says "words recorded from Foundry, checked by code".
- That the verifier proves a sentence is true or good: it proves where names, numbers and words come from, not meaning (README, "Honest limits").
- "First attempt" or the report for Italian (D20), a Premier League or Microsoft logo, real players or clubs, or music.
- That the `always_bad` scene is the real model: the scene says it is a test describer.
