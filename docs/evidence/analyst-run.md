# Analyst runs

Recorded 2026-10-26 with `soundpitch-mini` on Microsoft Foundry, as a Microsoft Agent Framework agent whose tools are the SoundPitch MCP server (`python -m app.analyst_run`). Every point is checked against the line it cites (SPEC §20); the rejected ones are listed with the reason.

| Window | Language | Attempts | Agent runs | Points kept | Points rejected | Tools called |
|---|---|---|---|---|---|---|
| kickoff | en | 2 | 0 | 1 | 7 | stored |
| kickoff | it | 2 | 0 | 2 | 4 | stored |
| goal_1 | en | 2 | 1 | 1 | 7 | get_recap, get_commentary, get_stats |
| goal_1 | it | 1 | 0 | 3 | 0 | stored |
| goal_2 | en | 2 | 0 | 3 | 5 | stored |
| goal_2 | it | 2 | 0 | 4 | 4 | stored |
| goal_3 | en | 2 | 0 | 4 | 4 | stored |
| goal_3 | it | 2 | 0 | 3 | 5 | stored |
| final_whistle | en | 2 | 0 | 2 | 6 | stored |
| final_whistle | it | 1 | 0 | 4 | 0 | stored |

## Rejected points

- kickoff en: point 1: 2 is not in recap:2
- kickoff en: point 2: commentary:3 is no source: cite recap:N or stats:M
- kickoff en: point 3: commentary:4 is no source: cite recap:N or stats:M
- kickoff en: point 4: commentary:6 is no source: cite recap:N or stats:M
- kickoff en: point 1: 64 is not in recap:1
- kickoff en: point 2: a stats:2 point must name exactly one team
- kickoff en: point 3: 2 is not in recap:2
- kickoff it: point 2: commentary:1 is no source: cite recap:N or stats:M
- kickoff it: point 3: commentary:3 is no source: cite recap:N or stats:M
- kickoff it: point 4: commentary:4,5,6 is no source: cite recap:N or stats:M
- kickoff it: point 1: a stats:2 point must name exactly one team
- goal_1 en: point 1: Harbour is not in recap:2
- goal_1 en: point 2: 16 is not in recap:3
- goal_1 en: point 3: goal_1 commentary is no source: cite recap:N or stats:M
- goal_1 en: point 4: a stats:16 point must name exactly one team
- goal_1 en: point 1: 1 is not in recap:2
- goal_1 en: point 2: a stats:16 point must name exactly one team
- goal_1 en: point 3: 5 is not Northgate's in stats:16
- goal_2 en: point 1: 1 is not in recap:3
- goal_2 en: point 2: commentary:4 is no source: cite recap:N or stats:M
- goal_2 en: point 3: commentary:3 is no source: cite recap:N or stats:M
- goal_2 en: point 4: 52 is not in recap:4
- goal_2 en: point 2: a stats:52 point must name exactly one team
- goal_2 it: point 2: goal_2 commentary:4 is no source: cite recap:N or stats:M
- goal_2 it: point 3: goal_2 commentary:3 is no source: cite recap:N or stats:M
- goal_2 it: point 1: a character other than letters, digits and . , ! : ; ' - % ( )
- goal_2 it: point 4: commentary:2,4 is no source: cite recap:N or stats:M
- goal_3 en: point 2: commentary:5 is no source: cite recap:N or stats:M
- goal_3 en: point 3: 78 is not in recap:5
- goal_3 en: point 1: recap:1-4 is no source: cite recap:N or stats:M
- goal_3 en: point 3: a stats:78 point must name exactly one team
- goal_3 it: point 1: Harbour is not in recap:4
- goal_3 it: point 2: Marsh is not in recap:5
- goal_3 it: point 4: commentary is no source: cite recap:N or stats:M
- goal_3 it: point 1: a character other than letters, digits and . , ! : ; ' - % ( )
- goal_3 it: point 4: commentary:5 is no source: cite recap:N or stats:M
- final_whistle en: point 1: 49 is not in recap:1
- final_whistle en: point 2: 2 is not in recap:2
- final_whistle en: point 3: a character other than letters, digits and . , ! : ; ' - % ( )
- final_whistle en: point 4: 5 is not in stats:90
- final_whistle en: point 1: Lindqvist is not in recap:2
- final_whistle en: point 4: a stats:90 point must name exactly one team
