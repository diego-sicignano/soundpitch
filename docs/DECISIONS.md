# Decisions

Short records of choices that shaped the project. Add an entry when you make a choice that someone could reasonably undo.

## D1. Code decides truth, the model only chooses words (2026-10-19)

Every sentence is checked against the events before it reaches a listener. A blind listener cannot see that a description is wrong, so an invented player or score is worse than silence. **Consequence:** a model can never put unverified text on air; it costs us a verifier and a fallback to maintain.

## D2. A deterministic template describer is both the offline mode and the fallback (2026-10-19)

It works with no network and always passes the verifier. **Consequence:** tests, the demo and the page work without any key; the model is an upgrade, not a dependency.

## D3. A synthetic match with a pinned storyline (2026-10-19)

Goals at 16', 52', 78' and a final 2-1, so every demo and test lands on the same moments. Random play never scores. Rules 4.7 require synthetic data. **Consequence:** the match is not realistic in detail, and positions are generated, not measured.

## D4. The timing planner is plain arithmetic (2026-10-19)

A speech duration estimate, a lag budget per priority, and slots reserved in priority order. No learned model. **Consequence:** results are deterministic and explainable, and counted in `docs/evaluation.md`. Real voices speak at their own speed, so estimates can be off by a little.

## D5. A plain HTML page, no build step (2026-10-19)

One `index.html`, `styles.css`, `app.js`. Accessibility is the product, and the less framework between the markup and the user, the easier it is to get right and to audit with axe. **Consequence:** no components or type checking on the front end; the server does the thinking.

## D6. One container serves the page and the API (2026-10-19)

FastAPI mounts the static page. One image, one URL, easy to host on Azure Container Apps and for judges to open. **Consequence:** the page and the API scale together.

## D7. The browser voice is the default, Azure neural voices are opt-in (2026-10-19)

The page works for anyone with no key and no cost. Azure AI Speech needs a key, so it is guarded by a per-minute limit. **Consequence:** the demo's best audio needs a configured server.

## D8. English and Italian only (2026-10-19)

The rules ask for multi-language output; two languages show it without diluting the verifier. The verifier is language independent, so adding a language means adding templates. **Consequence:** other languages are out of scope for the hackathon.
