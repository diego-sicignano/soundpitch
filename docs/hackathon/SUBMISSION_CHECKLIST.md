# Submission checklist

Deadlines are in [`SUMMARY.md`](SUMMARY.md). Registration closed **20 Oct 2026, 12:00 Pacific** (done); the submission closes **27 Oct 2026, 23:59 Pacific** (28 Oct, 07:59 in Italy). Tick items as they are done.

## Registration

- [x] Registered at <https://aka.ms/insidethegame> as an individual (confirmed by the owner on 20 Oct).
- [x] Eligibility (section 3) stated by the owner. Rule 4.12: no Microsoft funding, contract or license, stated by the owner; **re-confirm with D23 in view**: about USD 0.05 of Azure for Students credit paid for early testing (COMPLIANCE, billing row).

## The project (rules 4.3 and 4.4)

- [x] Newly built after 29 Sep 2026 (first commit: 2026-10-19; the owner states no code existed before 29 Sep).
- [x] Uses only synthetic data. No real match data, names or logos.
- [x] Explains why a moment matters (S31: a code-written score-context sentence; not checked by the verifier, and said so).
- [x] `pytest`, `ruff check`, `npm run e2e` green on a clean checkout: CI on `09db91c` ([run](https://github.com/diego-sicignano/soundpitch/actions/runs/39622166407)); started by hand, push-triggered runs did not start. Still to do: the video must show the same page.
- [x] Names the Microsoft and Azure technologies actually used, in the pitch (`docs/submission/PITCH.md`, updated 2026-10-21).

## Hero technologies (judging criterion 1, the tie-breaker)

- [x] **Microsoft Foundry** describer run live twice on 2026-10-20 (`docs/evidence/foundry-run.md`).
- [x] Replay file recorded from Foundry (T11: 26 replies, 30 of 30 windows).
- [x] Replay file committed; the owner reviewed the Italian sentences the model wrote, one is kept as recorded and documented.
- [x] **Microsoft Agent Framework** workflow for describer, verifier, fallback, timing (T03).
- [ ] **Azure AI Speech** voice tested with a real key (T04, needs a pricing-tier decision).
- [ ] **Azure Container Apps** hosting (T06): deployed and verified on 2026-10-21, then deleted the same day to stop costs; redeploy before submitting (`docs/DEPLOY.md`, "Teardown and redeploy").
- [ ] Optional: **MCP** server exposing the match tools (T08).

## Public repository

- [x] History prepared (D22, 2026-10-21): author and committer e-mail are the GitHub noreply address in every commit; the Official Rules and playlist copies are in no commit; a backup (bundle, mirror clone, uncommitted files) is kept outside the repository.
- [x] Decided (README, "Honest limits": the one-sentence disclosure is public; repeat it on the submission form if it asks about funding or credits). The question was: whether the submission text says that about USD 0.05 of Azure for Students credit was used in early testing (D23; recommended: yes, one sentence, in the testing notes or the README limits). After the October invoice (expected early November) check that the Students profile settled it and note the result in `COMPLIANCE.md`.
- [x] Scan of the whole history and the tree on 2026-10-21 (D22): no e-mail address other than the noreply one, no key or token pattern, no private notes, no competitor research. Repeat after any later commit.
- [x] Repository created on GitHub as **public**: <https://github.com/diego-sicignano/soundpitch> (2026-10-21).
- [x] `backend/.env` is not committed (git-ignored; in no revision).
- [x] README has the pitch, screenshots, how to run, the technologies used, and the honest limits.
- [x] `LICENSE` present (MIT).

## Judges' access (4.8)

- [ ] Public URL works without login, free of charge, **until at least 10 Nov 2026, 23:59 Pacific (11 Nov, 08:59 in Italy)**. It worked on 2026-10-21 and is **offline now**; redeploy from the public image (`docs/DEPLOY.md`), put the new address in the README, the pitch and the video, and run the cost check (G6) the next day.
- [x] The judges' path makes no model call and has no daily quota (replay mode, D12).
- [x] Budget alert on the Azure subscription (5 EUR, e-mail only). No Speech is enabled. The demo resource group was deleted on 2026-10-21, so nothing is accruing.
- [ ] Testing instructions in the README ("For judges": which preset to press, expected result), with the URL: the steps are there; the URL goes in after the redeploy.
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
