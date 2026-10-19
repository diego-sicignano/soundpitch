# T02. Foundry describer

**Depends on:** none  **Acceptance:** S11, S12  **Spec:** §5, §11  **Judging:** criteria 1 and 2, Best Use of Microsoft Foundry

## Goal

`SOUNDPITCH_LLM=foundry` writes the descriptions with a model on Microsoft Foundry, and everything it says still passes the verifier.

## Steps

1. **Look up the client with Context7 before writing code** (CLAUDE.md): the Foundry client for Python (Microsoft Agent Framework's `FoundryChatClient`, or the Azure AI Projects / OpenAI-compatible client) and its JSON output option. Check the API against the version you install; the docs may be ahead of the package. Record the choice in `docs/DECISIONS.md`.
2. **Test first (S11)** in `backend/tests/test_foundry.py` with a fake client that returns canned replies: correct JSON; wrong names then correct; unparsable JSON; an exception; over the call cap; and a check that the prompt holds only the facts of §11.
3. Implement `backend/app/foundry.py` (`FoundryDescriber`, the `Describer` protocol of `describer.py`): prompt builder with the style rules of §5, batches of at most 40 moments, JSON parsed into `Description`, 20 s timeout, `SOUNDPITCH_LLM_CALLS_PER_MINUTE` cap with the template describer as the answer when over it.
4. Wire it in `describer_from_env` in `pipeline.py`; replace the `NotImplementedError`; update its test.
5. Put the Foundry dependencies in `backend/requirements-agents.txt` (optional, not needed offline); keep `requirements.txt` unchanged.
6. **S12 (manual):** create or reuse a Foundry project and a model deployment, `az login`, set `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL` in `backend/.env`, run every preset at every detail level, and add a dated table to `docs/evaluation.md`: first-attempt pass rate, retries, fallbacks, median latency, model name. Never commit keys.

## Verification

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q; cd ..
cd backend; .\.venv\Scripts\python.exe -m ruff check .; cd ..
npm run e2e
```

## Out of scope

Streaming replies, fine-tuning, more than one deployment, languages beyond `en` and `it`.
