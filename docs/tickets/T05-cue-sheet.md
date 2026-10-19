# T05. Cue sheet and published JSON Schema

**Depends on:** none  **Acceptance:** S15  **Spec:** §13  **Rules:** 4.1 (e): "clean outputs, timed and machine-readable"

## Goal

A versioned, machine-readable cue sheet that a graphics or captioning system could consume, with a published JSON Schema.

## Steps

1. Add `CueSheet` and `CueSheetItem` to `backend/app/contracts.py` as specified in §13; list them in `CONTEXT.md`.
2. **Test first (S15)** in `backend/tests/test_cuesheet.py`: every preset and detail level validates against the committed schema (add `jsonschema` to `requirements-dev.txt`); the committed schema equals the generated one; items sorted by `at_ms`; descriptions never overlap; a caption has the timing of its description.
3. Implement `backend/app/cuesheet.py` (built from a `Session`, no new logic), the two endpoints in `main.py`, and `python -m app.export_schema` that writes `docs/contracts/cuesheet.v1.schema.json`.
4. Add the endpoints to the API table in `README.md`.

## Verification

Same commands as T02.

## Out of scope

Pushing cue sheets over a socket, other export formats (EBU-TT, IMSC).
