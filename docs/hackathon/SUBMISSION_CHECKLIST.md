# Submission checklist

Deadlines are in [`SUMMARY.md`](SUMMARY.md). Registration closes **20 Oct 2026, 12:00 Pacific**; the submission closes **27 Oct 2026, 23:59 Pacific**. Tick items as they are done.

## Before 20 October

- [ ] Register at <https://aka.ms/insidethegame> ("Register"). Decide: solo or a team of up to four, and who is the Representative.
- [ ] Confirm you are eligible (section 3) and that no Microsoft funding or contract is involved (4.12).

## The project (rules 4.3 and 4.4)

- [ ] Newly built after 29 Sep 2026. (First commit: 2026-10-19.)
- [ ] Uses only synthetic data. No real match data, names or logos.
- [ ] Runs as shown in the video. `npm run e2e` and `pytest` green on a clean checkout.
- [ ] Names the Microsoft and Azure technologies actually used, in the pitch.

## Hero technologies (judging criterion 1, the tie-breaker)

- [ ] Real run of the describer on **Microsoft Foundry** (see `ROADMAP.md`).
- [ ] **Microsoft Agent Framework** workflow for describer, verifier, timing.
- [ ] **Azure AI Speech** voice tested with a real key.
- [ ] Optional: **MCP** server exposing the match tools; **Azure Container Apps** hosting.

## Public repository

- [ ] Repository created on GitHub as **public** (rules: must be public to be considered).
- [ ] No secrets in the history: `git log -p | findstr /i "key secret token"` finds nothing real. `backend/.env` is not committed.
- [ ] README has the pitch, screenshots, how to run, and the technologies used.
- [ ] `LICENSE` present (MIT).

## Judges' access (4.8)

- [ ] Public URL works without login, free of charge, **until at least 10 Nov 2026 (end of judging)**.
- [ ] Cost guard on: `SOUNDPITCH_TTS_PER_MINUTE`, model call limits, a budget alert on the Azure subscription.
- [ ] Testing instructions in the README (which preset to press, expected result).
- [ ] Fallback if the live demo is down: the video and the README still show everything.

## Video (4.4)

- [ ] Under 2 minutes. Shows the project running on its target platform (a browser).
- [ ] Public URL on YouTube, Vimeo, Facebook Video or Youku.
- [ ] Has audio you made: your own voice or the project's voices. **No music** you do not have rights to; no Premier League or Microsoft logos.
- [ ] Story, in order: the problem (a blind fan, no description) -> press play -> hear the description and the ball sound -> the verifier blocking a wrong name -> the timeline of speech and silence.

## Pitch text (4.4)

- [ ] What it is, in one sentence.
- [ ] Which Microsoft and Azure technologies, listed.
- [ ] What problem it solves and for whom.
- [ ] English.

## Submit

- [ ] Fill every required field on the "Projects" page of the hackathon website before 27 Oct 23:59 Pacific (about 07:59 on 28 Oct in Italy). Do it a day early.
- [ ] Open the submitted page again and click every link (repo, video, demo).
- [ ] Do not change the project in ways that break the demo while judging runs.
