# Security

SoundPitch is a hackathon project. It handles no personal data and runs on a fully synthetic match.

## Secrets

- Never commit keys. `backend/.env` is git-ignored; `backend/.env.example` lists the settings with empty values.
- The Foundry describer signs in with `az login` or a managed identity; no key is used. Azure AI Speech needs `AZURE_SPEECH_KEY`, read from the environment only (a container-app secret when deployed).
- The judges' image (`SOUNDPITCH_LLM=replay`) needs no secret at all.

## What is limited, and what is not

- **Model calls** (`SOUNDPITCH_LLM=foundry`) are decided by a durable usage ledger before they are sent: per-minute, per-day, per-token and monthly-estimate limits, fail closed (`docs/DECISIONS.md` D11). It is per host and counts estimates. Azure's own budget only alerts; it is not a cutoff.
- **The judges' path makes no model call** (D12): it replays recorded replies and verifies them again on every request.
- **`POST /api/tts`** speaks only text that a session returned, serves repeated requests from memory, and refuses a request before calling Azure when a client, the process, the UTC day or the UTC month is over its limit (D14, `SPEC.md` §8). **These limits live in the memory of one process and restart at zero; they are a brake, not a spending cap.** The only hard cap on Speech spending is the pricing tier of the Speech resource. Behind a reverse proxy, set `SOUNDPITCH_TRUST_PROXY=1` (only behind exactly one trusted proxy), or every caller shares one per-client limit.
- **Headers**: `nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` and a content security policy on every response except the interactive API documentation (D16). No CORS is configured.
- **Input**: query parameters are enumerated or range-checked by the API contract; nothing a client sends reaches a model prompt. The session cache is bounded.

## Not covered

No penetration test has been done. There is no authentication (the demo is public by design) and no per-client limit on `/api/session`, which is cheap with the templates and the replay mode. Anyone holding the Azure credential can call the Foundry deployment directly, bypassing the ledger.

## Reporting a problem

Open a GitHub issue, or if it involves a credential, a private security advisory on the repository. Please do not post live keys anywhere.
