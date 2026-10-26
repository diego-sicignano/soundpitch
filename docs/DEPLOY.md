# Deploying SoundPitch

The judges' image runs offline in replay mode and costs nothing to serve. This page says how it is built, tested, published and hosted, what was verified, and what each billable step would cost. Decision record: D17 in [`DECISIONS.md`](DECISIONS.md); ticket: [`tickets/T06-deploy.md`](tickets/T06-deploy.md).

**State (26 Oct 2026).** The live demo runs at <https://soundpitch.icywave-efb40405.italynorth.azurecontainerapps.io> (D36). The tested image of commit `021fdfb2b10442bef7b7efd92c9549d73945989d` is public on GHCR (`ghcr.io/diego-sicignano/soundpitch:021fdfb2b10442bef7b7efd92c9549d73945989d`, manifest digest `sha256:6ea135a83e60e6a3da4565e48af2dd2ca5736c7b2b56fddd9e724e524c6c691a`), published by CI run [40385346831](https://github.com/diego-sicignano/soundpitch/actions/runs/40385346831) after the backend, SDK, end-to-end and Docker jobs passed; it runs the Agent Framework workflow (D31) and carries the MCP server (D32). The checks under "Verified on 23 Oct 2026" below were made on an earlier image; this one was built, run read-only without capabilities and smoke-tested by CI, and its digest read from the registry, but not pulled on a Mac. It is built for **`linux/amd64` only**: it runs where Docker runs amd64 images, and on Apple Silicon only through Docker Desktop's emulation. What was checked is under "Verified on 23 Oct 2026" below. A hosted copy on Azure Container Apps was deployed and verified once (below) and then deleted to stop costs, so **the live demo runs at the address above**. No Speech request has been sent and no voice clip exists. Steps that spend money are marked *needs approval*.

## What is deployed, and what is not

The judges' path is the container image in the `Dockerfile`: the page and the API, `SOUNDPITCH_LLM=replay`, no key, no Azure login, no network call, no writable path, no database. It answers `GET /api/health` with `{"status":"ok","llm":"replay","replies":<n>}`; `replies` is the number of distinct recorded Foundry replies the image holds (26 in the current image; they cover the 30 requests of the demo, see below), and `0` means the verified templates speak. A mistyped `SOUNDPITCH_LLM` makes it answer `503 llm_not_configured` (the container is then reported unhealthy) instead of `ok`; the message names the setting and never its value (S32, D19). The judge-facing path does not depend on Foundry credentials or on outbound connectivity.

The voice is spoken from **stored clips** (`backend/app/audio/`, S26): 200 of them, made once on 26 Oct 2026 with Azure AI Speech; the image holds no Speech key. Serving a live model publicly would need a different design; it is not planned.

## Build and run locally

*Run on 2026-10-20 and again on 2026-10-21 after S31 and D19* (Docker 29.6.2 on Windows; the second run rebuilt the image and repeated the read-only, non-root, `--network none` and smoke checks, and a mistyped `SOUNDPITCH_LLM` answered `/api/health` with 503): the image built; it ran with `--read-only --cap-drop ALL --security-opt no-new-privileges`; the process ran as UID 10001; `python -m app.smoke` inside the container printed `ok`; `/api/health` answered `"llm":"replay","replies":26`; writing under `/srv/backend` failed with "Read-only file system"; and with `--network none` the container was healthy and passed the smoke check. With a throw-away clip folder mounted read-only over `/srv/backend/app/audio` (one made-up clip, not Speech output), `POST /api/tts` for an issued sentence answered `200 audio/mpeg` with `X-Audio-Rate: 1` and no key, and for text that was never issued it answered `403`. The CI job `docker` repeats the first part when the workflow runs; it does not use `--network none`. The 2026-10-21 run is the one that includes S31.

```powershell
docker build -t soundpitch .
docker run --rm -p 8000:8000 --read-only --cap-drop ALL --security-opt no-new-privileges soundpitch
cd backend; .\.venv\Scripts\python.exe -m app.smoke http://localhost:8000; cd ..
```

## Recording the replay file (spends model calls)

The replay file `backend/app/replay_data/foundry_replies.json` holds the replies a Foundry model gave to every request of the demo (5 windows x 3 detail levels x 2 languages, first attempt). **Recorded on 2026-10-20: 26 replies, 30 of 30 requests** (`docs/evidence/foundry-run.md`). Before it existed the replay mode spoke the verified templates. The tool needs the optional packages (Python 3.13). Expected size: about 30 to 60 calls of the `gpt-4.1-mini` deployment, a few cents at the ledger's rate. Do it once, after the prompt is final: **any change to `SYSTEM`, the templates or the vocabulary changes the keys** (the score-context sentence of S31 is added after the verifier and is not part of a key) and the committed file then has no matching reply (`tests/test_replay.py` fails once the file has content and no longer covers every window, and `python -m app.replay_export --check` says how many requests are covered). The clip sentences below depend on those replies, so re-recording them means regenerating the clips.

```powershell
cd backend
# a throw-away ledger, and limits raised on purpose for this run only (the monthly ceiling stays below 4.00)
$env:SOUNDPITCH_USAGE_DB = "$PWD\data\record.sqlite"
$env:SOUNDPITCH_LLM_CALLS_PER_DAY = "200"
$env:SOUNDPITCH_LLM_TOKENS_PER_DAY = "1000000"
# also FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL, and `az login`
.\.venv\Scripts\python.exe -m app.foundry_run --pause-seconds 31 --write ..\docs\evidence\foundry-run.md
.\.venv\Scripts\python.exe -m app.replay_export --db data\record.sqlite --model gpt-4.1-mini --recorded <date>
.\.venv\Scripts\python.exe -m app.replay_export --check
```

Then run the tests, read the generated `docs/evidence/foundry-run.md` (it now ran under the ledger), and commit the two files. The replay file contains model text and no secret: check it by eye before committing.

## Making the voice clips (spends Speech characters)

The page can only say 140 distinct sentences (72 English, 68 Italian, 7,141 characters): every sentence the pipeline accepts for the five windows, three detail levels and two languages, in its full and short form, with the recorded model words and the score-context sentence of goal, half-time and full-time cues. `python -m app.clips_build` lists them, sends nothing and needs no key:

```powershell
cd backend; .\.venv\Scripts\python.exe -m app.clips_build; cd ..
# the demo can speak 140 sentences (en 72, it 68), 7141 characters
# stored clips: 0 of 140; missing: 140 (7141 characters)
# estimated cost of the missing clips at USD 15 per million characters: 0.11 USD (the price is to be confirmed before use)
```

**Estimated cost: about USD 0.11** for all 140 clips (USD 15 per million characters is the standard neural voice figure on Microsoft Learn's "Azure AI Speech quotas and limits"; the public pricing page did not show it, so confirm it first). **Nothing has been generated.** Before generating:

1. Read the key and region of the existing Speech-capable account (the Foundry account is of kind AIServices, S0) without printing them; it has not been checked that its key works against the regional text-to-speech endpoint.
2. Read the Azure AI Speech **Product Terms** in the original, on what may be done with the audio output (the summary seen so far suggests the right to publish synthesised audio is reserved to paid-tier customers, which S0 is). If the terms do not allow shipping the clips, stop: the page keeps the browser voice.
3. One test request, then the rest: `--generate --limit 1`, listen to the clip, then `--generate`. The tool only makes missing clips, refuses to send more than `--max-chars` (15,000) characters, retries 429 and 5xx with a growing wait, and writes the manifest after each clip so a stopped run resumes.

```powershell
# not run
$env:AZURE_SPEECH_KEY = "<from the Azure portal; keep it out of files>"
$env:AZURE_SPEECH_REGION = "italynorth"
cd backend
.\.venv\Scripts\python.exe -m app.clips_build --generate --limit 1
.\.venv\Scripts\python.exe -m app.clips_build --generate
cd ..
```

Then run the tests, listen to a clip of each language, commit `backend/app/audio/` (about 3 MB) and rebuild the image. The page says the voice is synthetic (S28); keep that note. Until the clips exist, the page does not offer the Azure voice at all (S29) and the default browser voice is used, which depends on the voices installed in the judge's browser and system (the page says when there is none for the language, S30): the video and the README must not claim an Azure voice before this step.

## Publishing the image

The `publish` job in `.github/workflows/ci.yml` runs only when the workflow is started by hand on `main` (Actions, "Run workflow"), after the backend, SDK, end-to-end and Docker jobs pass. It uses the built-in `GITHUB_TOKEN` with `packages: write` and nothing else; the rest of the workflow has a read-only token (a test checks it). It pushes `ghcr.io/diego-sicignano/soundpitch:<commit sha>`, never `latest`. A new package starts private; making it public is a manual step in the package settings. CI is started by hand (`workflow_dispatch`); push-triggered runs did not start for this repository. The run of `021fdfb` ([run](https://github.com/diego-sicignano/soundpitch/actions/runs/40385346831)) passed all five jobs, `publish` included, and published the image. The image runs as user 10001 with `SOUNDPITCH_LLM=replay` and holds no key in its environment or build history.

**Verified on 23 Oct 2026**, on an Apple Silicon Mac (M1, Docker Desktop, `linux/amd64` through its emulation), against the published image itself, never a local build: the registry reported manifest digest `sha256:44f65c497a725d8e861cb639414c9f3a670e8fb83a3fe281812c4dada6d49199` for the tag, the pull (no `ghcr.io` credentials configured) returned the same digest, and the config blob in the registry hashes to the image ID `sha256:5992dc0b039d46b90b6059a70dca26318cae6253a98d1945eda5e9ba78c155af` (Docker's containerd image store shows the manifest digest as the local image ID). The image config says user 10001, no entrypoint, `uvicorn app.main:app --host 0.0.0.0 --port 8000`, `SOUNDPITCH_LLM=replay` and the HEALTHCHECK. In a container with `--network none`, no published port, `--read-only` and `--cap-drop ALL --security-opt no-new-privileges`, all through `docker exec` on `127.0.0.1`: `/api/health` answered `{"status":"ok","llm":"replay","replies":26}`; `id -u` was 10001 and writes to `/srv/backend` and `/tmp` were refused; `python -m app.smoke` printed `ok`; the container became `healthy` and stopped with exit code 0. The final-whistle window answered with the full-time cue last (English: "Full-time. Northgate 2, Harbour 1. Northgate win."; Italian: "Fine partita. Northgate 2, Harbour 1. Vince Northgate."), the cue ending exactly at `duration_ms`, `duration_ms` beyond the 60 s window and no cue ending after the session (the same assertions as `backend/tests/test_pipeline.py`, at `detail=standard` and `rate=1.0`). The README command, run as written but without `--platform` and with the port published on `127.0.0.1:18000` instead of 8000, printed the platform warning, then served `/api/health`, the page (200) and a session (200). Not checked: a native amd64 host (CI built the image on one but this exact image was not pulled there), a browser session against this container, Azure hosting.

## Hosting on Azure Container Apps, Consumption only (optional)

**Optional: judging does not require it** (rule 4.8 accepts a test build, and the public image is one; D26). The cheapest form of the service, for the judging window only: its own resource group, a Consumption-only environment with no logging destination, one app that scales to zero and runs at most one replica. These commands were run once, on 21 Oct 2026, with an earlier image; they have not been run with the current one.

| Setting | Value | Why |
|---|---|---|
| resource group | `rg-soundpitch-demo` (Italy North) | holds nothing else, so deleting it cannot touch the Foundry resources |
| environment | `--enable-workload-profiles false`, `--logs-destination none` | no Dedicated profile, no private endpoint, no planned maintenance, no Log Analytics: nothing billed per environment according to the documentation |
| size | 0.25 vCPU, 0.5 GiB | the smallest valid pair; a local Docker test under the same limits used 41 to 73 MiB and served 200 parallel session requests without error (figures and limits of that test in [T06](tickets/T06-deploy.md)); it says nothing about Container Apps, cold starts or the network |
| replicas | min 0, max 1 | no always-on replica; the voice endpoint's limits live in one process's memory |
| ingress | external, target port 8000 | judges open it without a login (rules 4.8) |
| `SOUNDPITCH_LLM` | `replay` (the image default) | no model call, no Foundry credential, no outbound connection |
| `SOUNDPITCH_TRUST_PROXY` | `1` | the ingress proxy appends the real client address; set only behind exactly one trusted proxy |
| `SOUNDPITCH_LOG_FORWARDED` | `1` for the first requests | logs the *shape* of `X-Forwarded-For` (digits as `9`, never an address), to settle its format |
| secrets, volumes, registry credentials | none | the image is public and holds no key |

Free grants (documented, per subscription and calendar month): 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests, about 200 replica-hours at this size. Modelled judge traffic uses 3 to 125 hours in the whole window; kept awake all day the cost would be about USD 1.5 a month. Sources and numbers: [T06](tickets/T06-deploy.md).

```powershell
az login
az account show --query "{name:name}"            # check which subscription is selected
az extension add --name containerapp --upgrade    # once per computer
az provider register --namespace Microsoft.App --wait
$image = "ghcr.io/diego-sicignano/soundpitch:021fdfb2b10442bef7b7efd92c9549d73945989d"   # the tag form is what the 21 Oct deployment used; the same image by digest is ...soundpitch@sha256:6ea135a83e60e6a3da4565e48af2dd2ca5736c7b2b56fddd9e724e524c6c691a..., not tried with `az containerapp`; linux/amd64 only
az group create --name rg-soundpitch-demo --location italynorth
az containerapp env create --name cae-soundpitch --resource-group rg-soundpitch-demo --location italynorth --enable-workload-profiles false --logs-destination none
az containerapp create --name soundpitch --resource-group rg-soundpitch-demo --environment cae-soundpitch --image $image --ingress external --target-port 8000 --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi --env-vars SOUNDPITCH_LLM=replay SOUNDPITCH_TRUST_PROXY=1
az containerapp show --name soundpitch --resource-group rg-soundpitch-demo --query "properties.configuration.ingress.fqdn" -o tsv
cd backend; .\.venv\Scripts\python.exe -m app.smoke https://<fqdn>; cd ..
# stop every charge: the group holds nothing else
az group delete --name rg-soundpitch-demo --yes
```

A new address is generated at each deployment. The public image needed no `registry set`.

**Verified on 21 Oct 2026** (one deployment, then deleted): `python -m app.smoke` on the public address printed `ok`; a read-only script checked `/api/health` (`replay`, 26 replies), the page without a login, the security headers, five presets, goal 1 in English (attempt 1) and Italian (attempt 2, D20), `/api/cuesheet` and its schema, WebVTT, `/api/voice`, `POST /api/tts` with unissued text answering `403`, and an unknown preset answering `404`. The first request after creation took 16.8 s (cold start), later ones about 0.1 s; after about ten minutes idle the app had 0 replicas and the next request took 11.3 s. `X-Forwarded-For` arrived as one address or as two separated by a comma; the per-client voice limit takes the last entry (D14) and matters only when Speech is live. The page flow was covered by the end-to-end suite in CI, not driven in a browser against the public address.

**Cost check.** Pay-as-you-go has no spending limit; a budget only sends e-mail. The public price list has three undocumented meters named `Environment` (USD 0.13 an hour in Italy North in October 2026); the most probable reading, an inference, is that they split the documented Dedicated plan fee by cause, which this setup does not trigger. If they applied to every environment the cost would be about USD 3 a day, so a deployment is followed by a check: the same day, `az containerapp env show` shows no workload profile (it did: `workloadProfiles: null`); after 8 to 48 hours, Cost Management filtered to the resource group shows no `Environment` line above 0; if one appears, delete the environment at once.

Rollback: `az containerapp update --image <previous sha>`; take it offline without deleting: `az containerapp ingress disable`.

## Fallbacks

- **Render Free (USD 0, not on Azure).** A web service from the same image (`ghcr.io/diego-sicignano/soundpitch:<sha>`) or from the repository's `Dockerfile`, no environment variable but `SOUNDPITCH_LLM=replay`, and `SOUNDPITCH_TRUST_PROXY=1` only after reading how Render writes `X-Forwarded-For`. Limits to accept: 0.1 CPU and 512 MB, spin-down after 15 minutes without traffic and about a minute to wake, 750 free hours a month, and a bandwidth cap that suspends all free services if exceeded. Not confirmed: that the Free type takes an image-backed service and that a public ghcr.io image pulls without credentials (a deploy from the repository is the alternative). It would not count as Azure hosting for criterion 3.
- **Azure App Service, Linux B1.** About USD 8.8 for the window, fixed.

## Cost summary

| Item | State | Control |
|---|---|---|
| Foundry deployment `soundpitch-mini` (`gpt-4.1-mini`, Global Standard) | used on 2026-10-20; a full recording run is about USD 0.03 | not called by the judges' path; the ledger (D11) limits a live run; the Azure budget only e-mails |
| Speech clips | 200 made on 2026-10-26, 13,310 characters | about USD 0.20, once |
| Hosting | running since 2026-10-26 (D36) | Container Apps Consumption, scale to zero, inside the monthly grants; checked the next day |
| Speech at run time | none | the public app holds no key |

Azure's budgets alert, they do not stop spending (Microsoft Learn, "Create and manage budgets"); cost data arrives 8 to 24 hours late. An automatic stop would need an action group calling a function; it was not built.
