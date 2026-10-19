# T06. Deploy to Azure Container Apps

**Depends on:** T04 (and T02 if the model runs in Azure)  **Acceptance:** S16  **Spec:** §15  **Rules:** 4.8 (free access for judges until 10 Nov)  **Judging:** criterion 3, Best Azure Cloud Native Integration

## Goal

A public URL that works without a login, stays up until the end of judging, and cannot run up the bill.

## Steps

1. **Test first:** `backend/tests/test_smoke.py` for the checks of `scripts/smoke.py` (a function `check(client)` run against the TestClient: health, presets, a valid session for each preset with no overlap and the must-say moments present).
2. Write `scripts/smoke.py <base-url>` (httpx, exits non-zero on failure).
3. Start Docker Desktop and build the image: `docker build -t soundpitch .`; run it and run the smoke script against `http://localhost:8000`. Fix the `Dockerfile` if needed.
4. Write `docs/DEPLOY.md`: the commands (Azure CLI), the resources created, the settings and secrets, and how to delete everything.
5. Create the Container App: public ingress, min replicas 1, max 2, secrets for keys (or a managed identity), a budget alert on the subscription. Run the smoke script against the public URL; open it in a clean browser.
6. Add a CI job that builds the image and runs the smoke script (see `.github/workflows/ci.yml`).
7. Put the URL in `README.md` and `docs/submission/PITCH.md`. Calendar reminder: **do not delete or stop it before 10 Nov 2026.**

## Verification

`scripts/smoke.py` exits 0 on the public URL.

## Out of scope

Custom domain, autoscaling rules beyond the replica limit, a database, Functions or Logic Apps.
