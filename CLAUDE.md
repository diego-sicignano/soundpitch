# SoundPitch

Audio-first match companion for blind and low-vision fans, built for the Microsoft x Premier League "Inside the Game" hackathon (deadline 27 Oct 2026, 23:59 Pacific). Python 3.13 (FastAPI, Pydantic v2) in `backend/`, plain HTML/CSS/JS in `frontend/`, Playwright in `e2e/`. Windows 11, Windows PowerShell 5.1.

## Spec-driven development

The spec is the authority; code follows it.

- [`SPEC.md`](SPEC.md): behaviour, pinned numbers, UI test ids, acceptance rows `S1` to `S31`.
- [`CONTEXT.md`](CONTEXT.md): glossary and the map of the contracts. `backend/app/contracts.py` is the single source of the field-level contracts.
- [`ROADMAP.md`](ROADMAP.md) and [`docs/tickets/`](docs/tickets/): the work items `T01` to `T11`, each citing the acceptance rows it satisfies.
- [`docs/DECISIONS.md`](docs/DECISIONS.md): why things are the way they are.
- [`docs/hackathon/`](docs/hackathon/): the official rules (verbatim), our summary and the submission checklist. When a choice depends on a rule, cite the section.

Rules:

1. Pick one ticket. Its acceptance rows are the definition of done. Read its spec sections first.
2. A behaviour or contract change edits `SPEC.md` first, then `backend/app/contracts.py` (and `CONTEXT.md`), then the tests, then the code.
3. Test first: write the failing test for an acceptance row, make it pass, refactor.
4. **Only code decides what is true and when it is said.** A model may choose words; the verifier checks every name, number and attribution against the events. Never let model output reach a user unverified.
5. Keep the template describer working offline. It is also the fallback, so it must always pass the verifier.
6. Accessibility is the product: semantic HTML, labelled controls, keyboard operation, visible focus, `prefers-reduced-motion`, axe-core clean (S9). Do not add a feature that breaks these.
7. Synthetic data only. No real players, clubs, logos or footage (rules 4.7). Fictional teams: Northgate Red, Harbour Blue.
8. Never commit secrets. Keys live in `backend/.env` (git-ignored); `backend/.env.example` stays empty. Never put personal data in the repository.
9. Record a choice that someone could undo in `docs/DECISIONS.md`.
10. Mark the ticket done in `ROADMAP.md` in the same commit that finishes it.

## Library docs

Look up any library, framework, SDK or API through Context7 before writing against it (FastAPI, Pydantic, Playwright, Microsoft Agent Framework, Microsoft Foundry, Azure AI Speech, MCP):

```powershell
npx ctx7@latest library "<official name>" "<what to look up>"
npx ctx7@latest docs <libraryId> "<one concept>"
```

Check what the docs say against the version you actually install. Quota error: report it and suggest `npx ctx7@latest login` or `CONTEXT7_API_KEY`.

## Verification (PowerShell 5.1)

Chain with `;` and test `$LASTEXITCODE`; `&&` is unavailable in 5.1.

```powershell
# one-time setup
cd backend; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt; cd ..
npm install

# backend
cd backend; .\.venv\Scripts\python.exe -m pytest -q; cd ..
cd backend; .\.venv\Scripts\python.exe -m ruff check .; cd ..

# end to end and accessibility (starts its own servers on 8100 to 8102)
npm run e2e

# evaluation figures
cd backend; .\.venv\Scripts\python.exe -m app.evaluate --seeds 20 --write ..\docs\evaluation.md; cd ..
```

The tests that need the optional Agent Framework packages (`test_workflow.py`, `test_foundry_sdk.py`) are skipped in that environment. Run them in a Python 3.13 environment that also has `backend/requirements-agents.txt` (a throw-away venv is fine); CI has an `sdk` job for it.

A task is done when every command above exits 0 and the output is read, not assumed.

## Approval gates

Ask the owner before anything that spends money or is hard to undo: a live model call or evaluation run (`foundry_run`, replay recording), creating or changing Azure resources, a Speech resource, a deployment, a commit, a history rewrite, a push, changing a repository's visibility. Regression tests never use a real model: they use a fake client.

## Session hygiene

One ticket per session; `/clear` between tickets. When compacting, keep the list of modified files, the active ticket and the verification commands above. Read a file again before editing it if it may have changed.

## Run

Preview servers come from `.claude/launch.json`: `soundpitch` (port 8000, `SOUNDPITCH_LLM=scripted`). By hand:

```powershell
cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Open <http://localhost:8000>. `SOUNDPITCH_LLM` selects the describer: `scripted` (default, offline), `bad_then_good`, `always_bad` (test scenarios), `replay` (recorded Foundry replies, what the judges' image runs), `foundry` (a live model, behind the cost ledger). `SOUNDPITCH_ORCHESTRATOR=workflow` runs the pipeline as an Agent Framework graph. `python -m app.smoke <url>` checks a running server.
