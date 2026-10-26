# Decisions

Short records of choices that shaped the project. Add an entry when you make a choice that someone could reasonably undo.

## D1. Code decides truth, the model only chooses words (2026-10-19)

Every sentence is checked against the events before it reaches a listener. A blind listener cannot see that a description is wrong, so an invented player or score is worse than silence. **Consequence:** a model can never put unverified text on air; it costs us a verifier and a fallback to maintain.

## D2. A deterministic template describer is both the offline mode and the fallback (2026-10-19)

It works with no network and always passes the verifier. **Consequence:** tests, the demo and the page work without any key; the model is an upgrade, not a dependency.

## D3. A synthetic match with a pinned storyline (2026-10-19)

Goals at 16', 52', 78' and a final 2-1, so every demo and test lands on the same moments. Random play never scores. Rules 4.7 require synthetic data. **Consequence:** the match is not realistic in detail, and positions are generated, not measured.

## D4. The timing planner is plain arithmetic (2026-10-19)

A speech duration estimate, a lag budget per priority, and slots reserved in priority order. No learned model. **Consequence:** results are deterministic and explainable, and counted in `docs/evaluation.md`. Real voices speak at their own speed, so estimates can be off by a little.

## D5. A plain HTML page, no build step (2026-10-19)

One `index.html`, `styles.css`, `app.js`. Accessibility is the product, and the less framework between the markup and the user, the easier it is to get right and to audit with axe. **Consequence:** no components or type checking on the front end; the server does the thinking.

## D6. One container serves the page and the API (2026-10-19)

FastAPI mounts the static page. One image, one URL, easy to host on Azure Container Apps and for judges to open. **Consequence:** the page and the API scale together.

## D7. The browser voice is the default, Azure neural voices are opt-in (2026-10-19)

The page works for anyone with no key and no cost. Azure AI Speech needs a key, so it is guarded by a per-minute limit. **Consequence:** the demo's best audio needs a configured server.

## D8. English and Italian only (2026-10-19)

The rules ask for multi-language output; two languages show it without diluting the verifier. The verifier is language independent, so adding a language means adding templates. **Consequence:** other languages are out of scope for the hackathon.
## D9. The gate checks grounding: canonical phrases and a closed vocabulary (2026-10-19)

D1 says the model only chooses words. The first verifier compared the refs a describer *claimed* with the events and checked names and numbers, but did not tie the text to the facts: a wrong team, a swapped score, an invented player or an outcome of another kind of event all passed (probes run on 2026-10-19; the template describer hid it because it is right by construction).

The verifier now derives the facts of a moment from the events (`describer.facts`) and accepts a description only if: its refs are exactly the refs the code derives (a describer cannot certify its own claims); facts that carry a relation (score, assist clause, build-up chain, lane, zone, direction, minute) appear only as exact phrases built by code; the only names are the moment's own player and team; every other word is in the closed vocabulary of the moment's template key (its templates' words) or is an article or "and"; no symbol, emoji or control character; the text contains an outcome word of its kind (a word only that kind of event uses) and fits 400 characters; a name stands only between the neighbour words some template of the key gives it (the position rule); required facts are present (SPEC §5). A check that cannot run rejects (fail closed).

**Reversed during review.** A first version also shared "is/are", "it/that/this" and simple prepositions (`for to on at by with`, `per di su al`) between all kinds to reduce false rejection. An adversarial review showed this opens real attribution flips ("Marsh scores on Northgate", "Foul on Costa", "Marsh è assist di Adeyemi"): a word that relates two facts must come from the templates of one kind of event. Only articles and "and" are shared. Lesson: false rejection is not fixed by widening the shared list.

**Position rule (added after review).** Words from the right list could still be arranged into a wrong attribution ("Foul of Costa by Harbour"). A name now has to stand where a template stands it, and so does every canonical phrase: a second review round showed that the score phrase (it starts with the home team) could stand where a team belongs, and the assist clause could act as a subject. Measured cost on the corpus written with the word list in hand, sentence-on-moment pairs accepted: 68.7% to 46.9% in English, 85.5% to 78.6% in Italian; template variants unaffected. Chosen because attribution is the point of the product and a rejected sentence only costs naturalness.

**Rejected alternatives.** Open prose plus deny lists: a list is never complete, and relations ("scores for" or "against") cannot be told apart by pattern. Slot-only wording: another representation for every describer, and the final text still has to be verified; an adapter may use placeholders anyway. An LLM as judge: code would stop deciding what is true. Templates only: safe, but leaves the model nothing to do.

**Consequences.** The guarantee is bounded and stated: facts and words come from the moment and a reviewed list; the *meaning* of prose built from allowed words is not verified. Expect false rejections (the evaluation measures them on hand-written wording, with and without the word list in hand, and reports the share of moments that end in the template); the verified template fallback absorbs them, so they cost naturalness, not trust. The vocabulary grows only by reviewing rejected words from real model output (T02b), and a word may join only if it cannot change a fact. Two templates changed to fit: the assist became a canonical clause, and "wide of the goal" lost "goal" so outcome words stay exclusive to one kind of event (a test enforces it). Italian is the weaker language: articles and contractions reject variants a human would accept.

## D10. Foundry through Agent Framework's `FoundryChatClient`, behind one small seam (2026-10-19)

**Choice.** `agent-framework-foundry` 1.14.1 with `agent-framework-core` 1.22.0, `agent-framework-openai` 1.17.0, `azure-ai-projects` 2.7.0, `azure-identity` 1.26.0 and `openai` 3.35.1, pinned in `backend/requirements-agents.txt`. Checked in a throwaway Python 3.13 environment beside the core pins: it installs with no conflict (`pip check` clean), the core `httpx 0.28.1` and `pydantic 2.14.1` are untouched, and `FoundryChatClient(project_endpoint=, model=, credential=)` builds offline with an async `DefaultAzureCredential`. The API used is documented on Microsoft Learn: `await client.get_response(messages, options={"response_format": Model})`, a typed `response.value`. 1.15.0 was five days old at the decision and exposes the same API; 1.14.1 is the patch release after 1.14.0 and eleven days old, so it was preferred. Both resolve to the same dependencies. Ticket T03 needs the same package, so one stack serves both.

**Alternatives.** `azure-ai-projects` plus `openai` directly: fewer packages and a native `timeout`, but a second client stack once T03 brings Agent Framework, and the structured-output call is the same Responses API. Not chosen; the seam (`LlmClient.complete(system, user) -> str`) makes the swap one class. A generic OpenAI-compatible endpoint: no Foundry identity story. Not chosen.

**Design.** `FoundryDescriber` holds no SDK type: it builds the prompt, calls an `LlmClient`, parses `{items: [{moment_id, full, short}]}` into `Description` with the refs of `describer.facts`, and returns them. Verification, retries, the fallback and timing stay in the pipeline (D1, D9); the adapter does not repeat them. The real adapter lives on one long-lived event loop in a daemon thread because the SDK client is async and must not be shared across threads or loops; this reuses the connection and the token. Structured output narrows the shape of a reply, never its truth: the text is parsed again and verified as any other.

**Cache.** The model's replies are cached by (match seed, language, the moments asked about, the issues sent, the instructions), in the database of the usage ledger (D11), so they also survive a restart. The describer sees nothing of speech rate, ball sound or calm mode, so those never cause a call; this is why the cost is bounded by windows, not by profiles. The cache holds replies, not verdicts, so a parsable reply that the verifier rejects is rejected again each time and its retries replay from the cache too; an unparsable reply or a failed call is never cached, so a bad moment does not pin a window to templates. Three failures found by an adversarial review shaped the rest: identical requests in flight share one call (single flight); at most two calls run at once and a saturated pool fails fast without reserving anything; the API does not keep a session built during an outage or over the cap (an `lru_cache` would have kept it until restart). The fence around a JSON reply is stripped without a regular expression, which a degenerate reply could make backtrack for minutes.

**Azure setup (2026-10-20), and its limits.** A Foundry account and project (Italy North) on a **pay-as-you-go** subscription (an earlier deployment of the same name on an Azure for Students subscription was used for testing, D23), and one deployment, `soundpitch-mini`: model `gpt-4.1-mini` (2025-04-14), SKU `GlobalStandard`. Capacity was 10 (10 requests and 10,000 tokens per minute) and was lowered in place to **8 (8 requests and 8,000 tokens a minute)** on 2026-10-20, see D11; above it the service answers 429, which the pipeline treats as a failed attempt. The cheapest model that gives the quality needed was chosen: list price USD 0.40 per million input tokens and 1.60 per million output tokens (checked 2026-10-20). A budget of 5 EUR a month with alerts at 50%, 100% and a forecast exists on the resource group, and **it only sends e-mail**: Azure has no pay-as-you-go cutoff, and cost data arrives 8 to 24 hours late. Data is processed outside the region (GlobalStandard); the match is synthetic. Authentication is `az login` (`DefaultAzureCredential`), no key anywhere. In the app, the usage ledger (D11) decides every call. Settings are in the git-ignored `backend/.env`.

**Live acceptance (S12), 2026-10-20.** `docs/evidence/foundry-run.md`: 26 calls, 81 of 81 moments verified at the first attempt in each language, no failed call, median latency 3.31 s, p95 4.52 s, slowest 4.81 s (the figures the run printed and the evidence file records; Two things the run taught: a first prompt answered for 1 moment of 10 (the example reply in the prompt had one item), fixed with `items_expected` and a test; and the model mostly **copies** the template sentences it is shown: its wording differs from every template sentence in only 1.2% of English cues and 16.0% of Italian ones. (The run predates D11: it used per-process caps raised for the run and 6,000 output tokens. A new full run would need the ledger limits raised on purpose and was not done.) The verifier is not what limits it: the vocabulary and the positions are. Whether to give the model more room (richer templates, a reviewed vocabulary) or to accept that Foundry mostly confirms the templates is a product decision, not a verifier setting.

**Undo.** `az cognitiveservices account deployment delete -n <account> -g <resource-group> --deployment-name soundpitch-mini` removes the deployment (the cost hardening did not delete it, and created nothing). Capacity is restored with `az cognitiveservices account deployment create ... --sku-capacity 10`.

## D11. A durable usage ledger decides every model call (2026-10-20)

**Why.** The per-minute and per-day caps of D10 lived in the memory of one process: a restart cleared them, several workers would each have their own, and nothing counted money. The Azure side cannot fill the gap: the deployment allocation limits **throughput** (tokens per minute, estimated from the prompt text plus `max_tokens`, 429 above it), and the Azure budget only **alerts**, 8 to 24 hours late (Microsoft Learn, cost-management budgets, checked 2026-10-20). Neither stops spending.

**What.** `backend/app/usage.py`: a SQLite file (standard library, no new dependency, no new paid resource). `reserve` runs in one `BEGIN IMMEDIATE` transaction that counts the calls of the last minute and of the UTC day, the tokens of the day and the estimated euros of the month, refuses if the worst case of this call does not fit, and otherwise records the reservation; that is what makes concurrent threads and processes on one host unable to overshoot. `settle` replaces the estimate with the provider's reported usage. Failure, timeout and cancellation keep the worst case. An unreadable database refuses the call. Money is stored in integer micro-units (column `micro_eur`), see Currency below. Replies that parse are kept in the same file, so the 20 calls a day are spent only on windows nobody has asked yet.

**Numbers.** 2 calls a minute, 20 a day, 120,000 tokens a day, 2.00 EUR a month, 1,000 output tokens a request, 20 moments a chunk. A window needs one call of about 2,000 input and 300 output tokens, so a real call costs about 0.0016 at the ledger rate (the one measured call, 686 input and 34 output tokens, was 0.000411); 20 a day is about 0.03 a day, and the monthly ceiling is a backstop 60% below the budget. The reservation uses the same rate and three SDK attempts, so an in-flight call is held at about 0.013.

**Currency (audit of 2026-10-20).** The list price is in US dollars (0.40 and 1.60 per million tokens). The policy is now explicit in code (`usage.LIST_USD_PER_MILLION_*`, `EUR_PER_USD = 1.0`, `SAFETY_MARGIN = 1.25`) and tested: **1 USD is counted as 1 EUR**, with no exchange rate fetched, plus 25%. It over-counts while a dollar is worth less than a euro (not checked here) and it is not a statement about the bill, which is in the subscription's billing currency (not read). 686 input and 34 output tokens: USD 0.0003288 at list, 0.000411 with the margin, stored as 411 micro-units.

**Retries and in-flight (audit).** The `openai` 3.35.1 client inside `FoundryChatClient` has `max_retries = 2` (read offline, not changed by the application), all within the adapter's 20 s timeout. The month reservation is cost x 3; the day token reservation is tokens x 1 (the 20-call daily cap bounds repeats). A reservation never settled (error, timeout, killed process) stays at its worst case until the month ends; 83 reservations of the largest allowed call reach 2.00 (a test). A provider usage report above the output allowance is recorded as reported; it used to be clamped, which could hide spend, and was fixed.

**Persistence in the actual configuration (audit; superseded by D12 for the judges' image, which no longer uses the ledger).** Default file `backend/data/usage.sqlite` next to the source: on a developer machine it is on the host disk, git-ignored, and a fresh process read the same totals. In the current `Dockerfile` it is `/srv/backend/data/usage.sqlite`, the image runs as a non-root user and `/srv/backend` belongs to root, no `VOLUME` or `SOUNDPITCH_USAGE_DB` is set, and the image has not been built: the directory could not be created, so the ledger would be unavailable and every model call refused (the templates speak). Even if it were writable, a container's disk is lost when the container is replaced. There is therefore **no protection across deployments, replicas or ephemeral restarts** until T06 mounts a writable persistent volume and sets `SOUNDPITCH_USAGE_DB`.

**Alternatives.** Process memory only: lost on restart, per worker. A managed store (Table, Cosmos, Redis): shared by replicas, but a new paid resource and a new dependency for a hackathon demo; not built for a demo. Counting only requests: blind to long prompts. An automatic cutoff at the budget: needs an action group and a function; not built.

**Limits that remain.** One host only. A hosted copy would need the file on a persistent volume and one replica; on an ephemeral disk the counters restart from zero at each deployment, and then only the Azure allocation and the budget alert stand behind the application. The prices are assumptions with a margin, not a guarantee.

**Azure side, 2026-10-20 (read, then one change).** Read: one deployment (`soundpitch-mini`), `GlobalStandard`, capacity 10 = 10 requests and 10,000 tokens per minute, no provisioned throughput, the budget above with spend 0. The application allows 2 calls a minute and each is estimated by the service at about 3,200 tokens (prompt of about 2,200 plus 1,000 `max_tokens`, counted even when unused), so it needs about 6,400 tokens a minute. Capacity 8 still covers that and lowers the burst anybody holding the credential could send; it is a throughput limit, not a spending limit, and it saves nothing by itself. Changed in place with `az cognitiveservices account deployment create` and the same model, version and SKU (no second deployment, nothing deleted); reversible the same way. Not done and not claimed: an automatic cutoff. One would be a budget action group calling a function that deletes the deployment; it is a new paid resource and was not built.

**What is enforced, and what is not.** Per call: at most 1,000 output tokens, 20 moments, a prompt estimated at 12,000 tokens or less, a 20 s timeout, 2 in flight. Per host, durably: 2 calls a minute, 20 a day, 120,000 tokens a day, 2.00 EUR a month of estimated spend (configurable in the environment; only the month has a fixed maximum, 4.00). Not enforced: spending on another host or by another process that does not use the ledger (a person with the Azure credential can call the deployment directly); the real bill (the ledger counts the usage the service reports at 1.25 times the list price, the SDK may retry a failed request twice and only the final attempt reports usage, so the worst case is reserved for three attempts and a call that failed stays at its worst case). Evidence: `docs/evidence/cost-safety.md`.

## D12. The judges' demo replays recorded Foundry replies; it makes no live model call (2026-10-20)

**Why.** Rules 4.8 ask for the project to be available "free of charge and without any restriction" to the judges until the judging period ends, and do not say what counts as a restriction. A live model behind a daily cap would be a restriction the moment the cap is spent, and the cost ledger (D11) needs a persistent writable file that a container does not give (the image ran as a non-root user with a root-owned working directory, so every model call would have been refused; and mounted network storage is the wrong place for SQLite). But the demo is a **finite set**: the API accepts only a preset, a detail level and a language, and speech rate, ball sound and calm mode never reach the prompt, so there are 5 x 3 x 2 = 30 windows (about 30 to 60 requests to the model, first attempts only).

**Choice.** `SOUNDPITCH_LLM=replay` (`backend/app/replay.py`). A JSON file holds, for each request, the reply a Foundry model gave to the *same* request earlier (the key is the one of the ledger's reply cache: match seed, language, attempt, moments, issues, instructions). A recorded reply is data, not a verdict: it is turned into descriptions with the code's refs and **the verifier checks every session**, so a stale, edited or hostile record can only end in the template fallback. A request with no record is described by the templates and the trace says so. The file is produced offline from the ledger of an approved live run (`python -m app.foundry_run`, then `python -m app.replay_export`); `--check` reports coverage. The Docker image runs this mode and needs no key, no network, no writable path.

**Alternatives.** *Live Foundry in the judges' path, ledger on the container's ephemeral disk*: counters reset at every restart and the 4.8 question stays open. *Ledger on Azure Files*: the App Service documentation advises against SQLite on mounted storage and SQLite's guide warns about network file systems; not tried. *A managed store (Table, Cosmos DB)*: a new paid resource and new code to make a feature the judges do not need. *Only templates in the demo*: honest but shows nothing of Foundry; replay keeps the words a model wrote and the proof (`docs/evidence/foundry-run.md`) that they pass. *A static prebuilt site*: loses the live verifier and the profile options.

**Consequences.** The public demo costs nothing however many judges use it, and works with the network cut. The words are those of one recorded run of one deployment, so a changed prompt, template or vocabulary invalidates the file (a test fails once the file has content and no longer covers every window). It was recorded on 2026-10-20 (T11) and again on 2026-10-26 with a prompt that asks for the model's own wording within the vocabulary: 26 replies cover all 30 windows, every session replays verified at the first attempt, and about 29% of the cues are in the model's own words. Without the file the replay mode speaks the verified templates and `/api/health` says `"replies": 0`. The live describer and the ledger stay in the code for recording and experiments; they are not served publicly.

## D13. The Agent Framework workflow reuses the pipeline's steps (2026-10-20)

**Choice.** `backend/app/workflow.py` builds the pipeline as a Microsoft Agent Framework graph: executors `MomentDetector`, `Describer`, `Verifier`, `Fallback`, `TimingPlanner`, a conditional edge from `Verifier` back to `Describer` for the retry, and the `Session` as the workflow output. Each executor calls the function of `app.pipeline` that the plain pipeline also calls (`describe_step`, `verify_step`, `fallback_step`, `assemble_session`), so the two orchestrators cannot drift; a test (S13) compares their cues, statuses and report over presets, languages, scenarios and a recorded-reply store. Selected by `SOUNDPITCH_ORCHESTRATOR=workflow`; `plain` stays the default and needs no framework.

**Found with the installed version (agent-framework-core 1.22.0, Python 3.13, read from the package, not from memory).** `WorkflowBuilder(start_executor=..., output_from=[...])`, `@executor(id=...)` on async functions with a `WorkflowContext[Out]` or `WorkflowContext[Never, Final]` annotation, `add_edge(source, target, condition=callable)`, `await workflow.run(message)` returning a result with `get_outputs()`. A prototype showed that edge conditions are evaluated when a message is **delivered**, so a message mutated by its sender sent a finished round down two edges at once; messages are therefore immutable frozen dataclasses copied at each step.

**What it is not.** The model is not an autonomous agent with tools, and the framework does not make answers better: it makes the control flow explicit, drawable and traced executor by executor (`TraceStep.executor`). Only the `Describer` touches a model; truth stays in code (D1). The framework is also used for the model call itself (`FoundryChatClient`, D10).

**Alternatives.** No workflow (the loop is a few lines; the graph adds a dependency and a second code path): rejected because an explicit graph can be drawn, traced executor by executor and extended, for the cost of one module and one optional package. Foundry hosted agents or prompt agents: a managed service and a deployment for what a function does, and the verifier must stay in our code. Handoff or group-chat orchestration: nothing here needs agents to talk to each other. A fan-out of verifiers: nothing to parallelise.

**Consequences.** A new use of the optional dependency set (already pinned for the Foundry adapter); CI has a job that runs the tests that need it. `asyncio.run` per request means this orchestrator is for the synchronous API handlers only (FastAPI runs them in a thread pool).

## D14. The voice endpoint speaks only text a session returned (2026-10-20)

**Why.** `POST /api/tts` accepted any text of up to 400 characters and was limited only by a process-wide requests-per-minute counter: an open text-to-speech proxy that a single script could hold at the limit (starving real users) and that would spend Speech characters for anyone. The page only ever sends cue text.

**Choice** (SPEC §8, S22). The server remembers the `(language, text)` of every cue it has returned and refuses anything else (`403 tts_text_not_issued`); keeps the audio of each `(language, text, speech-rate percent)` so repetitions cost nothing; and refuses before calling Azure when a client, the process, the UTC day or the UTC month is over its limit (defaults 30 and 120 requests a minute, 60,000 characters a day, 300,000 a month). The client is the connection's address, or the last `X-Forwarded-For` entry only with `SOUNDPITCH_TRUST_PROXY=1`.

**What it is not.** The counters live in the memory of one process and restart at zero, so they are a brake, not a spending cap. The only hard cap on Speech spending is the pricing tier of the Speech resource, which has not been chosen (T04); the daily and monthly defaults are conservative guesses to be set under that tier's allowance once it is known. Behind a proxy without `SOUNDPITCH_TRUST_PROXY=1` every caller shares one per-client bucket.

**Alternatives.** A signed token per cue (stateless, survives restarts, more code and a secret to manage). Pre-rendering every clip into the image (no Speech call at run time, a licensing question about redistributing synthesised audio, and a large image). A durable counter in a file or table (the same persistence problem as D11).

## D15. The cue sheet is a discriminated union, validated by the models that make its schema (2026-10-20)

**Choice** (SPEC §13, S15). `CueSheet` with items of three `type`s (`audio_description`, `caption`, `ball_sound`) so that each type has exactly its own fields and `extra="forbid"` holds; a ball sound has no duration because the player decides how long it lasts, and no `event_ids` or priority because the session's earcons carry neither (adding them would change `Session`). The JSON Schema is generated from `contracts.py`, served at `/api/cuesheet.schema.json` and committed under `docs/contracts/`; a test fails if the committed file differs from the generated one. No second validator (`jsonschema`) is a dependency, so "validates against the schema" means "validates against the models that produced it"; an independent consumer can use the committed schema with any validator.

**Alternatives.** One flat item type with optional fields (a looser schema that cannot say which fields belong to which type). Adding the validator library for tests (a dependency for a check the models already make).

## D16. Security headers and a content security policy (2026-10-20)

Every response carries `nosniff`, `Referrer-Policy: no-referrer` and `X-Frame-Options: DENY`; everything except the interactive API documentation also carries `default-src 'self'` and `frame-ancestors 'none'` (SPEC §8, S25). The page has no inline script or style and no external request, so nothing is relaxed, and an end-to-end test fails on a policy violation. The documentation pages (`/docs`, `/redoc`) load their own scripts and get no policy; they are left on because a judge can read the API contract there and they expose nothing the repository does not. No CORS is configured: the page and the API share an origin.

## D17. Hosting target: Container Apps, Consumption only, with stored clips (2026-10-20; hosting made optional by D25 and D26)

**Why.** The page can say only a finite set of sentences (140: 72 English, 68 Italian, 7,141 characters). A live Speech key in a public app would be a spending risk that the in-memory limits of D14 do not cap, and the judges must be able to use the demo free of charge and without restriction (rules 4.8).

**Choice** (SPEC §8, §15, S26 to S28). The voice clips are made once with `python -m app.clips_build --generate` (about 3 MB of mp3, normal speed, no markup) and shipped in the image under `backend/app/audio/` with a manifest that records the language and text of each clip. `POST /api/tts` serves a stored clip before it needs a key, so the public app holds no Speech key and has no quota to exhaust; the page applies the chosen speed with `playbackRate` (header `X-Audio-Rate`) and says that the voice is synthetic. The live Speech path stays for local use. The host is Azure Container Apps on the Consumption plan, in its own resource group: a legacy Consumption-only environment, no Log Analytics, minimum replicas 0, maximum 1, 0.25 vCPU and 0.5 GiB, replay mode, no secret, no volume, image from a public GitHub Container Registry package tagged with the commit SHA. `X-Forwarded-For` is read defensively (last entry, port and IPv6 forms), only with `SOUNDPITCH_TRUST_PROXY=1`.

**Fallbacks, in order of cost.** Render Free (no Azure cost; spin-down and a cold start) if the Environment meters of Container Apps cannot be explained or controlled; Azure App Service B1 (about USD 8.8 for the window) was not approved.

**What it is not.** The free grants are per subscription and month; the `Environment` meters in the public price list are undocumented and are checked by a cost gate after the first deployment (docs/DEPLOY.md). Pay-As-You-Go has no spending limit, and a budget only alerts.

**Alternatives.** A live Speech key behind the limits of D14 (a cost that only the pricing tier caps). A minimum of one replica (no cold start, about USD 1.4 to 3.4 more in the window). App Service (fixed cost, not approved). Azure Container Registry (a monthly cost for no need). Synthesising clips in the browser (not the Azure voice the project shows). D14 listed pre-rendering as an alternative because of a licensing question and an assumed large image; the image grows by about 3 MB, and the licence question is settled by reading the Product Terms before the clips are published.

## D18. The context of a moment is a sentence written by code, added after verification (2026-10-20)

**Why.** The official rules ask for the context behind the events and for why a moment matters, not only for what happened. SoundPitch said who scored and the score, but a listener had to work out for themselves that 1-1 means an equaliser. The recorded model copies the templates (D10), so asking it for context would add risk, not meaning.

**Choice** (SPEC §5 Stakes, S31). `app/stakes.py` derives one fixed sentence per situation from the score state only: the scorer and the score after the goal on the goal event, the score before it on the event before, and the score at the whistle for half-time and full-time. It covers the opening goal, level, take the lead, extend, pull one back, who leads at the break and who won or drew. It runs after the verifier, in `pipeline.apply_context`, which both orchestrators and the clip tool use; the sentence is appended to the `full` text only and also kept in `Cue.context` (and in the cue sheet), so a page can show it apart from the description ("score context") and a captioning system can use it. If the events disagree about the score, the scorer is unknown, or the state is anything else, there is no context.

**What it is not.** The verifier does not check it and no claim says so: its correctness is the tests of S31 and a short fixed phrase list, in the same way the templates are trusted. It does not explain tactics, form or anything the events do not hold. A goal never says "win"; only full-time does. Nothing in the Foundry prompt, the recorded replies or their keys changed (the replay still covers 30 of 30 windows). The stored clips are still not made, so the browser voice speaks the sentence; the clip list now includes the longer goal and whistle texts (7,150 characters, still 140 sentences).

**Alternatives.** Asking the model for context (new prompt, new recordings, unverifiable meaning). Adding the phrase to the templates and the verifier's vocabulary (rewrites the replay keys and the fallback). A separate cue after the description (a second voice slot and more timing conflicts). Facts beyond the score, such as shots or possession (no source in the events, and invented statistics are what the project avoids).

## D19. A mistyped mode setting is a configuration error, not a bug (2026-10-21)

**Why.** A mistyped `SOUNDPITCH_LLM` raised a bare `ValueError`, so every session request answered a generic `500 internal_error` and the cause was only in the log; `/api/health` echoed whatever the variable held; and a mistyped `SOUNDPITCH_ORCHESTRATOR` echoed its value in a 503.

**Choice** (SPEC §8, S32). `pipeline.llm_mode()` checks the setting against the five supported modes and raises the existing `FoundryNotConfigured`, which the API already answers as `503 llm_not_configured`. The message names the setting and lists the supported modes; it never contains the value typed. `/api/health` answers the same 503: a container with a mistyped mode is not healthy, so the Docker health check and `python -m app.smoke` fail closed instead of reporting `ok`. The `500` path stays for genuinely unexpected errors, still with fixed text and the security headers (S25); its test now triggers it with a failing session builder instead of the mistyped setting.

**Alternatives.** Falling back to `scripted` for an unknown value (silently serves templates when the operator meant `replay` or `foundry`). Echoing the value to help the operator (an environment value is not ours to print). Failing at start-up (the API would not start at all, and the page could not explain why).

## D18 addendum: Italian wording (2026-10-21)

The Italian context sentences use singular verbs with a club name ("Northgate passa in vantaggio", "Vince Northgate") and shorter forms ("Finisce in parità", "Northgate avanti all'intervallo"). The first version used plural verbs to match the older Italian templates; Italian sports prose treats a club name as one subject, and the plural also read awkwardly after a name without an article. The templates were left alone at that point; D20 corrects them. The author, a native speaker, reviewed both registers.

## D20. The Italian templates agree with a club name, and recorded sentences that do not are rejected (2026-10-21)

**Why.** The Italian templates gave a club name the plural verb of its players ("Northgate danno il via, attaccano", "costruiscono", "manovrano", "riconquistano", "recuperano", "avanzano") and put "del" before every name ("Silva del Harbour", wrong before a name that begins with an aspirated h). The context sentences of D18 already used the singular. The model had copied the templates, so the recorded replies repeated the error.

**Choice.** The templates use the singular ("Northgate dà il via, attacca", "costruisce", "manovra", "riconquista", "avanza") and "{p} recupera palla per {team}" instead of "{p} del {team} recupera palla"; the short form of the team-subject turnover is "{team} riconquista." so that "recupera" keeps only a player before it (the first draft let a name stand where the other belongs, and the S19 mutation test caught it). `tests/test_italian.py` states the rule on the templates and on what the replay lets a listener hear. The recorded file is **not edited**: it is the model's text. The verifier now rejects the recorded sentences with the old wording (the words are no longer in the vocabulary), the retry is described by the templates, and the moment is verified at attempt 2. Effect on the 30 demo windows: 14 of the 15 Italian sessions report 2 attempts; every moment is still verified, none falls back, English is unchanged; the replay still covers 30 of 30 requests (its key hashes the system prompt, which did not change). The model's own words remain in goals, shots and every other moment.

**Alternatives.** Leave the plural verbs (grammar errors in a product for listeners, at odds with D18). Edit the recorded replies by hand (falsifies the record). Re-record the Italian windows (restores model wording for those moments; it needs live model calls; the cost would be a few cents, D11 limits apply). Changing the verifier to tolerate the old wording (weakens the check to protect a mistake).

**Re-recording, assessed (done on 2026-10-26, with D34).** 52 of the 81 Italian moments of the demo (64%) are now rejected at attempt 1 and spoken by the templates; none in English. The model's own wording was rare in Italian anyway (11 of 81 cues in the recorded run), so what a listener hears changes little apart from the grammar; what a re-recording would restore is attempt 1 in the Italian reports and those few sentences. `python -m app.foundry_run` has no language filter: it asks for every window in both languages (26 calls, about 54,000 tokens, about USD 0.03 at the list price in the recorded run, with limits raised and a 31 s pause, about 15 minutes), and a model does not repeat itself, so the English recording would change too and would have to be read again with the Italian. The command is in `docs/DEPLOY.md`.

**Not settled.** "nello specchio" for a shot on target is the usual short form of "nello specchio della porta" and was kept. The author, a native speaker, reviewed the Italian.

## D21. Rules, licences and disclosure (2026-10-21)

**Why.** Before going public the project was read against the Official Rules: synthetic data (§4.7), third-party software (§4.3, §4.11), and the use of developer tools (§4).

**Choice.** The rules are summarised in our own words and linked at their source, not copied. Every runtime dependency is under a permissive licence (MIT, BSD, Apache-2.0, MPL-2.0, PSF) and `pip-audit` and `npm audit` report no known vulnerability. The use of an AI coding assistant is stated in the README, since the rules allow developer tools and name GitHub Copilot among the judged technologies.

**Alternatives.** Keeping a copy of the rules in the repository (the text is one click away at its source).

## D22. The pitch names only what exists (2026-10-21)

**Choice.** The pitch names only what runs, and says what is built but not in use.

## D23. Azure credit used in early testing (2026-10-21)

**Why.** To state plainly how the cloud usage was paid for.

**Choice.** About USD 0.05 of the first Foundry tests, on 2026-10-20, was charged against an Azure for Students credit; every recorded reply in the replay file was made on a pay-as-you-go subscription. No grant, sponsorship, contract or licence from Microsoft is involved. The README says so in one sentence.

**Alternatives.** Not mentioning it (a small fact is better stated than found).

## D24. First public release: CI by hand, a public image, one container app, a dev container (2026-10-21)

**Why.** The repository went public and the judges need a way to run the project (rules 4.4, 4.8) until 10 Nov.

**Choice.** (1) CI is started with `workflow_dispatch`, because GitHub started no run for any push or pull request (cause not found, probably a setting on GitHub's side). The first run found a genuine fault that only Linux showed: the settings form's inline `onsubmit`, refused by the page's own content security policy (S25); it was fixed in the markup and a test now asserts that no element carries an inline handler. The tests were not weakened. (2) The `publish` job of the same dispatch pushed the tested commit's image to GHCR; the package is public and an anonymous pull was verified. (3) One Container Apps app in its own group, Consumption only, no logging destination, scale 0 to 1, 0.25 vCPU and 0.5 GiB, the replay image, no secret. (4) A minimal `.devcontainer` for GitHub Codespaces: Python 3.13, Node 22, the CI setup commands, `CI=true` so that Playwright uses its own Chromium; verified by building it locally and running pytest and the end-to-end suite inside.

**Not done.** A cost check of that app (Azure cost data arrives 8 to 48 hours after creation), a browser run of the page against the public address, any Speech clip, the demo video, the submission form.

**Alternatives.** A private package with a registry credential on the app (a secret to hold for no benefit). Azure Container Registry (a second paid service). A prebuilt Playwright image for the dev container (larger, and it would not match the CI setup).

## D25. The hosted demo is taken down (2026-10-21)

**Why.** To stop Azure costs. The resource group held only the demo (the container app and its environment) and nothing depended on it: the image is public on GHCR and the settings are in `docs/DEPLOY.md`.

**Choice.** The resource group was deleted after its contents were listed; the documents say that no hosted demo exists. Deleting stops further hosting charges; it does not erase what accrued.

**Alternatives.** Leaving it up (scale to zero keeps the expected cost near zero). Deleting only the app and keeping the environment (the environment is the item with the unclear `Environment` meters, D17).

## D26. Submission polish pass: test build over hosting (2026-10-22)

**Why.** A review of the repository against the current Official Rules and of the public history, before the submission.

**Choice.** (1) *Rule 4.8 asks for access to a working project "by providing a link to a website, functioning demo, or a test build", free and unrestricted until 10 Nov; it does not say hosted or public.* The README had said "public demo". They now say what the rule says; the public tested image, Codespaces and a clone are the test build, with instructions in the README. A hosted copy stays optional: it costs almost nothing but needs approval, and is the lowest-friction way for a judge to open the project. (2) The player page was fixed where it was wrong or hard to use (sideways scroll at 320 px, a squeezed transcript on phones, an empty half of the page on desktop, a stale session after a failed reload, a replayed clip on resume) and gained one plain sentence in the report.

**Alternatives.** Keeping a hosted copy running for the whole judging window (a standing cost for a path the rules do not require).

## D27. A session lasts until its last cue ends (2026-10-22)

**Why.** An audit that played every window found 49 of 180 session variants (preset x detail x language x calm x speed) with a cue that started after the window had ended, among them the full-time sentence of "The final whistle" at default settings: the whistle is the last event of its window, so its sentence starts at least 300 ms later. The page stopped at the window end, so the sentence was never shown or spoken, while the report and the cue sheet counted it. No test played that window through the page.

**Choice.** `duration_ms` is the preset window, extended to the end of the last cue when a cue runs past it (SPEC §6). Every cue now starts and ends inside the session, so the player runs until it has been spoken; cue sheet, WebVTT and session agree on all 60 variants of preset, detail, language and calm, re-checked after the change. At default settings 12 of the 30 sessions are 2.7 to 4.3 s longer than their window (the final whistle at every detail level and in both languages, Goal 1 at full detail, Goal 2 at standard and full detail); the others are unchanged, among them Goal 1 at standard detail, so its cue times and the facts of the demo plan hold. The one published figure that moved, the share of the window spent speaking, went from 20.0% to 19.7% (`docs/evaluation.md`, regenerated). Tests: a backend test over every preset, detail, language and rate, a browser test at a slow clock (a fast clock overshoots the window end and hides the fault), and a literal 250 ms gap test, because the other gap tests compare with the constant they test.

**Alternatives.** Dropping the late cue (loses the full-time announcement, the point of that window). Stretching the final-whistle preset by a few seconds (works for that window only and moves its event list). Changing only the page to wait for the last cue (leaves the cue sheet saying a cue ends after the session).

## D28. Commit messages carry no tool links (2026-10-25)

**Choice.** `.claude/settings.json` turns off the session links that the coding assistant adds to commit messages.

## D29. Player focus and match statistics, written by code (2026-10-26)

**Why.** The challenge's *Interpret* and *Personalize* stages (rules 4.1 (b), (e) and (ii)) ask for statistics and for favourite-player or favourite-club modes; the project had neither, although T09 was specified. Both fit without touching the verifier, the prompt or the recorded replies.

**Choice.** (1) *Match statistics* (SPEC §18, S33) are counted by code in `stats.py` and never spoken, so nothing a model writes can carry a number the events do not hold. Possession is the share of passes, the usual broadcast estimate, because the events carry no ball-in-play time; a pass is completed when the next event with a team, a foul aside, is the passer's side; lengths are measured on a 105 x 68 m pitch from the event before the pass, because an event's position is where the ball ends up. The counts run from kick-off, so a window shows the match so far, and `Session.stats` carries one point before the window and one after each of its events, so the page can follow the clock without a second request. (2) *Player focus* (SPEC §17, S18) is T09 as written: the player's moments go up one priority, up to 2, before the detail filter, and their ball sounds are 1.5 times louder. A focused session asks the describer about a different set of moments, which has no recorded reply, so in replay mode the templates describe it, verified, and the trace says "no recorded reply: templates"; recording replies for every player would cost model calls for little gain. (3) The same pass fixed what an accessibility review found in the page: the clock now runs on a timer (a background tab pauses animation frames, which stopped the commentary), Play is disabled while a session reloads, the screen-reader output is suggested under the Voice control, and the control borders reach 3:1.

**Alternatives.** Possession by time between events (the gaps are random, 3 to 9 s, so time would mostly measure the generator). Speaking the statistics at half-time and full-time (a stats sentence would need its own verified phrases; left for later). A spoken focus sentence ("Marsh on the ball"), which would change the vocabulary and every recorded reply key.

## D30. Commit metadata normalised (2026-10-26)

**Choice.** Commit metadata was normalised once: one author address and no tool trailers; trees and dates are unchanged. `.claude/settings.json` turns the assistant's attribution off. The AI assistance is disclosed in the README.

## D31. The judges' image runs the Agent Framework workflow (2026-10-26)

**Why.** The workflow (D13) was built and tested, but the image ran the plain pipeline, so the orchestration that the project describes was not the one it served.

**Choice.** `backend/requirements-workflow.txt` holds the one package the workflow needs, `agent-framework-core` 1.22.0 (its own dependencies are small: msgspec, opentelemetry-api, pyyaml, regex, python-dotenv), and `requirements-agents.txt` includes it, so the pin lives in one place. The image installs it and sets `SOUNDPITCH_ORCHESTRATOR=workflow`; the Foundry SDK and Azure identity packages stay out of it. With only that package installed, every preset builds through the five executors with the recorded replies and the same cues as the plain pipeline (S13, run with the agent packages: 38 tests). The page names the executor beside each pipeline step. The CI `docker` job smoke-tests the image, so it now checks the workflow in the image too.

**Alternatives.** Installing all of `requirements-agents.txt` in the image (the Foundry SDK, OpenAI and Azure identity add size and code the judges' path never calls). Keeping `plain` in the image and the workflow as an option.

## D32. The match as MCP tools, in the judges' image (2026-10-26)

**Why.** An AI agent, such as GitHub Copilot in agent mode, should be able to use the match the way the page does, and only through verified output. T08 was specified and not built.

**Choice.** `backend/app/mcp_server.py` serves read-only tools over stdio with the official MCP Python SDK: `list_presets`, `get_match`, `get_moments`, `get_commentary` and `get_stats` (SPEC §16). Every tool answers from the same pipeline, orchestrator and describer as the HTTP API, so an agent cannot get a sentence the verifier did not accept or a number code did not count. `mcp` 1.30.0 (FastMCP, 7 Sep 2026) is pinned in `requirements-mcp.txt`, which the image and the development requirements include; it installs beside the core pins and the Agent Framework packages with no conflict (`pip check`). The 2.x line (2.3.0, 2 Oct 2026) renames the server class and negotiates the protocol of 2026-07-28 by default; 1.30.0 was preferred for the clients in use today, and it negotiated `2025-11-25` over stdio in a local check. The image serves it with `docker run -i --rm <image> python -m app.mcp_server`, and `.vscode/mcp.json` connects VS Code's GitHub Copilot agent mode to that command. Tests: an in-memory MCP client session (S17). Checked over a real stdio transport with the SDK's own client.

**Alternatives.** An HTTP transport mounted in the FastAPI app (a second public surface on a hosted copy, with its own origin and authentication questions). Letting the describer call `get_moments` instead of receiving the facts in its prompt (T08 step 4; it would change the recorded reply keys and is left for later). The 2.x SDK.

## D33. A match recap written by code, and an MCP prompt (2026-10-26)

**Why.** The challenge asks for automated match recaps and for explaining why moments matter (rules 4.1 (iii), (iv)). The statistics of D29 already hold the pressure before each goal; nothing said it.

**Choice.** `recap.py` builds the summary of the match up to the end of a window from fixed English and Italian phrases: the score, each goal with its assist, and a pressure clause when the scoring side had at least 60% of the passes in the five minutes before (or at most 40%: against the run of play). No model writes it, so it needs no verifier and no recorded reply. `Session.recap` carries it; the page shows it and reads it aloud when the clip ends, not before. The MCP server adds `get_events` (the ingested events), `get_recap` and a prompt, `match_report`, that asks the client's model to write a report from those tools alone.

**Alternatives.** A model-written recap (live calls, a cost, and a text the verifier was not built for). A recap on every goal cue (longer cues would move the timing of the recorded demo).

## D34. A second agent, the Analyst, checked line by line (2026-10-26)

**Why.** One model call site made the pipeline a single agent with code around it. The challenge asks to explain why moments matter, and a studio analysis is where a model adds something a template cannot; the project's rule still holds: no model word reaches a listener unchecked.

**Choice.** The Analyst is a Microsoft Agent Framework `Agent` on Foundry whose tools are the SoundPitch MCP server (SPEC §20). It writes three or four points, each citing one source: a recap line or the statistics of a minute. `analysis.check_point` rejects a point whose names or numbers are not in the line it cites, so an attribution swapped between lines cannot pass; one retry carries the issues; with no valid point, code writes the points and the status says `fallback`. Cues are context, not sources, because they change with the detail level, the language and the focus, while one recorded analysis must serve every profile of a window. The live agent runs only in `app.analyst_run`, behind the ledger (each run reserves three rounds under the 12,000-token cap); the judges' image replays its recorded replies and checks them on every session. In the workflow the Analyst and the AnalysisChecker are two executors with their own retry edge, so the graph now holds two agents and two code checkers.

**What the check does not cover.** The judgement around the facts ("pressed hard") and, inside a statistics line that names both teams, which team a number belongs to.

**Alternatives.** Letting the Analyst cite cues (a recorded reply would not match other profiles). Free prose with a whole-text check (an attribution swap would pass). A model-written recap instead of the code one (D33).

## D35. The neural voice is stored, and is the default (2026-10-26)

**Why.** The browser's own voice differs from one system to the next and is often robotic; a listener and a judge should hear the same, good voice, and the judges' path must still need no key and no network.

**Choice.** `clips_build --generate` made one clip for each of the 200 sentences the demo can say, cues, recap lines and analysis points, with `en-GB-RyanNeural` and `it-IT-DiegoNeural` on the pay-as-you-go AI Services resource in Italy North (13,310 characters, about USD 0.20). The image serves them from `backend/app/audio/` through `/api/tts`, which still speaks only text the server issued (now also the recap lines and the analysis points). Where a language has clips the page picks the neural voice by default; the summary is read clip by clip. `SOUNDPITCH_CLIPS_DIR` points the tests that check the live path, and the end-to-end servers, at an empty folder.

**Alternatives.** A live Speech key in a hosted copy (a spending risk that only the pricing tier caps, D14). Keeping the browser voice as the default (the better voice would go unheard by most judges).

## D36. The demo is online again, for the judging window (2026-10-26)

**Why.** A judge can click a link more easily than run `docker run`, and the hosting shows the Azure deployment the project describes.

**Choice.** The tested image of `021fdfb` runs on Azure Container Apps as before (D17, D24): its own resource group in Italy North on the pay-as-you-go subscription, Consumption only, no logs destination, 0.25 vCPU and 0.5 GiB, zero to one replica, `SOUNDPITCH_TRUST_PROXY=1`. Smoke, health, stored voice clips, the workflow trace with both agents, the content security policy and the page in a browser were checked on its address (https://soundpitch.icywave-efb40405.italynorth.azurecontainerapps.io). The first request after a quiet spell waits for a replica, about 18 seconds. The cost is checked the next day; the group is deleted after judging, or at once if an unexpected meter appears (D25).

**Alternatives.** One replica always on (no cold start, a few euros more). The image alone (D26).

