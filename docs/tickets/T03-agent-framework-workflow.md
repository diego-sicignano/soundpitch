# T03. Microsoft Agent Framework workflow

**Depends on:** T02  **Acceptance:** S13  **Spec:** §12  **Judging:** criteria 1 and 2, Best Multi-Agent System

## Goal

The describe, verify, retry, fallback and timing flow runs as an Agent Framework workflow with distinct executors, shared state and a conditional retry edge, and gives the same results as the plain pipeline.

## Steps

1. **Context7 first:** Microsoft Agent Framework for Python: `WorkflowBuilder`, `AgentExecutor`, `add_edge` with `condition`, running a workflow and reading events. Check against the installed version.
2. **Test first (S13)** in `backend/tests/test_workflow.py`: for `scripted`, `bad_then_good` and `always_bad` the workflow returns the same cues, statuses and report as `build_session`; the trace names the executors; a describer that raises once is retried. Skip the file with a clear reason when the optional package is missing.
3. Implement `backend/app/workflow.py` with the executors of §12, reusing `detect_moments`, the `Verifier`, `TemplateDescriber` and `plan`. Do not duplicate their logic.
4. Select it with `SOUNDPITCH_ORCHESTRATOR=workflow` in `main.py`; `plain` stays the default.
5. Add the package to `backend/requirements-agents.txt`. Update the diagram and the table in `README.md`.

## Verification

Same commands as T02, plus `pytest` with the agents requirements installed.

## Out of scope

Handoff builders, group chat, running agents in separate processes.
