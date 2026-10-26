# T02a. Grounded verifier

**Depends on:** none  **Acceptance:** S3 (extended), S19, S20  **Spec:** §5  **Decision:** D9

## Goal

Before a model writes any commentary, the gate that decides what reaches a listener checks that every fact and word in a description comes from the moment's own facts. No Azure or Foundry credential is needed.

## What was done

1. SPEC §5 states the contract and its limits (what is proved, what is not); S19 and S20 added.
2. `describer.facts(moment, ctx)` returns the template key, the values a sentence may use and the refs; `render` uses it, and the verifier derives its expectations from the same object.
3. `Verifier.check` additionally rejects: a wrong `moment_id` or `lang`; refs that are not exactly the derived ones; text outside canonical phrases that uses a word that is not the moment's player or team, or in the vocabulary of the moment's template key (articles and "and" are shared); symbols, emoji and control characters; text without an outcome word of its kind; text over 400 characters; a missing required fact. `describer.facts` offers a sentence only the team, player and lane its refs carry. A check that raises counts as a rejection, and a template fallback that does not verify stops the session (no `assert`).
4. Two templates changed to fit the contract (the assist is a canonical clause; "wide of the goal" lost "goal").
5. `backend/tests/test_grounding.py`: generated adversarial mutations (S19), cross-moment text, a lying describer and a crashing check through the whole pipeline, template variants, random conforming sentences and spelling variants (S20), hand-written corpora through the pipeline, a policy test that shared words stay neutral, and a test that outcome words belong to one kind of event.
6. `app.evaluate` (with `app.corpora`) reports false acceptance, false rejection and fallback separately, with denominators, in `docs/evaluation.md`.
7. An adversarial review by a separate AI review agent that attacked the verifier and the pipeline (findings below).

## Verification

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q; cd ..
cd backend; .\.venv\Scripts\python.exe -m ruff check .; cd ..
npm run e2e
cd backend; .\.venv\Scripts\python.exe -m app.evaluate --seeds 20 --write ..\docs\evaluation.md; cd ..
```

## Known limits (carried to T02b)

- The verifier proves where facts and words come from. It does not prove that prose built from allowed words means what it should (SPEC §5).
- Natural wording written without the vocabulary is mostly rejected (`docs/evaluation.md`). T02b must put the vocabulary and the canonical phrases in the prompt, then review the rejected words from real model output; a word may join the vocabulary only if it cannot change a fact.
- Italian inflection (articles, contractions) is stricter than English.
- A describer adapter must produce the refs the verifier expects (`describer.facts`), or fill them itself.

## Adversarial review: findings and disposition

| Round | Finding | Disposition |
|---|---|---|
| 1 | Lane phrase allowed in kinds whose refs do not carry a lane (save, foul, score reminder, goal) | Closed: `facts` offers team, player and lane only if the refs carry them; test |
| 1 | Symbols, emoji, `?`, control and bidi characters invisible to the tokenizer | Closed: leftover characters outside letters, space and `. , ! : ; ' -` are rejected; test |
| 1 | Content-free text (`!`, `the`) replaced a real description | Closed: an outcome word is required; test |
| 1 | Length limit bypassable (no spaces, 100k characters) | Closed: 400 characters per field, words counted by whitespace and by token; test |
| 1 | `int()` on 4,301+ digits crashed `build_session` | Closed: numbers compared as strings, a failing check rejects (fail closed); test |
| 1 | Role or attachment ambiguity inside the allowed words ("Foul of Costa by Harbour") | Closed for names by the position rule (rule 6); ambiguity in the order of other allowed words stays documented in SPEC §5 |
| 2 | Widening the shared function words opened real flips ("scores on Northgate", "Foul on Costa", "è assist di") | Reverted: only articles and "and" are shared; test turns relation words round |
| 2 | A lone word other kinds share ("Time.", "Fine.", "Off.") passed the content rule | Closed: the rule uses outcome words; compounds are matched as whole words; test |
| 2 | An object that returns different text on each read passed `check` and became a cue | Closed: the result is copied into a validated `Description` before checking; test |
| 3 | The score phrase (starts with the home team) accepted where a team belongs ("Throw-in to Northgate 0, Harbour 0" for an away throw-in); the assist clause accepted as a subject | Closed: the position rule covers every canonical phrase; tests |
| 4 | "Foul of Harbour." accepted (the team follows an attested "of"; nothing checks the word before the "of") | **Open, documented** (SPEC §5): a two-word look-behind closes it but costs 14 points of acceptance in English and 16 in Italian on the corpus written with the word list in hand (3 seeds), so it was not applied |

Position rule (decided after the first review, implemented, extended to canonical phrases after round 3): a name or a phrase must stand between the neighbour words some template of the key gives it. Measured on 20 seeds with the corpus written with the word list in hand, sentence-on-moment pairs accepted went from 68.7% to 46.9% (en) and from 85.5% to 78.6% (it); the role-confusion examples of the review and the round-3 score-phrase and assist-subject bypasses went from accepted to rejected; template variants stayed at 100%.
