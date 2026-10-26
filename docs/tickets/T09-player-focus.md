# T09. Player focus

**Status: done (2026-10-26, D29).**  **Depends on:** none  **Acceptance:** S18  **Spec:** §17  **Rules:** 4.1 (e): "player focused mode"

## Goal

A listener can follow one player: that player's moments get described more often and their ball sounds are louder.

## Steps

1. Add `focus` and `focus_team` to `Profile` in `contracts.py` and to `CONTEXT.md`.
2. **Test first (S18)** in `backend/tests/test_focus.py`: priority raised by one up to 2 for moments involving the player, others unchanged, earcon gain x1.5 capped at 1.0, no focus gives identical output, an invalid shirt gives `422`.
3. Implement in `moments.py` and `render.py`; add the query parameters `focus` and `focus_team` to the API.
4. Add a labelled select to the page (`data-testid="focus"`), an e2e test, and an axe re-check (S9).

## Out of scope

Stats about the player, following several players at once.
