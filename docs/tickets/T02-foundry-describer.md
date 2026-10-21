# T02b. Foundry describer

**Depends on:** [T02a](T02a-grounded-verifier.md) (done)  **Acceptance:** S11, S12  **Spec:** §5, §11  **Judging:** criteria 1 and 2, Best Use of Microsoft Foundry

## Goal

`SOUNDPITCH_LLM=foundry` writes the descriptions with a model on Microsoft Foundry, and everything it says still passes the grounding verifier of §5.

## Carried over from T02a

- The prompt lists, per moment, the canonical phrases (`describer.facts`), the vocabulary of its template key (`verifier.vocabulary`) and the places a name or a phrase may stand (`verifier.position_contexts`: the words before and after the player, the team and each canonical phrase). The reply is verified whatever way the text was produced; refs come from `facts`, never from the model.
- S12 also reports the first-attempt pass rate per language and the words the verifier rejected most. Review them: a word joins the vocabulary only if it cannot change a fact. If real output is rejected so often that the model adds little, decide with data whether to grow the vocabulary or accept more fallback; do not loosen the checks.
- The cost guard may also cache verified descriptions by (preset, detail, lang), because rate, ball sound and calm mode do not change the words. Decide this when the dependencies are checked (spike).

## Status

| Part | State |
|---|---|
| Context7 and package research, isolated spike (Python 3.13) | done; choice and versions in D10 |
| S11, the describer against a fake client (`backend/tests/test_foundry.py`) | done |
| The adapter against the real SDK types, network stubbed (`backend/tests/test_foundry_sdk.py`) | done in the Python 3.13 environment with `requirements-agents.txt`; skipped in the core environment |
| `backend/app/foundry.py`, wiring in `pipeline.py` and `main.py`, `requirements-agents.txt` | done |
| `python -m app.foundry_run` and its tests | done |
| **S12, a real request against a Foundry deployment** | **done 2026-10-20**: `docs/evidence/foundry-run.md` (26 calls, 81 of 81 moments verified at attempt 1 in each language, median 3.31 s, p95 4.52 s). The model copies the templates in 98.8% (en) and 84.0% (it) of cues; see D10. The cost hardening of 2026-10-20 (D11, S21) came after this run |

## Independent review of the failure paths

A separate reviewer ran the integration against hostile replies, concurrency, outages and the cap. Defects confirmed, each now closed and covered by a test in `test_foundry.py`:

| Finding | Fix |
|---|---|
| A fenced reply made of whitespace froze the whole process for seconds to minutes (regex backtracking) | The fence is stripped with string operations; a reply over 20,000 characters is refused before it is cached |
| An outage or an exhausted cap was remembered by the API's session cache until restart | A session is kept only if no model call failed and the budget was not exhausted |
| 15 identical concurrent requests made 15 calls | Single flight per (window, attempt) |
| Hung calls filled the pool and each queued attempt still spent the cap | At most 2 calls in flight; a busy pool fails at once and reserves nothing |
| An unparsable reply was pinned for the life of the process | Only parsable replies are cached |
| `RateLimiter` had no lock | Locked, with a threaded test (it now serves only `/api/tts`; the model is limited by the ledger, D11) |

Known and left: if one chunk of several fails, the paid chunks are asked again at the next attempt (windows have at most 12 moments today, one chunk); an authentication failure spends a cap slot per attempt and the trace shows only the exception type.

## Azure resources and limits (2026-10-20)

Foundry account `<account>` and project `<project>` on the pay-as-you-go subscription (Italy North), one deployment, `soundpitch-mini` (`gpt-4.1-mini`, GlobalStandard, capacity 8 = 8,000 tokens per minute after the reduction of 2026-10-20), a budget of 5 EUR a month that only alerts. App limits (D11, S21): 1,000 output tokens a request, 2 calls a minute, 20 a day, 120,000 tokens a day, 2.00 EUR of estimated spend a month, kept in a SQLite file. Undo and details: D10, D11.

## What the live run did not settle

The three points below were open before the run and are now answered: the deployment accepted `response_format` and `instructions` (replies were typed JSON), `DefaultAzureCredential` worked through `az login`, and a window costs one call. Still open: a managed identity in Azure (T06), and the value of the model over the templates (1.2% and 16.0% own wording).

## What was not proved without the live run (before 2026-10-20)

- That the deployment accepts `response_format` (structured output) and the `instructions` option for the chosen model. If it does not, the adapter returns the model's text and the describer parses it, so the pipeline still works; only the first-attempt rate suffers.
- `DefaultAzureCredential` on this machine and, later, a managed identity in Azure (T06).
- The real first-attempt pass rate, the rejection reasons, the latency and the cost of a window.

## Steps

1. Create or reuse a Foundry project and a model deployment; `az login`; copy `backend/.env.example` to `backend/.env` and set `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL` (never commit them).
2. `cd backend; .\.venv\Scripts\python.exe -m pip install -r requirements-agents.txt` (Python 3.13 recommended; a separate environment keeps the core one clean).
3. `.\.venv\Scripts\python.exe -m app.foundry_run --write ..\docs\evidence\foundry-run.md`: about 30 windows, at most 90 calls. The ledger limits apply to it too: raise them on purpose in the shell (`SOUNDPITCH_LLM_CALLS_PER_DAY`, `SOUNDPITCH_LLM_TOKENS_PER_DAY`) and use `--pause-seconds 30`. Do not run it casually: it spends money.
4. Read the report. Review the words the verifier rejected most, in `SPEC.md` §5 terms: a word joins the vocabulary only if it cannot change a fact or a relation. Do not loosen a check.
5. Decide with the numbers whether the model adds enough over the templates, or whether the templates should be richer.

## Verification

Core environment (no SDK):

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q; cd ..
cd backend; .\.venv\Scripts\python.exe -m ruff check .; cd ..
npm run e2e
```

With the SDK (Python 3.13, `requirements-agents.txt`): also `python -m pytest -q tests/test_foundry_sdk.py`.

## Out of scope

Streaming replies, fine-tuning, more than one deployment, languages beyond `en` and `it`.
