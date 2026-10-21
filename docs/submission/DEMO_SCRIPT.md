# Demo video script (under 2 minutes)

Rules 4.4: under two minutes, a public URL, the project running on its platform (a browser), no third-party trademarks, no music you lack rights to. Judges need not watch past two minutes, so the best moment goes first. Target: about 110 seconds. Ticket: [T07](../tickets/T07-video-and-pitch.md).

Before recording: use headphones for stereo, open the demo URL in Chrome (<https://soundpitch.delightfulbay-5202fc67.italynorth.azurecontainerapps.io>; wake it with one request first, a cold start takes about 15 s; the video must show the public URL, rules 4.4), set the zoom to 125%, close other tabs, mute notifications. Start a second server with `SOUNDPITCH_LLM=always_bad` for the sabotage scene.

| Time | On screen | Voice-over (English) |
|---|---|---|
| 0:00 to 0:10 | Black, then the page title. Captions on. | "For a blind fan, football commentary assumes you can see the pitch. SoundPitch describes the match instead." |
| 0:10 to 0:35 | Choose "Goal 1: Northgate, minute 16", press Play. Let the voice and the ball sound run; the ball moves on the pitch. | (silence for a few seconds so the audio is heard) then: "It speaks like a radio commentator, and a sound moves across your headphones with the ball." |
| 0:35 to 0:55 | The goal is announced; captions show it; the scoreline changes. | "When the goal comes, you hear who scored, the score, and what it means: here, the opening goal of the match." |
| 0:55 to 1:10 | Point to the timeline: speech blocks, gaps, the yellow must-say block. | "Speech is planned into the gaps. A goal is never pushed out by routine play." |
| 1:10 to 1:35 | Second page on the `always_bad` server. Open the report: "Template fallback", attempts 3. Open "Pipeline steps". Transcript badges say "template". | "Every name, team and score in a described sentence is checked against the match events before it is spoken; the score summary after a goal is computed by code. Here a deliberately faulty test describer keeps naming the wrong player. The verifier rejects it three times and a verified template takes over. The listener never hears a wrong name." |
| 1:35 to 1:48 | Switch to Italian, then calm mode, then "My own screen reader". | "Italian or English, a calm mode, large captions, or plain text for your own screen reader." |
| 1:48 to 1:55 | Title card with the URL and the technologies. | "Model words recorded from Microsoft Foundry through the Microsoft Agent Framework, checked again by code on every request." On the title card: the demo URL, and "Microsoft Foundry, Microsoft Agent Framework". Say "open source": the repository is public. Add "hosted on Azure Container Apps" (true since 2026-10-21). Add Azure AI Speech only if `docs/DEPLOY.md` G3 is done (it is not). |

Checklist after recording:

- [ ] Under 2:00 and plays signed out on the public URL.
- [ ] The ball sound is audible and clearly moves left to right.
- [ ] No Premier League or Microsoft logos, no music.
- [ ] Captions added to the video itself.
- [ ] Every technology in the last line is true (see the table in `PITCH.md`), and "open source" is said only if the repository is public (T10).
- [ ] The Italian scene does not open the report or say "first attempt": since D20 the Italian demo sessions report 2 attempts (the corrected templates replaced recorded sentences with the old wording).
- [ ] The sabotage scene says it is a test describer (`SOUNDPITCH_LLM=always_bad`), not the recorded Foundry model, which passed the verifier at the first attempt in the recorded run (`docs/evidence/foundry-run.md`).
