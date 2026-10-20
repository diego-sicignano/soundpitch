# Submission checklist

Deadlines are in [`SUMMARY.md`](SUMMARY.md). Registration closed **20 Oct 2026, 12:00 Pacific** (done); the submission closes **27 Oct 2026, 23:59 Pacific** (28 Oct, 07:59 in Italy). Tick items as they are done.

## Registration

- [x] Registered at <https://aka.ms/insidethegame> as an individual (confirmed by the owner on 20 Oct).
- [x] Eligibility (section 3) and no Microsoft funding or contract (4.12) stated by the owner.

## The project (rules 4.3 and 4.4)

- [x] Newly built after 29 Sep 2026 (first commit: 2026-10-19; the owner states no code existed before 29 Sep).
- [x] Uses only synthetic data. No real match data, names or logos.
- [ ] Runs as shown in the video. `pytest`, `ruff check`, `npm run e2e` green on a clean checkout (CI green after the first push).
- [ ] Names the Microsoft and Azure technologies actually used, in the pitch (see the table in `README.md`).

## Hero technologies (judging criterion 1, the tie-breaker)

- [x] **Microsoft Foundry** describer run live once (`docs/evidence/foundry-run.md`).
- [ ] Replay file recorded from Foundry and committed (T11, needs approval).
- [x] **Microsoft Agent Framework** workflow for describer, verifier, fallback, timing (T03).
- [ ] **Azure AI Speech** voice tested with a real key (T04, needs a pricing-tier decision).
- [ ] **Azure Container Apps** hosting (T06, needs approval).
- [ ] Optional: **MCP** server exposing the match tools (T08).

## Public repository

- [ ] History prepared: author and committer e-mail are the GitHub noreply address; backup kept outside the repository.
- [ ] Final scan of the whole history and the tree: no secrets, no personal data, no private notes, no competitor research.
- [ ] Repository created on GitHub as **public** (rules: must be public to be considered).
- [ ] `backend/.env` is not committed (git-ignored).
- [ ] README has the pitch, screenshots, how to run, the technologies used, and the honest limits.
- [ ] `LICENSE` present (MIT).

## Judges' access (4.8)

- [ ] Public URL works without login, free of charge, **until at least 10 Nov 2026, 23:59 Pacific (11 Nov, 08:59 in Italy)**.
- [x] The judges' path makes no model call and has no daily quota (replay mode, D12).
- [ ] Budget alert on the Azure subscription; a Speech tier chosen on purpose if Speech is enabled.
- [ ] Testing instructions in the README ("For judges": which preset to press, expected result), with the URL.
- [ ] Fallback if the live demo is down: the video and the README still show everything.

## Video (4.4)

- [ ] Under 2 minutes. Shows the project running on its target platform (a browser).
- [ ] Public URL on YouTube, Vimeo, Facebook Video or Youku.
- [ ] Has audio you made: your own voice or the project's voices. **No music** you do not have rights to; no Premier League or Microsoft logos.
- [ ] Story, in order: the problem (a blind fan, no description) -> press play -> hear the description and the ball sound -> the verifier blocking a wrong name -> the timeline of speech and silence.

## Pitch text (4.4)

- [ ] What it is, in one sentence.
- [ ] Which Microsoft and Azure technologies, listed, each true on the day.
- [ ] What problem it solves and for whom.
- [ ] English.

## Submit

- [ ] Fill every required field on the "Projects" page of the hackathon website before 27 Oct 23:59 Pacific (28 Oct, 07:59 in Italy). Do it a day early.
- [ ] Open the submitted page again and click every link (repo, video, demo).
- [ ] Do not change the project in ways that break the demo while judging runs.
