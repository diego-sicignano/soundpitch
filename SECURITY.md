# Security

SoundPitch is a hackathon project. It handles no personal data and runs on a fully synthetic match.

## Secrets

- Never commit keys. `backend/.env` is git-ignored; `backend/.env.example` lists the settings with empty values.
- Azure AI Speech and Microsoft Foundry credentials come from environment variables only.
- `POST /api/tts` is rate limited (`SOUNDPITCH_TTS_PER_MINUTE`, default 120 per process) so a public demo cannot drain the Speech quota. Text is capped at 400 characters.

## Reporting a problem

Open a GitHub issue, or if it involves a credential, a private security advisory on the repository. Please do not post live keys anywhere.
