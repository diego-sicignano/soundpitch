# Microsoft x Premier League "Inside the Game" hackathon: what the rules say

Source: [`OFFICIAL_RULES.md`](OFFICIAL_RULES.md) (verbatim, downloaded 2026-10-19). Section numbers below are the rules' own. This page is our reading, not legal advice; where it matters, read the original.

## Dates

All times in the rules are **Pacific Time**. The Italian times are our conversion (US daylight saving ends 1 Nov, Italy's ends 25 Oct), check them against a clock before relying on them.

| What | Rules (Pacific) | Italy |
|---|---|---|
| Registration opens | 29 Sep 2026, 09:00 | |
| **Registration closes** | **20 Oct 2026, 12:00** | **20 Oct, about 21:00** |
| Build and submit | 6 Oct 09:00 to 27 Oct 2026, 23:59 | |
| **Submission deadline** | **27 Oct 2026, 23:59** | **28 Oct, about 07:59** |
| Judging | 27 Oct 09:00 to 10 Nov 2026, 23:59 | to 11 Nov, about 08:59 |
| Winners announced | no later than 20 Nov 2026, 23:59 | |

- Section 4.3: the project must be **newly created after the start of the Registration Period** (29 Sep). SoundPitch's first commit is on 2026-10-19.
- The rules never mention a finalist round, a live pitch or a "top six". Judging is of the written submission, the video and, if judges choose, the live demo (4.8). A third-party README claimed a "top six notified 10 Nov"; that is not in the rules.

## Who can enter (section 3)

- Individuals of legal age, **teams of up to four**, or organisations. One representative submits for a team. A person can be in several teams.
- Not open to residents of countries where US or local law prohibits it (the rules list Brazil, Quebec, Russia, Crimea, Cuba, Iran, North Korea, Sudan, Syria and OFAC-designated countries), to Microsoft and Premier League staff, judges and their employers, or anyone with a conflict of interest.
- 4.12: the project must not have had financial or preferential support from Microsoft (funding, contract work, a commercial licence) before the submission period ends.

## The challenge (4.1)

Build AI applications or agents that turn **synthetic football events** into **explainable match intelligence**, real-time narratives and automated recaps for studio, broadcast or streaming use, flexible enough for fans in any market. It must be responsive enough for live play.

One pipeline, five stages:

1. **Ingest** synthetic events as they happen.
2. **Interpret** them into statistics, patterns and context.
3. **Explain** why a moment matters, not only that it happened.
4. **Render** it as something that can sit on screen alongside the match; clean, timed, machine-readable output is explicitly welcome.
5. **Personalize** it so an analyst and a casual fan get two genuinely different experiences (favourite club or player, player-focus mode, language, a single metric).

Also listed: player identification, pass quality, speed metrics, auto-eventing from video, narrative generation, explainability (control vs chaos, pressure, rhythm), **data innovation** (create or extend synthetic datasets), multi-language storytelling. A project that only generates metrics has no audience; one that only personalizes has nothing to personalize.

Data (4.7): **synthetic, football-realistic data only.** Microsoft and the Premier League distribute no data or footage; you source your own and must hold the rights.

## What a valid submission contains (4.4, 4.8)

- A newly built project.
- A short **pitch**: what you built, which **Microsoft and Azure technologies** you used, what it does, what problem it solves.
- A **demo video under 2 minutes** (judges need not watch longer), showing the project working on its target device and platform, with a **public URL** on YouTube, Vimeo, Facebook Video or Youku. No third-party trademarks or copyrighted music or material without permission.
- A **public GitHub repository** URL ("must be public for your entry to be considered").
- **Free, unrestricted access for judges** (link to a site, functioning demo or test build; login details if private) **until the Judging Period ends (10 Nov)**. Judges may judge from the text, images and video alone.
- English, or an English translation of everything.
- Original work you solely own; open-source use is allowed if you follow the licences and add to the underlying software (4.11). Third-party SDKs, APIs and data need authorisation (4.3).
- Not a winner of any other contest. No obscene, offensive, violent, defamatory or illegal content; nothing promoting alcohol, drugs, tobacco or a political agenda.
- You can submit several projects if they are substantially different (4.5).

## Prizes (section 8)

Amounts are per team member; cash is a USD e-gift card. One project can win at most one Grand Prize and one Category Prize.

| Prize | What it rewards (4.2) | Per member |
|---|---|---|
| Grand Prize, first | Best overall: most complete and compelling, innovative use of the Microsoft AI platform, accessible and personalized experiences | $4,000 + a digital Premier League game ticket (about $1,000) + $50 store voucher + social feature |
| Grand Prize, second | Runner-up on the same basis | $2,500 + ticket + $50 voucher + social feature |
| Best Use of Microsoft Foundry | Using Foundry to develop, orchestrate and manage AI solutions | $1,500 + $50 voucher + social feature |
| Best Enterprise Solution | Readiness for enterprise deployment: reliability, transparency, controls | same |
| Best Multi-Agent System | Specialised agents with distinct roles, shared state and handoffs, failure recovery, an outcome one agent could not match. Names GitHub Copilot, Microsoft Agent Framework, A2A | same |
| Best Azure Cloud Native Integration | AKS, Container Apps, Functions, Logic Apps, AI-optimised data platforms; event-driven, resilient | same |

Judges can move a project to a better-fitting category (4.3). Winners go through identity and eligibility verification and sign affidavits and tax forms (8.2 to 8.4).

## How judging works (section 6)

- **Stage one**, pass or fail: the project reasonably fits the theme and the required technologies.
- **Stage two**: five equally weighted criteria, 20% each:
  1. **Technological Implementation**: creative, optimised synthetic data; quality software practice; effective use of the "hero technologies" (**Microsoft Foundry, Agent Framework, Azure MCP, GitHub Copilot Agent Mode, Fabric, GitHub SDK, GitHub CLI, Azure Apps and AI Services, Azure databases, etc.**); well-structured, documented, maintainable code.
  2. **Agentic Design and Innovation**: creative agentic patterns, sophisticated orchestration, MCP integration or multi-agent collaboration, novelty.
  3. **Real-World Impact and Applicability**: significance of the problem, production deployability, impact on users and businesses.
  4. **User Experience and Presentation**: intuitive design, a demo video that communicates the value, a balanced mix of frontend and backend.
  5. **Adherence to Hackathon Category**.
- **Ties** go to the higher score on criterion 1, then 2, and so on; then a judges' vote. So **technology is the tie-breaker**.
- Judges' decisions are final and may be made on the written material alone.

## Rights you give away (section 7, 10)

You keep ownership, but you grant Microsoft and the Premier League a worldwide, perpetual, irrevocable, royalty-free licence to use the submission for any purpose, and consent to use of your name and likeness for three years. The MIT licence of this repository is compatible with that.

## What this means for SoundPitch

| Rule | SoundPitch status |
|---|---|
| Synthetic data only | Yes: a seeded generator, no real footage or data. |
| Five-stage pipeline | Ingest, Interpret, Render and Personalize are implemented (see `SPEC.md` section 2). Two honest gaps against section 4.1: "Explain" says **what** happened and who was involved, not **why a moment matters** (the verifier forbids opinion on purpose); and "Interpret" produces prioritised moments, not statistics or patterns. Personalization is an accessibility profile, not a favourite club or player (T09, optional). |
| Render as timed, machine-readable output | Cues, earcons and WebVTT with millisecond timings. The cue sheet has a versioned JSON Schema (`docs/contracts/cuesheet.v1.schema.json`). |
| Two genuinely different experiences | Blind and low-vision listening, captions for deaf and hard-of-hearing fans, calm mode, three detail levels, two languages. |
| "Hero technologies" | **Partly met.** Foundry: run live once (26 calls), replay mode for the demo. Agent Framework: `FoundryChatClient` and a workflow (`workflow.py`). Not yet: Azure AI Speech with a real key (T04), Azure Container Apps hosting (T06), MCP (T08, optional). Criterion 1 is the tie-breaker, so this matters most. |
| Multi-agent category | The roles (moment detector, describer, verifier, fallback, timing planner) are executors of an Agent Framework workflow with a conditional retry edge. Only the describer touches a model, so this is orchestration of one model and deterministic code, not a team of autonomous agents; say so plainly. |
| Public repo, public demo until 10 Nov, video under 2 minutes | Not done yet. See [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md). |
| No third-party trademarks in the video | Teams are fictional (Northgate Red, Harbour Blue). Use no Premier League or Microsoft logos in the video without checking permission. |

## Points to keep in mind

- **Original work (4.6, 4.11):** the rules require the submission to be the entrant's own original work, solely owned. The README states that an AI coding assistant was used; the specification and the decisions are in the repository. 8.2 asks winners to verify their "role ... in the creation of the Submission".
- **Participation:** individual.
- **Commit email:** commits use the author's GitHub `noreply` address.
- **Trademarks:** do not show Premier League or Microsoft logos in the video without permission (4.4); the README says the project is not affiliated with either.
- **Voice-over:** use your own voice, or a synthetic voice whose licence allows it. No music.
- **Judge access (4.8):** the rules say "free of charge and without any restriction" until the judging period ends and do not define "restriction". The judges' path therefore makes no model call and has no daily quota (`docs/DECISIONS.md` D12).

