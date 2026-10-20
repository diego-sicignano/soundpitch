# T11. Record the replay file

**Status: done (2026-10-20).** Recorded under the ledger: 26 replies, 30 of 30 requests, about 0.028 USD at list price (provider tokens). A pacing bug in the tool cost one extra invocation and was fixed with tests. Results, and the open point about one Italian sentence, are in `docs/evidence/foundry-run.md`.

**Depends on:** T02b, the prompt and templates frozen, **the owner's approval** (it spends model calls)  **Acceptance:** S24  **Spec:** §11  **Decision:** D12

## Goal

`backend/app/replay_data/foundry_replies.json` holds a Foundry reply for every request of the demo (5 windows x 3 detail levels x 2 languages, first attempt), so the judges' path speaks words a model wrote, verified again on every request, with no live call.

## Steps

1. Freeze the prompt, the templates and the vocabulary: any change after this changes the keys and invalidates the file.
2. Ask the owner for approval: about 30 to 60 calls of the `soundpitch-mini` deployment, a few cents at the ledger's rate, with the limits raised on purpose for this run (D11).
3. Run the procedure of `docs/DEPLOY.md` ("Recording the replay file") with a throw-away ledger file.
4. `python -m app.replay_export --check` exits 0; `pytest` passes (the test that was skipped now runs); read the file by eye.
5. Regenerate `docs/evidence/foundry-run.md` (written by the same run, now under the ledger) and update its comment in the README and `docs/evidence/README.md`.
6. Commit both files.

## Verification

`python -m app.replay_export --check` reports every request covered; `pytest -q tests/test_replay.py` passes with the committed file; `python -m app.smoke` against a server with `SOUNDPITCH_LLM=replay` exits 0 and `/api/health` reports the number of replies.

## Out of scope

Recording retries (a request with feedback is described by the templates); recording other models.
