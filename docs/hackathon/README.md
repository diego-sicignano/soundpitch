# Hackathon material

| File | What it is |
|---|---|
| [`COMPLIANCE.md`](COMPLIANCE.md) | Each rule that could disqualify the project, the evidence read, the decision taken and the risk that remains. |
| [`SUMMARY.md`](SUMMARY.md) | Our reading of the rules: dates, what to submit, categories, judging, risks, and how SoundPitch maps to them. |
| [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) | The tick-box list to finish before the deadline. |

## The Official Rules themselves

The rules are published by Microsoft at <https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md> (the hackathon website named in the rules, <https://aka.ms/insidethegame>, answered "404 Error" on 2026-10-19 and again on 2026-10-21, so check it in a browser before relying on anything not in the rules). Section numbers in this repository are the rules' own, as read from the copy downloaded on 2026-10-19; the last change to the file upstream is dated 2026-09-28.

This repository does **not** redistribute the rules text or Microsoft's playlist page. The source repository carries an MIT licence, but the rules also state "All rights are reserved" for the hackathon's intellectual property (section 11.8), carry no copyright line of their own, and say nothing about copying; whether the repository licence covers that one file is not settled, so the copy is kept only on the owner's machine, in the git-ignored folder `docs/hackathon/_local/`. See [`COMPLIANCE.md`](COMPLIANCE.md) and D21 in [`../DECISIONS.md`](../DECISIONS.md).

To refresh the private copy:

```powershell
$base = "https://raw.githubusercontent.com/microsoft/insidethegamehackathon/main"
New-Item -ItemType Directory -Force docs/hackathon/_local | Out-Null
Invoke-WebRequest "$base/OFFICIAL%20RULES.md" -OutFile docs/hackathon/_local/OFFICIAL_RULES.md
```
