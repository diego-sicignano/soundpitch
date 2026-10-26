# T06. Deploy to Azure Container Apps

**Status: done (2026-10-26, D36).** Live at https://soundpitch.icywave-efb40405.italynorth.azurecontainerapps.io. Deployed and verified once on 2026-10-21 and removed; deployed again on 2026-10-26. It ran on Azure Container Apps (Consumption only, Italy North, scale to zero, one replica at most, 0.25 vCPU, 0.5 GiB) from an earlier public GHCR image and passed acceptance (`docs/DEPLOY.md`, "Hosting on Azure Container Apps"). The cost is checked the day after each deployment.

**Depends on:** T11 (so the demo shows recorded model words), T04 optional  **Acceptance:** S16  **Spec:** §15  **Rules:** 4.8 (free access for judges until 10 Nov, 23:59 Pacific)

## Goal

An optional hosted copy of the judges' image: a public URL that works without a login, makes no model call and cannot run up the bill. Rule 4.8 accepts the public image as a test build, so judging does not depend on it.

## How

The commands, the settings (Consumption only, scale to zero, one replica at most, replay mode, no secret) and the teardown are in [`docs/DEPLOY.md`](../DEPLOY.md). Acceptance is S16: `python -m app.smoke <url>` exits 0 against the public URL.
