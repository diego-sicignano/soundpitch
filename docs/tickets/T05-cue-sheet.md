# T05. Cue sheet and JSON Schema

**Status: done (2026-10-20).**  **Depends on:** none  **Acceptance:** S15  **Spec:** §13  **Decision:** D15  **Judging:** criterion 1 (clean, machine-readable output is welcome in the Render stage)

## Goal

A versioned, schema-checked JSON export of a session that a graphics or captioning system can consume.

## Done

- `CueSheet`, three item types and the schema in `backend/app/contracts.py`; the builder and `python -m app.cuesheet --write` in `backend/app/cuesheet.py`; `GET /api/cuesheet` and `GET /api/cuesheet.schema.json` in `main.py`.
- The schema is committed as `docs/contracts/cuesheet.v1.schema.json`; `backend/tests/test_cuesheet.py` fails if it differs from the generated one, and checks all 30 combinations of preset, detail and language against their session (order, unique ids, no overlap, caption equals description, ball sounds equal earcons).

## Verification

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q tests/test_cuesheet.py
```

## Out of scope

A second validator library, a streaming (live) cue feed, other output formats than JSON and WebVTT.
