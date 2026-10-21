# Deploying SoundPitch

State on 2026-10-21: **deployed.** The public demo is <https://soundpitch.delightfulbay-5202fc67.italynorth.azurecontainerapps.io> (Azure Container Apps, Consumption only, Italy North, the pay-as-you-go subscription), running the GHCR image of the commit `09db91c`, verified end to end the same day (below, "Deployment record"). No Speech request has been sent and no voice clip exists. The commands in this guide that are marked *not run* are still a plan; those under "Deployment record" were run. Hosting resources and the voice clips cost money; the gates below say what needed approval. The decision behind this plan is D17 in [`DECISIONS.md`](DECISIONS.md); the ticket is [`tickets/T06-deploy.md`](tickets/T06-deploy.md).

## What is deployed, and what is not

The judges' path is the container image in the `Dockerfile`: the page and the API, `SOUNDPITCH_LLM=replay`, no key, no Azure login, no network call, no writable path, no database. It answers `GET /api/health` with `{"status":"ok","llm":"replay","replies":<n>}`; `replies` is the number of recorded Foundry replies the image holds, and `0` means the verified templates speak. A mistyped `SOUNDPITCH_LLM` makes it answer `503 llm_not_configured` (the container is then reported unhealthy) instead of `ok`; the message names the setting and never its value (S32, D19). The judge-facing path does not depend on Foundry credentials or on outbound connectivity.

The voice is spoken from **stored clips** (`backend/app/audio/`, S26): the image holds no Speech key. The live Foundry describer and its cost ledger (a SQLite file, D11) are **not part of the image**: the judges do not need them (replay covers the 30 windows of the demo) and the ledger would need a persistent writable file; the App Service documentation on custom-mounted Azure Storage advises against using a mount for local databases such as SQLite, and SQLite's own guide on network file systems warns that locking can misbehave there (both read on 2026-10-20 through a summarising tool; re-read them before relying on the exact wording). If a live model is ever served publicly, that needs a different, approved design; it is not planned.

## Build and run locally

*Run on 2026-10-20 and again on 2026-10-21 after S31 and D19* (Docker 29.6.2 on Windows; the second run rebuilt the image and repeated the read-only, non-root, `--network none` and smoke checks, and a mistyped `SOUNDPITCH_LLM` answered `/api/health` with 503): the image built; it ran with `--read-only --cap-drop ALL --security-opt no-new-privileges`; the process ran as UID 10001; `python -m app.smoke` inside the container printed `ok`; `/api/health` answered `"llm":"replay","replies":26`; writing under `/srv/backend` failed with "Read-only file system"; and with `--network none` the container was healthy and passed the smoke check. With a throw-away clip folder mounted read-only over `/srv/backend/app/audio` (one made-up clip, not Speech output), `POST /api/tts` for an issued sentence answered `200 audio/mpeg` with `X-Audio-Rate: 1` and no key, and for text that was never issued it answered `403`. The CI job `docker` repeats the first part on every push. The 2026-10-21 run is the one that includes S31.

```powershell
docker build -t soundpitch .
docker run --rm -p 8000:8000 --read-only --cap-drop ALL --security-opt no-new-privileges soundpitch
cd backend; .\.venv\Scripts\python.exe -m app.smoke http://localhost:8000; cd ..
```

## Recording the replay file (needs approval; spends model calls)

The replay file `backend/app/replay_data/foundry_replies.json` holds the replies a Foundry model gave to every request of the demo (5 windows x 3 detail levels x 2 languages, first attempt). **Recorded on 2026-10-20: 26 replies, 30 of 30 requests** (`docs/evidence/foundry-run.md`). Before it existed the replay mode spoke the verified templates. The tool needs the optional packages (Python 3.13). Expected size: about 30 to 60 calls of the `gpt-4.1-mini` deployment, a few cents at the ledger's rate. Do it once, after the prompt is final: **any change to `SYSTEM`, the templates or the vocabulary changes the keys** (the score-context sentence of S31 is added after the verifier and is not part of a key) and the committed file then has no matching reply (`tests/test_replay.py` fails once the file has content and no longer covers every window, and `python -m app.replay_export --check` says how many requests are covered). The clip sentences below depend on those replies, so re-recording them means regenerating the clips.

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

## Making the voice clips (G3: needs approval; spends Speech characters)

The page can only say 140 distinct sentences (72 English, 68 Italian, 7,141 characters): every sentence the pipeline accepts for the five windows, three detail levels and two languages, in its full and short form, with the recorded model words and the score-context sentence of goal, half-time and full-time cues. `python -m app.clips_build` lists them, sends nothing and needs no key:

```powershell
cd backend; .\.venv\Scripts\python.exe -m app.clips_build; cd ..
# the demo can speak 140 sentences (en 72, it 68), 7141 characters
# stored clips: 0 of 140; missing: 140 (7141 characters)
# estimated cost of the missing clips at USD 15 per million characters: 0.11 USD (the price is to be confirmed before use)
```

**Estimated cost: about USD 0.11** for all 140 clips (USD 15 per million characters is the standard neural voice figure on Microsoft Learn's "Azure AI Speech quotas and limits"; the public pricing page did not show it, so confirm it first). **Nothing has been generated.** What needs the owner's approval first:

1. Read the key and region of the existing Speech-capable account (the Foundry account is of kind AIServices, S0) without printing them; it has not been checked that its key works against the regional text-to-speech endpoint.
2. Read the Azure AI Speech **Product Terms** in the original, on what may be done with the audio output (the summary seen so far suggests the right to publish synthesised audio is reserved to paid-tier customers, which S0 is). If the terms do not allow shipping the clips, stop: the page keeps the browser voice.
3. One test request, then the rest: `--generate --limit 1`, listen to the clip, then `--generate`. The tool only makes missing clips, refuses to send more than `--max-chars` (10,000) characters, retries 429 and 5xx with a growing wait, and writes the manifest after each clip so a stopped run resumes.

```powershell
# not run
$env:AZURE_SPEECH_KEY = "<read from the portal, never written to a file or a chat>"
$env:AZURE_SPEECH_REGION = "italynorth"
cd backend
.\.venv\Scripts\python.exe -m app.clips_build --generate --limit 1
.\.venv\Scripts\python.exe -m app.clips_build --generate
cd ..
```

Then run the tests, listen to a clip of each language, commit `backend/app/audio/` (about 3 MB) and rebuild the image. The page says the voice is synthetic (S28); keep that note. Until the clips exist, the page does not offer the Azure voice at all (S29) and the default browser voice is used, which depends on the voices installed in the judge's browser and system (the page says when there is none for the language, S30): the video and the README must not claim an Azure voice before this step.

## Publishing the image (G2: done 2026-10-21)

The workflow job `publish` in `.github/workflows/ci.yml` **never runs on a push or a pull request**: ordinary CI (backend, sdk, e2e, docker) runs on both, and `publish` runs only when the owner starts the workflow by hand (Actions tab, "Run workflow", branch `main`), after those four jobs pass, with the built-in `GITHUB_TOKEN` (`packages: write`, nothing else, no Azure identity). So the first push of the repository publishes nothing. The whole workflow also runs with a read-only token (`permissions: contents: read` at the top, a test checks it); only `publish` adds `packages: write`. A manual run pushes `ghcr.io/diego-sicignano/soundpitch:<commit sha>`; there is no `latest` tag. The `Dockerfile` label `org.opencontainers.image.source` links the package to the repository; the repository address in it is the **planned** one (`diego-sicignano/soundpitch`); the repository does not exist yet, and the label, the image names in this file and the workflow's owner (taken from the repository at run time) must be corrected if it is created under another name.

A new package is **private**. Making it public is a manual, irreversible step (package settings, "Change visibility"), and it needs the owner's approval. Then test an anonymous pull:

```powershell
# not run
docker logout ghcr.io
docker pull ghcr.io/diego-sicignano/soundpitch:<sha>
```

## Hosting on Azure Container Apps, Consumption only (G4 and G5 done 2026-10-21, G6 pending)

The cheapest form of the service, for the judging window only: its own resource group, a Consumption-only (legacy) environment with no logging destination, one container app that scales to zero and runs at most one replica.

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

Free grants (documented, per subscription and calendar month): 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests, equal to 200 replica-hours at this size. Modelled judge traffic uses 3 to 125 hours in the whole window; kept awake 24/7 the cost would be about USD 1.5 in October and USD 1.9 in November. The numbers and their sources are in the ticket.

**Commands (not run; check each flag against the current `az containerapp` reference first).** Sign in as the owner, check the subscription, and register the provider only with approval (it is free, but it cannot be undone while resources of that provider exist). Install the `containerapp` extension only if the CLI asks for it.

```powershell
az login
az account show --query "{name:name, id:id}"
az provider register --namespace Microsoft.App --wait
# only if the CLI asks: az extension add --name containerapp --upgrade

$image = "ghcr.io/diego-sicignano/soundpitch:<commit sha>"
az group create --name rg-soundpitch-demo --location italynorth
az containerapp env create --name cae-soundpitch --resource-group rg-soundpitch-demo --location italynorth --enable-workload-profiles false --logs-destination none
az containerapp create --name soundpitch --resource-group rg-soundpitch-demo --environment cae-soundpitch --image $image --ingress external --target-port 8000 --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi --env-vars SOUNDPITCH_LLM=replay SOUNDPITCH_TRUST_PROXY=1 SOUNDPITCH_LOG_FORWARDED=1
az containerapp show --name soundpitch --resource-group rg-soundpitch-demo --query "{fqdn:properties.configuration.ingress.fqdn, min:properties.template.scale.minReplicas, max:properties.template.scale.maxReplicas}"
```

Things that may need a different command, to be settled in the documentation or by the first error, not guessed: whether the legacy environment type can still be created in October 2026 and combines with `--logs-destination none`; if it cannot, use the default environment with only its Consumption profile and the same settings. Whether a public GitHub image needs `az containerapp registry set --server ghcr.io` (the documentation contradicts itself): try the plain create first. Whether the console log stream can be read with no logging destination (`az containerapp logs show --name soundpitch --resource-group rg-soundpitch-demo --follow`); if not, the `X-Forwarded-For` format stays unconfirmed and the safe behaviour is that an unreadable value falls back to the connection address.

**Acceptance on the public address (G5).** The first request may be slow (cold start; no official duration exists for this plan).

```powershell
cd backend; .\.venv\Scripts\python.exe -m app.smoke https://<fqdn>; cd ..
```

It must exit 0. Also check by hand: `/api/health` shows `"llm":"replay"` and `replies` 26; `/api/voice` shows the stored clips per language (zeros and `live: false` until the clips are made and shipped, and then the page disables the Azure voice option and speaks with the browser voice); both languages; transcript, captions, ball sound, calm mode and screen-reader output; `/api/cuesheet` and its schema; the security headers; `POST /api/tts` for text that was not issued answers `403`; a clean browser window with no login; and that it works with no Foundry credential. Then set `SOUNDPITCH_LOG_FORWARDED` back off if the shape was seen.

### Cost check (G6; read-only commands; step 1 done, steps 2 to 4 pending)

Pay-As-You-Go has no spending limit; the 5 EUR budget only e-mails. The public price list has three undocumented meters named `Environment` (`Environment Management Hour`, `Environment Planned Maintenance Hour`, `Environment Private Endpoint`; USD 0.13 an hour in Italy North, effective 2026-09-01 to 2026-10-31). The most probable reading, an inference, is that they split the documented "Dedicated Plan Management" fee by cause, which this setup does not trigger. If they applied to every environment the cost would be about USD 3.1 a day. So the first deployment is followed by a check:

1. The same day: `az containerapp env show --name cae-soundpitch --resource-group rg-soundpitch-demo --query "{profiles:properties.workloadProfiles, plan:sku.name}"` shows no Dedicated or Flexible profile, and no private endpoint or maintenance window exists.
2. After 8 to 24 hours (on a new subscription up to 48 hours, and earlier queries on this one answered `NotFound` and `[]`): in the portal, Cost Management, Cost analysis, scope = the subscription, filter resource group `rg-soundpitch-demo`, group by Meter. Or read-only from the CLI: `az consumption usage list --start-date <yyyy-mm-dd> --end-date <yyyy-mm-dd> --query "[?contains(instanceName,'soundpitch') || contains(instanceName,'cae-soundpitch')]" -o table`.
3. Any line named `Environment` with a cost above 0, or an unexplained one, means: **delete the environment at once** (the loss is about USD 3 to 6) and move to the fallback. If no cost data appears after 48 hours the check cannot be done: ask the owner whether to keep the service running anyway, or use the fallback.
4. Repeat once on the day before the end of judging.

### Rollback and cleanup (*not run*)

```powershell
# back to a previous image
az containerapp update --name soundpitch --resource-group rg-soundpitch-demo --image ghcr.io/diego-sicignano/soundpitch:<previous sha>
# take it offline without deleting
az containerapp ingress disable --name soundpitch --resource-group rg-soundpitch-demo
# stop every charge: delete the group (it holds nothing else)
az group delete --name rg-soundpitch-demo --yes
```

**Keep it up until 10 Nov 2026, 23:59 Pacific** (11 Nov, 08:59 in Italy): rules 4.8 require the project to be available free of charge and without restriction until the judging period ends. Delete the group only after that, and put both dates in the calendar.

## Deployment record (2026-10-21)

**CI.** The workflow was registered by GitHub only after the first push, and pushes of `main` and of a temporary branch started no run (the repository's events list showed no push event; the cause is on GitHub's side and was not found). `workflow_dispatch` works, so CI was started by hand: [run 39621035417](https://github.com/diego-sicignano/soundpitch/actions/runs/39621035417) on `42c004a` found one genuine failure, the end-to-end test S25 on Linux: the settings form carried an inline `onsubmit` that the page's own content security policy blocks (fixed in `09db91c`, with a test that no element carries an inline handler). [Run 39622166407](https://github.com/diego-sicignano/soundpitch/actions/runs/39622166407) on `09db91c`: backend, SDK, end-to-end and Docker jobs green, then `publish` pushed `ghcr.io/diego-sicignano/soundpitch:09db91c21a048312e1855c45f3629e07d7b6e54d`. The workflow's `publish` job runs on a manual dispatch of `main`, so every dispatch publishes.

**Image.** The package was already public (the repository is public and the image is linked to it by its source label): an anonymous registry token and manifest request answered 200 and `docker pull` after `docker logout ghcr.io` worked. Inspected: user 10001, `SOUNDPITCH_LLM=replay`, no key or credential in its environment or build history.

**Azure** (the pay-as-you-go subscription, checked by name and offer, never the Azure for Students one; `Microsoft.App` registered; the `containerapp` CLI extension installed): resource group `rg-soundpitch-demo`, environment `cae-soundpitch` created with `--enable-workload-profiles false --logs-destination none` (no workload profiles, no Log Analytics), container app `soundpitch` with the image above, external ingress on port 8000, 0.25 vCPU and 0.5 GiB, minimum 0 and maximum 1 replica, environment variables `SOUNDPITCH_LLM=replay`, `SOUNDPITCH_TRUST_PROXY=1`, `SOUNDPITCH_LOG_FORWARDED=1`, no secret and no registry credential. The public image needed no `registry set`.

**Acceptance (G5).** `python -m app.smoke` on the public address: `ok`. A read-only script checked: `/api/health` (`replay`, 26 replies), the page without a login, the security headers and the policy, no inline handler, five presets, goal 1 in English (attempt 1) and Italian (attempt 2, per D20) with every must-say moment scheduled and no fallback, `/api/cuesheet` and its schema, WebVTT, `/api/voice` (no stored clips, not live), `POST /api/tts` with unissued text answering `403`, and an unknown preset answering `404`. The first request to the new app took 16.8 s (cold start); later ones about 0.1 s. The page flow (play, transcript, captions, ball sound) is covered by the end-to-end suite that ran in CI against the same code; it was not driven in a browser against the public address.

**Cost gate.** G6 step 1 done: the environment has no workload profile (`workloadProfiles: null`, no Dedicated or Flexible plan), no private endpoint and no maintenance window. Steps 2 to 4 (Cost Management after 8 to 48 hours, any `Environment` meter above 0 means delete the environment and use the fallback, and once more before 10 Nov) are **pending**.

## Fallbacks

- **Render Free (USD 0, not on Azure).** A web service from the same image (`ghcr.io/diego-sicignano/soundpitch:<sha>`) or from the repository's `Dockerfile`, no environment variable but `SOUNDPITCH_LLM=replay`, and `SOUNDPITCH_TRUST_PROXY=1` only after reading how Render writes `X-Forwarded-For`. Limits to accept: 0.1 CPU and 512 MB, spin-down after 15 minutes without traffic and about a minute to wake, 750 free hours a month, and a bandwidth cap that suspends all free services if exceeded. Not confirmed: that the Free type takes an image-backed service and that a public ghcr.io image pulls without credentials (a deploy from the repository is the alternative). It would not count as Azure hosting for criterion 3.
- **Azure App Service, Linux B1.** About USD 8.8 for the window, fixed. Not approved.

## Cost summary

| Item | State | Control |
|---|---|---|
| Foundry deployment `soundpitch-mini` (`gpt-4.1-mini`, Global Standard, capacity 8) | exists, created 2026-10-20; used on that day (a full recording run is about USD 0.03; Azure Cost Management shows EUR 0.05, USD 0.057, for everything on the subscription through 2026-10-21; the earlier test usage on an Azure for Students subscription, and the credit it used, are in `docs/hackathon/COMPLIANCE.md` and D23) | not called by the judges' path; the ledger (D11) limits a live run; Azure's 5 EUR budget only sends e-mail |
| Speech clips | not generated | about USD 0.11 once, on the existing S0 resource, after approval |
| Hosting | deployed 2026-10-21 | Container Apps Consumption, scale to zero, one replica at most, inside the monthly grants; cost gate G6; group deleted after judging |
| Speech at run time | none | the public app holds no key |

Azure's budgets alert, they do not stop spending (Microsoft Learn, "Create and manage budgets": a budget does not affect resources or stop consumption; cost data arrives 8 to 24 hours late). An automatic stop would need an action group calling a function; it was not built.

## Gates

| Gate | What | Cost | Approval |
|---|---|---|---|
| G0 | offline code, tests, CI (done) | 0 | no |
| G1 | public repository and push (done 2026-10-21) | 0 | yes: visible, hard to undo |
| G2 | publish workflow started by hand; package public; anonymous pull (done 2026-10-21) | 0 | yes: irreversible visibility |
| G3 | Speech: read key, Product Terms, 1 test clip, 140 clips | about USD 0.11 | yes |
| G4 | register `Microsoft.App`, create the group, environment and app (done 2026-10-21) | inside the grants, per the cost gate | yes |
| G5 | acceptance on the public address (done 2026-10-21) | 0 | no |
| G6 | cost check after 8 to 48 hours | 0 | no; a bad result means delete and fall back |
