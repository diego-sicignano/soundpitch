# T03. Microsoft Agent Framework workflow

**Status: done (2026-10-20).**  **Depends on:** T02  **Acceptance:** S13  **Spec:** §12  **Decision:** D13

## Goal

The describe, verify, retry, fallback and timing flow runs as an Agent Framework workflow with distinct executors and a conditional retry edge, and gives the same results as the plain pipeline.

## Done

- The API of the pinned version (`agent-framework-core` 1.22.0) was read from the installed package and the documentation through Context7, then prototyped; it is recorded in D13, including the finding that edge conditions are evaluated when a message is delivered, which is why the messages are immutable.
- `backend/app/pipeline.py` was split into `describe_step`, `verify_step`, `fallback_step` and `assemble_session`, which the plain pipeline and the workflow both call. `TraceStep.executor` names the executor of each step.
- `backend/app/workflow.py`; `SOUNDPITCH_ORCHESTRATOR=workflow` selects it in `main.py`; `plain` stays the default.
- `backend/tests/test_workflow.py` (S13). With the packages installed (Python 3.13): the workflow equals the plain pipeline for the three scenarios, languages, presets and a recorded-reply store; the trace names the executors in order; a describer that raises once is retried; a template fallback that does not verify stops the workflow; concurrent requests are correct; the API serves it. Without the packages the tests that need them are skipped, and the missing-package message and the unknown-orchestrator message are tested everywhere. CI has a `sdk` job for the skipped tests.

## Verification

```powershell
cd backend; .\.venv\Scripts\python.exe -m pip install -r requirements-agents.txt   # Python 3.13
cd backend; .\.venv\Scripts\python.exe -m pytest -q tests/test_workflow.py
```

## Out of scope

Handoff builders, group chat, running agents in separate processes, a model that chooses tools.
