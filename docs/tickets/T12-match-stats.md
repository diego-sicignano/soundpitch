# T12. Match statistics

**Status: done (2026-10-26).**  **Depends on:** none  **Acceptance:** S33  **Spec:** §18  **Decision:** D29  **Rules:** 4.1 (b) Interpret, (ii) pass quality

## Goal

The listener who wants numbers gets the match statistics an analyst expects, counted by code from the events, beside the commentary.

## Done

- `TeamStats` and `StatsPoint` in `backend/app/contracts.py`; `backend/app/stats.py` counts possession (share of passes), passes completed, pass accuracy, average pass length, shots, shots on target and balls won; `Session.stats` carries the points of the window.
- The page shows a "Match stats" table (`data-testid="stats"`) that follows the clock.
- Tests: `backend/tests/test_stats.py` (a hand-built sequence and every preset), an end-to-end test, axe.

## Verification

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q tests/test_stats.py; cd ..
npm run e2e
```

## Out of scope

Speaking the statistics; statistics of one player.
