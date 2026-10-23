# T10. Make the repository public and submit

**Depends on:** all tickets you intend to show  **Acceptance:** none (checklist)  **Rules:** 4.4, 4.8  **See:** `docs/hackathon/SUBMISSION_CHECKLIST.md`

## Goal

The entry is complete, public and submitted a day before the deadline (**27 Oct 2026, 23:59 Pacific**).

## Steps

1. Run every command in `CLAUDE.md` on a clean checkout; all exit 0.
2. Secret scan of the whole history (done for the local release candidate, see D22; repeat it after any later commit). All commits carry a noreply address (the owner's GitHub one, or `noreply@anthropic.com` for the assistant's commits).
3. Create the GitHub repository as **public**, push `main`, check the CI is green.
4. Add the video URL (and a demo URL only if a hosted copy exists, D26) to `README.md` and `docs/submission/`, and update `PITCH.md` only for a step that is really done (for example a hosted copy). Tick every box in `docs/hackathon/SUBMISSION_CHECKLIST.md`.
5. Fill the "Projects" page on the hackathon site: repository, video, pitch, testing instructions (a demo URL only if a hosted copy exists, D26). Submit.
6. Open the submission again and click every link from a signed-out browser.

## Done when

The submission is confirmed on the hackathon site and every link works.
