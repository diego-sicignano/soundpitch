# Evidence

Small files that record the live and manual checks (SPEC S12 and S14) and the cost limits (S21). Today that is the output of the real model runs and the cost-limit record; **the short Azure AI Speech clip and the screenshot of the page using it that S14 asks for do not exist yet** (Speech has never been called). Keep each file small, and never include keys, endpoints with secrets, or personal data.

- `foundry-run.md` is written by `python -m app.foundry_run`. It holds two runs of 2026-10-20: run 1 came before the cost ledger (limits raised for that run, 6,000 output tokens a call), run 2 was made under the ledger with limits raised on purpose and produced the replay file (T11). Neither can be reproduced under the shipped limits (26 calls against 20 a day) without raising them on purpose. It is one deployment on one day.
- `cost-safety.md` records the cost limits of the live model (S21) and what they do not cover.
- What can be reproduced offline, with no model: `python -m app.evaluate --seeds 20` (regenerates `docs/evaluation.md` identically), the whole test suite, and the replay of a recorded run (`python -m app.replay_export --check`).
