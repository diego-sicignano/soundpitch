# SoundPitch

Audio-first match companion for blind and low-vision fans, built for the Microsoft x Premier League "Inside the Game" hackathon (deadline 27 Oct 2026, 23:59 Pacific). Python 3.13 (FastAPI, Pydantic v2) in `backend/`, plain HTML/CSS/JS in `frontend/`, Playwright in `e2e/`. Windows 11, Windows PowerShell 5.1.

This repository is a clean, separate project. Do not copy code, docs or history from any other project into it.

## Spec-driven development

The spec is the authority; code follows it.

- [`SPEC.md`](SPEC.md): behaviour, pinned numbers, UI test ids, acceptance rows `S1` to `S10`.
- [`ROADMAP.md`](ROADMAP.md): what is done and what is left before the deadline.
- [`docs/hackathon/`](docs/hackathon/): the official rules (verbatim), our summary and the submission checklist. When a choice depends on a rule, cite the section.

Rules:

1. A behaviour or contract change edits `SPEC.md` first, then `backend/app/contracts.py`, then code.
2. Test first: write the failing test for an acceptance row, make it pass, refactor.
3. **Only code decides what is true and when it is said.** A model may choose words; the verifier checks every name, number and attribution against the events. Never let model output reach a user unverified.
4. Keep the template describer working offline. It is also the fallback, so it must always pass the verifier.
5. Accessibility is the product: semantic HTML, labelled controls, keyboard operation, visible focus, `prefers-reduced-motion`, axe-core clean (S9). Do not add a feature that breaks these.
6. Synthetic data only. No real players, clubs, logos or footage (rules 4.7). Fictional teams: Northgate Red, Harbour Blue.
7. Never commit secrets. Keys live in `backend/.env` (git-ignored); `backend/.env.example` stays empty.
8. Mark roadmap items done in the same commit that finishes them.

## Library docs

Look up any library, framework, SDK or API through Context7 before writing against it (FastAPI, Pydantic, Playwright, Microsoft Agent Framework, Microsoft Foundry, Azure AI Speech):

```powershell
npx ctx7@latest library "<official name>" "<what to look up>"
npx ctx7@latest docs <libraryId> "<one concept>"
```

Quota error: report it and suggest `npx ctx7@latest login` or `CONTEXT7_API_KEY`.

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

A task is done when every command above exits 0 and the output is read, not assumed.

## Run

```powershell
cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Open <http://localhost:8000>. `SOUNDPITCH_LLM` selects the describer: `scripted` (default, offline), `bad_then_good`, `always_bad` (test scenarios), `foundry` (planned).
