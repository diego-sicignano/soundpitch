# Submission checklist

Deadlines are in [`SUMMARY.md`](SUMMARY.md). Registration closed **20 Oct 2026, 12:00 Pacific** (done); the submission closes **27 Oct 2026, 23:59 Pacific** (28 Oct, 07:59 in Italy). Tick items as they are done.

## Registration

- [x] Registered at <https://aka.ms/insidethegame> as an individual (confirmed by the owner on 20 Oct).
- [x] Eligibility (section 3) stated by the owner.
- [ ] **Rule 4.12 is open, not settled.** The owner stated no Microsoft funding, contract or licence, but about USD 0.05 of Azure for Students credit paid for early testing (COMPLIANCE, billing row; D23), and whether that counts as "financial or preferential support" is the Sponsor's reading. Open until the organizer answers (not asked yet) or the owner decides to accept the risk.

## The project (rules 4.3 and 4.4)

- [x] Newly built after 29 Sep 2026 (first commit: 2026-10-19; the owner states no code existed before 29 Sep).
- [x] Uses only synthetic data. No real match data, names or logos.
- [x] Explains why a moment matters (S31: a code-written score-context sentence; not checked by the verifier, and said so).
- [x] `pytest`, `ruff check`, `npm run e2e` green on a clean checkout: CI on `747e6f0` ([run](https://github.com/diego-sicignano/soundpitch/actions/runs/39846734463)); started by hand, push-triggered runs did not start. Still to do: the video must show the same page.
- [x] Names the Microsoft and Azure technologies actually used, in the pitch (`docs/submission/PITCH.md`, updated 2026-10-21).

## Hero technologies (judging criterion 1, the tie-breaker)

- [x] **Microsoft Foundry** describer run live twice on 2026-10-20 (`docs/evidence/foundry-run.md`).
- [x] Replay file recorded from Foundry (T11: 26 replies covering 30 of 30 first-attempt requests: 5 windows x 3 detail levels x 2 languages; `standard` and `full` share a reply in two windows).
- [x] Replay file committed; the owner reviewed the Italian sentences the model wrote, one is kept as recorded and documented.
- [x] **Microsoft Agent Framework** workflow for describer, verifier, fallback, timing (T03).
- [ ] **Azure AI Speech** voice tested with a real key (T04, needs a pricing-tier decision).
- [ ] Optional: **Azure Container Apps** hosting (T06): deployed and verified once on 2026-10-21, then deleted to stop costs; redeploying needs approval (D26, `docs/DEPLOY.md`).
- [ ] Optional: **MCP** server exposing the match tools (T08).

## Public repository

- [x] History prepared (D22, 2026-10-21): author and committer e-mail are a noreply address in every commit (the owner's GitHub noreply address in 32 commits; `Claude <noreply@anthropic.com>` in the 6 commits made by the coding assistant from 2026-10-22, from `2c50121` on; checked 2026-10-23); the Official Rules and playlist copies are in no commit; a backup (bundle, mirror clone, uncommitted files) is kept outside the repository.
- [x] Decided (README, "Honest limits": the one-sentence disclosure is public). The question was: whether the submission text says that about USD 0.05 of Azure for Students credit was used in early testing (D23; recommended: yes, one sentence, in the testing notes or the README limits). After the October invoice (expected early November) check that the Students profile settled it and note the result in `COMPLIANCE.md`.
- [x] Scan of the whole history and the tree on 2026-10-21 (D22): no e-mail address other than the noreply one, no key or token pattern, no private notes, no competitor research. Repeat after any later commit. Repeated on 2026-10-23 over every revision of every public ref (`main`, the assistant's branch and the closed pull request #1, an empty commit) by pattern search only, since no scanner is installed: no key, token, private-key block, connection string, e-mail address, home path or phone number, and no text of the Official Rules in any revision.
- [x] Repository created on GitHub as **public**: <https://github.com/diego-sicignano/soundpitch> (2026-10-21).
- [x] `backend/.env` is not committed (git-ignored; in no revision).
- [x] README has the pitch, screenshots, how to run, the technologies used, and the honest limits.
- [x] `LICENSE` present (MIT).

## Judges' access (4.8)

- [ ] The working project is reachable free of charge and without restriction **until 10 Nov 2026, 23:59 Pacific (11 Nov, 08:59 in Italy)** (§4.8: a website, a functioning demo or a test build). Today: the public tested image (`linux/amd64` only; checked on 23 Oct 2026 on an Apple Silicon Mac through Docker's emulation, see `docs/DEPLOY.md`), Codespaces and a clone, with instructions in the README. A hosted URL is optional and needs approval (D26); if one is made, put it in the README, the pitch and the video.
- [x] The judges' path makes no model call and has no daily quota (replay mode, D12).
- [x] Budget alert on the Azure subscription (5 EUR, e-mail only). No Speech is enabled. The demo resource group was deleted on 2026-10-21, so no hosting cost is accruing.
- [x] Testing instructions in the README ("For judges": the `docker run` line, which preset to press, the expected result).
- [ ] If a hosted copy is made and goes down, the test build, the video and the README still show everything.

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

- [ ] Sign in to the hackathon website (it redirects to a Microsoft login) and read the "Projects" form, any contact route and any posted amendment to the rules (rule 11.5) or deadline. None of it could be read without signing in on 2026-10-23.
- [ ] Fill every required field on the "Projects" page of the hackathon website before 27 Oct 23:59 Pacific (28 Oct, 07:59 in Italy). Do it a day early.
- [ ] Open the submitted page again and click every link (repo, video, demo).
- [ ] Do not change the project in ways that break the demo while judging runs.
