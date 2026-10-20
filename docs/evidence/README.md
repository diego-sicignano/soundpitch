# Evidence

Small files that prove a manual acceptance row (SPEC S12, S14 and S21): a short mp3 from Azure AI Speech, a screenshot of the page using it, and the output of a real model run. Keep each file small, and never include keys, endpoints with secrets, or personal data.

- `foundry-run.md` is written by `python -m app.foundry_run`. **The committed one is from 2026-10-20, before the cost ledger existed**: it used limits raised for that run and 6,000 output tokens a call, and it cannot be reproduced under the shipped limits (26 calls against 20 a day) without raising them on purpose. It was one run of one deployment. Recording the replay file (T11) regenerates it under the ledger.
- `cost-safety.md` records the cost limits of the live model (S21) and what they do not cover.
- What can be reproduced offline, with no model: `python -m app.evaluate --seeds 20` (regenerates `docs/evaluation.md` identically), the whole test suite, and the replay of a recorded run (`python -m app.replay_export --check`).
