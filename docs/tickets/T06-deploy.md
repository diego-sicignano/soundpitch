# T06. Deploy to Azure Container Apps

**Status: in progress.** Done: the `Dockerfile` for the judges' image (D12), `python -m app.smoke`, the CI job that builds the image, runs it read-only and smoke-tests it, `docs/DEPLOY.md`. Not done: building the image on a Docker daemon (none was running), creating the Azure resources, running the smoke check against the public URL.

**Depends on:** T11 (so the demo shows recorded model words), T04 optional  **Acceptance:** S16  **Spec:** §15  **Rules:** 4.8 (free access for judges until 10 Nov, 23:59 Pacific)  **Judging:** criterion 3, Best Azure Cloud Native Integration

## Goal

A public URL that works without a login, stays up until the end of judging, makes no model call and cannot run up the bill.

## Steps

1. *(done)* `backend/tests/test_smoke.py` and `backend/app/smoke.py` (`python -m app.smoke <base-url>`).
2. Start Docker Desktop, then `docker build -t soundpitch .` and `docker run --rm -p 8000:8000 --read-only --cap-drop ALL soundpitch`; run the smoke check against `http://localhost:8000`. Fix the `Dockerfile` if needed and record the result in `docs/DEPLOY.md`.
3. **With the owner's approval of the resources and their cost:** create the resource group, the Container Apps environment and the container app (external ingress, port 8000, one replica, `SOUNDPITCH_TRUST_PROXY=1`), from the image. Check the current `az containerapp` documentation first; write the commands that were run into `docs/DEPLOY.md`.
4. Run the smoke check against the public URL; open it in a clean browser window.
5. Put the URL in `README.md` and `docs/submission/PITCH.md`. Calendar reminder: **do not delete or stop it before 11 Nov 2026, 08:59 Italian time.**

## Verification

`python -m app.smoke https://<url>` exits 0; `/api/health` answers `"llm":"replay"`.

## Out of scope

A live model or its ledger in the public path (D12), a custom domain, autoscaling rules beyond the replica limit, a database, Functions or Logic Apps.
