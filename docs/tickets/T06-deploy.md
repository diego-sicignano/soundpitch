# T06. Deploy to Azure Container Apps

**Status: deployed and verified once on 2026-10-21, then removed to stop costs; optional now (D26).** It ran on Azure Container Apps (Consumption only, Italy North, scale to zero, one replica at most, 0.25 vCPU, 0.5 GiB) from an earlier public GHCR image and passed acceptance (`docs/DEPLOY.md`, "Hosting on Azure Container Apps"). No hosted URL exists now; rule 4.8 accepts a test build, which the public image is. Redeploying needs approval, and the cost check (G6) must be run on the new group.

**Depends on:** T11 (so the demo shows recorded model words), T04 optional  **Acceptance:** S16  **Spec:** §15  **Rules:** 4.8 (free access for judges until 10 Nov, 23:59 Pacific)

## Goal

An optional hosted copy of the judges' image: a public URL that works without a login, makes no model call and cannot run up the bill. Rule 4.8 accepts the public image as a test build, so judging does not depend on it.

## How

The commands, the settings (Consumption only, scale to zero, one replica at most, replay mode, no secret) and the teardown are in [`docs/DEPLOY.md`](../DEPLOY.md). Acceptance is S16: `python -m app.smoke <url>` exits 0 against the public URL.
