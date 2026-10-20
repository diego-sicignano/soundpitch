# Deploying SoundPitch

State on 2026-10-20: **nothing is deployed and no Azure resource has been created for hosting.** The commands marked *not run* below are a plan to be checked against the current Azure documentation when ticket T06 is done; the commands marked *run* were run. Creating hosting resources costs money and needs the owner's approval.

## What is deployed, and what is not

The judges' path is the container image in the `Dockerfile`: the page and the API, `SOUNDPITCH_LLM=replay`, no key, no Azure login, no network call, no writable path, no database. It answers `GET /api/health` with `{"status":"ok","llm":"replay","replies":<n>}`; `replies` is the number of recorded Foundry replies the image holds, and `0` means the verified templates speak.

The live Foundry describer and its cost ledger (a SQLite file, D11) are **not part of the image**. Reasons: the judges do not need them (replay covers the 30 windows of the demo), the ledger would need a persistent writable file, and the App Service documentation on custom-mounted Azure Storage advises against using a mount for local databases such as SQLite, and SQLite's own guide on network file systems warns that locking can misbehave there (both read on 2026-10-20 through a summarising tool; re-read them before relying on the exact wording). If a live model is ever served publicly, that needs a different, approved design; it is not planned.

## Build and run locally

*Not run on a Docker daemon in this repository's history: none was running on the development machine.* The CI job `docker` builds the image, runs it with `--read-only --cap-drop ALL`, checks that it runs as UID 10001, runs `python -m app.smoke` inside it and waits for the container healthcheck.

```powershell
docker build -t soundpitch .
docker run --rm -p 8000:8000 --read-only --cap-drop ALL soundpitch
cd backend; .\.venv\Scripts\python.exe -m app.smoke http://localhost:8000; cd ..
```

*Run*, without Docker: the same files copied into the image's layout (`/srv/backend/app`, `/srv/frontend`), started with `SOUNDPITCH_LLM=replay` and an empty environment, passed `python -m app.smoke`, and a hash of the file tree was identical before and after (nothing was written).

## Recording the replay file (needs approval; spends model calls)

The replay file `backend/app/replay_data/foundry_replies.json` holds the replies a Foundry model gave to every request of the demo (5 windows x 3 detail levels x 2 languages, first attempt). It is empty until this is done, and then the replay mode speaks the verified templates. Expected size: about 30 to 60 calls of the `gpt-4.1-mini` deployment, a few cents at the ledger's rate. Do it once, after the prompt is final: **any change to `SYSTEM`, the templates or the vocabulary changes the keys** and the committed file then has no matching reply (`tests/test_replay.py` fails once the file has content and no longer covers every window, and `python -m app.replay_export --check` says how many requests are covered).

```powershell
cd backend
# a throw-away ledger, and limits raised on purpose for this run only (the monthly ceiling stays below 4.00)
$env:SOUNDPITCH_USAGE_DB = "$PWD\data\record.sqlite"
$env:SOUNDPITCH_LLM_CALLS_PER_DAY = "200"
$env:SOUNDPITCH_LLM_TOKENS_PER_DAY = "1000000"
# also FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL, and `az login`
.\.venv\Scripts\python.exe -m app.foundry_run --pause-seconds 31 --write ..\docs\evidence\foundry-run.md
.\.venv\Scripts\python.exe -m app.replay_export --db data\record.sqlite --model gpt-4.1-mini --recorded 2026-10-DD
.\.venv\Scripts\python.exe -m app.replay_export --check
```

Then run the tests, read the generated `docs/evidence/foundry-run.md` (it now ran under the ledger), and commit the two files. The replay file contains model text and no secret: check it by eye before committing.

## Hosting on Azure Container Apps (*not run*)

Resources a single-image, no-database demo needs: a resource group, a Container Apps environment, one container app from the image, and a place to build or hold the image (Azure Container Registry, or a source build). Container Apps on the Consumption plan bills only while replicas run; a registry is a small monthly cost. Settings:

| Setting | Value | Why |
|---|---|---|
| ingress | external, target port 8000 | judges open it without a login (rules 4.8) |
| replicas | min 1, max 1 | no cold start for a judge; the voice endpoint's limits live in one process's memory |
| `SOUNDPITCH_LLM` | `replay` (already the image default) | no model call |
| `SOUNDPITCH_TRUST_PROXY` | `1` | the ingress proxy appends the real client address to `X-Forwarded-For`; without this every judge shares one per-client voice limit. Set it only behind exactly one trusted proxy |
| Speech | only if T04 is done: `AZURE_SPEECH_KEY` as a container-app **secret**, `AZURE_SPEECH_REGION` | otherwise the page uses the browser voice |

Check the exact `az containerapp` flags in the current Microsoft Learn documentation before running anything, and put the commands that were actually run in this file with the date. After deploying: `python -m app.smoke https://<the app's address>` must exit 0, and the page must load in a clean browser window.

**Keep it up until 10 Nov 2026, 23:59 Pacific** (11 Nov, 08:59 in Italy): rules 4.8 require the project to be available free of charge and without restriction until the judging period ends. Put a reminder in the calendar. Afterwards delete the resource group to stop all charges.

## Azure AI Speech (*not run*)

`tts.py` is tested only against a stub. Before creating a Speech resource, read the current pricing page and choose the tier on purpose: the application's own limits (SPEC §8) are in memory and restart at zero, so **the tier is the only hard cap on Speech spending**. Whether a free tier is available, its monthly allowance and what happens when it is exhausted must be read from the Azure pricing and quota pages at the time; none of that is recorded here as fact. The defaults (`SOUNDPITCH_TTS_CHARS_PER_DAY` 60,000, `..._PER_MONTH` 300,000) are conservative guesses to be set below the chosen tier's allowance.

## Cost summary

| Item | State | Control |
|---|---|---|
| Foundry deployment `soundpitch-mini` (`gpt-4.1-mini`, Global Standard, capacity 8) | exists; used once on 2026-10-20 | not called by the judges' path; the ledger (D11) limits a live run; Azure's 5 EUR budget only sends e-mail |
| Hosting | none | Container Apps Consumption plan, one replica, deleted after judging |
| Speech | none | the pricing tier |

Azure's budgets alert, they do not stop spending (Microsoft Learn, "Create and manage budgets": a budget does not affect resources or stop consumption; cost data arrives 8 to 24 hours late). An automatic stop would need an action group calling a function; it was not built.
