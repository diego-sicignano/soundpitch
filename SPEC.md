# SoundPitch — Specification

**SoundPitch lets a blind or low-vision fan follow a football match by ear.** It turns a stream of synthetic match events into a timed audio-description track, a spatial "ball sound", and captions. Built for the Microsoft x Premier League "Inside the Game" hackathon. The spec is the authority; code follows it.

## §1 Why

- Live audio description of football is rare and mostly volunteer-run; broadcasters have only just started (Sky Sports, 10 Oct 2026: about 109 Premier League games a season).
- Good description *describes the action* in a radio style, without opinions (RNIB guidance), and must fit into the gaps of play.
- Fans also want to know where the ball is and who is attacking.

## §2 Pipeline (the five hackathon stages)

| Stage | Component | Kind |
|---|---|---|
| Ingest | `match_gen` synthetic match, 1 event every 3–9 s | code |
| Interpret | `moments` groups events into prioritised **moments** | code |
| Explain | `Describer` writes a `full` and a `short` sentence per moment | LLM (Foundry) or templates |
| Verify | `verifier` checks every name, number and attribution against the events; 2 retries, then the template fallback | code |
| Render | `timing` plans cues into the silence between moments; `render` emits cues, earcons and WebVTT | code |
| Personalize | `Profile`: detail, language, sonification, calm mode, speech rate, output channel | code |

Only code decides **what is true** and **when it is said**. The model only chooses words.

## §3 Data

- Pitch: `x` 0–100 along the length as the TV camera sees it (0 = left goal), `y` 0–100 across. Home attacks left to right in the first half, right to left in the second.
- `lane` is team-relative: `left`, `centre`, `right` from the point of view of the team attacking.
- `progress` of a team = `x` if it attacks left to right, else `100 - x` (0 = own goal line, 100 = opponent's goal line).
- Teams: `Northgate Red` (`home`), `Harbour Blue` (`away`), 11 fictional players each. Minutes are `t // 60 + 1` (1..90); no stoppage time.
- Storyline for `SEED = 424242`: goals by home at 16', away at 52', home at 78'; final score `Northgate Red 2 - 1 Harbour Blue`. Random play never scores.

## §4 Moments and detail levels

| Priority | Moments |
|---|---|
| 3 (must say) | kickoff, goal, half-time, full-time |
| 2 | shot (on, off, blocked), save, corner, dangerous free kick (`progress >= 70`), score reminder every 10 minutes |
| 1 | tackle/interception won in the opposition half or midfield, foul, throw-in, build-up reaching `progress >= 60` |
| 0 | any other run of passes/dribbles |

Detail profile → minimum priority: `essential` 2, `standard` 1, `full` 0. A run of consecutive pass, dribble, long ball and clearance events by one team is one **build-up** moment, described when it ends.

## §5 Describing and verifying

- Style: present tense, factual, no opinions, surnames only, team names, direction words relative to the attacker (`left`, `centre`, `right`).
- A `Description` has `full`, `short` and `refs`: a list of `(event_id, field, value)` claims. The `refs` are the audit trail of the facts a sentence may state: the code derives them from the moment (`describer.facts`) and a describer cannot add, drop or change them.
- The verifier rejects a description when any of these holds:
  1. `moment_id` or `lang` differ from the moment's and the profile's, or the `refs` differ from the ones the code derives.
  2. A ref differs from the event; the text names a player not involved in the moment; the text contains an integer that is not a score, the minute or a score reminder minute; `full` has more than 45 words or `short` more than 15 words or `short` is longer than `full`; `full` or `short` has more than 400 characters (the most `/api/tts` speaks), or a word count by whitespace or by words exceeds the limit. (The checks of S3, plus the length cap.)
  3. *Grounding.* A sentence may state only the facts the refs carry, plus the score. `describer.facts` builds them and drops the team, player or lane of the moment's last event when the moment's refs do not carry it (a save, a foul or a score reminder has no lane to state). Facts that carry a relation are written only as **canonical phrases**, built by code and copied verbatim: the score (`Northgate 1, Harbour 0`), the assist clause (`set up by Adeyemi`, `assist di Adeyemi`), the build-up chain (`Moretti, Okafor, Duval`), the minute phrase of a score reminder (`Minute 10`), the direction and zone phrases, and, where the refs carry a lane, the lane phrases (`from the left`). Outside canonical phrases every word of `full` and of `short` must be the surname of the player or the short name of the team the facts carry, a word of the **vocabulary** of the moment's template key (the words of that key's templates in `LEX`, `describer.py`; a hyphenated word may be written with a space, `half time`, but its parts are not words of their own), or an article or "and" (`the a an and`; `il lo la i gli le un una e`), the only words shared by every key. Every word that relates two facts, such as `for`, `on`, `by`, `per`, `di`, belongs to the templates of one kind of event, because "scores on Northgate" and "scores for Northgate" are different facts; a wider shared list was tried and reversed after review (D9). A digit is allowed only inside a canonical phrase. Text is compared after Unicode NFC normalisation and lower-casing. Another name, a number word, another team, a lane, zone or direction word, an event word of another kind, or an opinion is therefore rejected.
  4. Outside canonical phrases, a character other than a letter, whitespace or one of `. , ! : ; ' -` is present: symbols, emoji, `?`, quotes, brackets, control and invisible characters are rejected.
  5. The text does not say what happened: it has no outcome word of the key (a word that only this kind of event uses, so `time`, `off`, `Fine` or `shoots` alone are not enough), unless it is a score reminder carrying the score phrase.
  6. *Position.* A name or a canonical phrase stands only where a template of the key stands it. Ignoring articles, the word before it and the word after it must each be a word that comes before, or after, that name or phrase in some template of the key; the start of the text, its end and another canonical phrase all count as one *edge* neighbour, because phrases are optional. "Foul by Costa of Harbour" is a template order; "Foul of Costa by Harbour" is not, and neither is "Goal! Northgate finds Marsh" or "Corner to Rossi, taken by Harbour". A key whose templates never name the team, or the player, or never contain a phrase, does not allow it: a shot sentence carries no score, the score phrase (it starts with the home team) cannot stand where a team belongs ("Throw-in to Northgate 0, Harbour 0"), and the assist clause cannot be a subject ("set up by Adeyemi scores for Northgate").
  7. A required fact is missing: goal: scorer, team and score in `full`, scorer in `short`; kick-off: the team; half-time, full-time and score reminder: the score in `full`.
- A verifier that cannot run rejects: if the check raises, the pipeline counts the attempt as rejected (fail closed). A describer's result is copied into a plain, validated `Description` before it is checked, and only the copy can become a cue, so an object that answers differently each time it is read cannot pass and then change. The template fallback must verify; if it does not, building the session fails instead of speaking.
- What this guarantees and what it does not. Every entity, number, score, minute, lane, zone, direction and event outcome in a description comes from the moment's own facts, and the words around them come from a reviewed list. It does **not** verify the meaning of the prose. Names and phrases are held in the places the templates give them, but a describer can still reorder the allowed words that do not touch a name, or choose, among the words of the key, one that fits the sentence badly. For example "Foul of Harbour." (a foul by a Harbour player, worded like a foul against Harbour) is accepted, because "of" before the team is a template word and the rule looks one word to each side; looking two words back closes it but, measured on the corpus written with the word list in hand, accepts a third fewer sentences in English (46.8% to 33.0%) and a fifth fewer in Italian (78.7% to 62.8%), so it is not applied. `POST /api/tts` speaks only text the server itself returned as the `text` of a cue in a session (§8), so it cannot be used to synthesise other text; the 400-character cap is the length of the longest verified description. Adding a word to the vocabulary or to the shared articles is a human review decision (the word must not change a fact or a relation). The guarantee is bounded by the vocabulary, not by understanding the sentence.
- A false rejection costs only naturalness, because the verified template fallback exists; a false acceptance costs trust. When in doubt the verifier rejects.
- Attempt 1..3: failed moments get `ValidationFeedback` and are described again (max 2 retries); then the deterministic template description is used and the cue is marked `fallback`.
- Languages: `en` and `it`. The verifier is language-independent.

## §6 Timing

- Speech duration estimate: `words * 60000 / wpm + 300` ms, `wpm = 165 * rate` (`en`) or `155 * rate` (`it`).
- A cue may start no earlier than its moment time plus 300 ms, and not later than moment time plus the **max lag**: priority 3 → 10 s, 2 → 6 s, 1 → 5 s, 0 → 4 s.
- Cues never overlap; gap between cues at least 250 ms.
- Planning order: priority high to low, then time. For each moment try `full`, then `short`; if neither fits it is **dropped** with a reason. Priority 3 is never dropped: it takes the first free gap after its earliest start, even past the max lag.
- The result is deterministic.

## §7 Earcons (ball sound) and calm mode

One short sound per event, `pan = (x - 50) / 50` (left to right), `pitch = progress / 100` (higher near the opponent's goal). Kinds: `tick` (pass, dribble, long ball, clearance), `turnover`, `shot`, `save`, `goal`, `set_piece`, `whistle`, `whistle_long`. **Calm mode** keeps only `goal` and `whistle*` at gain 0.3 and slows speech to rate 0.9 at most.

## §8 API

| Method | Path | Result |
|---|---|---|
| `GET` | `/api/match` | teams, rosters, final score, goal list |
| `GET` | `/api/presets` | windows: `kickoff`, `goal_1`, `goal_2`, `goal_3`, `final_whistle` |
| `GET` | `/api/session?preset&detail&lang&earcons&calm&rate` | `Session` |
| `GET` | `/api/session.vtt?…` | WebVTT captions |
| `GET` | `/api/cuesheet?…` | `CueSheet`, JSON for graphics and captioning systems (§13) |
| `GET` | `/api/cuesheet.schema.json` | JSON Schema of the `CueSheet` |
| `POST` | `/api/tts` `{text, lang, rate}` | `audio/mpeg` from Azure AI Speech, `501` when not configured |
| `GET` | `/api/health` | `{status, llm}` |
| `GET` | `/api/voice` | `VoiceSupport`: `{stored_clips: {en, it}, live}`, what the Azure voice can do on this server (S29) |

Errors (`{code, message}`): unknown preset → `404 preset_not_found`; invalid parameter → `422`; `/api/tts` → `501 tts_not_configured`, `403 tts_text_not_issued`, `502 tts_failed`, `429 rate_limited`; `/api/session`, `/api/session.vtt` and `/api/cuesheet` with `SOUNDPITCH_LLM=foundry` or `SOUNDPITCH_ORCHESTRATOR=workflow` and a missing setting or package → `503 llm_not_configured`; an unhandled error → `500 internal_error` (a fixed message that names no setting and no value). `Session.cues[].start_ms` is relative to the window start.

### Response headers (S25)

Every response, an unhandled `500` included, carries `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and `X-Frame-Options: DENY`. Every response except the interactive API documentation (`/docs`, `/redoc`, which load their own scripts) also carries `Content-Security-Policy: default-src 'self'; media-src 'self' blob:; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`. The page uses no inline script, no external request and no inline style attribute, so the policy needs no relaxation; the end-to-end suite fails if the browser reports a policy violation.

### `/api/tts` guard (S22) and stored clips (S26)

Order of checks: input validation (`422`), text not issued (`403`), the client's per-minute limit (`429`), a stored clip (`200`), Speech not configured (`501`), then the live limits (`429`), then Azure.

- **Only issued text.** The server remembers the `(lang, text)` of every cue it has returned in a session (at most 4,096 pairs, oldest forgotten first, per process). Any other text is refused with `403 tts_text_not_issued` and nothing is spoken. The page then falls back to the browser voice. A server restart forgets the pairs; reloading the session issues them again.
- **Stored clips (the judges' path).** `backend/app/audio/` holds one mp3 for each sentence the demo can speak, made once at speech rate 1.0 with the neural voices of §14, and a `manifest.json` (`version`, `format`, `voices`, `generated`, and for each clip its id, `lang`, `text` and size). `/api/tts` serves the clip of an issued `(lang, text)` with no Azure call and no Speech key, with the header `X-Audio-Rate: 1`; the page applies the speed itself (§9). A clip is used only if its manifest entry has the same language and text and its file exists and is not empty; otherwise it is treated as absent. The clips are made by `python -m app.clips_build`: without options it is a **dry run** that only counts the sentences, the characters and the estimated cost and needs no key and no network; `--generate` calls Speech (`AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`), only for missing clips, refuses to send more than `--max-chars` (default 10,000) characters, accepts `--limit N`, retries `429` and `5xx` with a growing wait, stops at `401` or `403`, and never prints the key.
- **Live path (development only).** Without a stored clip and with Speech configured the text is sent to Azure. Repeating a request is served from memory (at most 256 clips, keyed by language, text and speech-rate percent), and the response carries `X-Audio-Rate` equal to the rate applied by the service. These requests are limited before Azure is called: requests per minute for the whole process (`SOUNDPITCH_TTS_PER_MINUTE`, default 120); characters sent to Azure per UTC day (`SOUNDPITCH_TTS_CHARS_PER_DAY`, default 60,000) and per UTC month (`SOUNDPITCH_TTS_CHARS_PER_MONTH`, default 300,000). Characters are counted when a request is sent, also if it then fails, because it may have been billed. A value that is not a whole number of at least 1 is ignored and the default applies.
- **Per client (S27).** At most `SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE` requests a minute (default 30) per client, counted for every request that passes the issued-text check. The client is the connection's address or, only with `SOUNDPITCH_TRUST_PROXY=1`, the address in the **last entry of the last `X-Forwarded-For` header line**, read defensively because proxies write it differently: `1.2.3.4`, `1.2.3.4:5678`, `[2001:db8::1]:5678`, `2001:db8::1` and `[2001:db8::1]` all give the address without the port, so a client that changes port is still one client; anything that is not an address falls back to the connection's address. With `SOUNDPITCH_LOG_FORWARDED=1` the server logs, for up to five distinct values, only the **shape** of the raw header (every digit replaced by `9` and every hex letter by `x`, so `999.9.999.9:99999`), never an address, so the format of a real proxy can be settled from the log stream.
- **What this is not.** The live counters live in the memory of one process and restart at zero; they are not a spending cap and not a statement about the Azure bill. The public deployment holds no Speech key, so it has no Speech spending at all; the pricing tier of a Speech resource is the only hard cap on a resource that is used live.
- **Availability (S29).** `GET /api/voice` says what the Azure voice can do on this server, so the page never offers a voice that is not there: `stored_clips` is, for each language, the number of manifest entries whose file is present and not empty (the same test as a clip is served by), and `live` is true when `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` are both set. It sends nothing to Azure, reads no key value and is not rate limited. A server without clips and without a key answers zeros and `false`: this is the state of the repository until the clips are made.
- **Disclosure.** The Azure voice is synthetic (Code of Conduct for Microsoft AI Services): the page says so in a visible note (§9).

## §9 UI (`frontend/`, plain HTML, one page, keyboard first)

Landmarks `header`, `main`, skip link. All controls are real labelled form elements. The controls are English; the commentary is in the language of the profile, so the transcript, the captions and the live region carry `lang` of the session (WCAG 3.1.2) and the page language stays `en`. The Azure voice is synthetic, so a visible note under the Voice control says so and describes it (`aria-describedby`). The page applies the speed of a stored clip itself: it plays the audio with `playbackRate` set to the effective speech rate divided by the `X-Audio-Rate` header of the response (pitch preserved); a response without that header is played as it is (S28). **The page offers only voices that exist (S29, S30).** It reads `/api/voice` when it loads and whenever the language changes: the `azure` option of the Voice control is disabled, and the note says so, when the server has no stored clip for the language of the commentary and no live voice; if `azure` was selected and the language changes to one without clips, the page goes back to `browser` and says so in `status`. The default voice is `browser`, the only one that needs nothing from the server. When Play is pressed with the browser voice and the browser has no speech synthesis, or no installed voice for the language of the commentary, `status` says so and points to the captions, the transcript and the “My own screen reader (text only)” output, which keep working; the page does not pretend that anything is being spoken. Test ids:

| Id | What |
|---|---|
| `preset`, `detail`, `lang`, `rate` | selects / range |
| `toggle-earcons`, `toggle-calm`, `toggle-captions` | checkboxes |
| `output` | select: `browser` voice, `azure` voice, `screenreader` (text into an `aria-live` region) |
| `voice-note` | the visible note under the Voice control: that the Azure voice is synthetic when it is available, that it is not available on this server when it is not (S29) |
| `play` | play / pause button (also `Space`) |
| `scoreline` | current score |
| `pitch` | schematic pitch with ball marker `ball` |
| `timeline` | speech blocks over time; `timeline-cue-{n}` per cue |
| `transcript`, `transcript-cue-{n}` | cues as they are spoken |
| `captions` | large caption line |
| `live-region` | `aria-live="polite"` used by the `screenreader` output |
| `report` | verification and timing figures |
| `status` | `role="status"` line: loading, ready, playing, paused, finished, errors |

Query parameters for automation: `preset` (initial window, default `goal_1`), `speed` (clock multiplier, default 1), `speech=off`.

## §10 Acceptance rows

| ID | Given | Then |
|---|---|---|
| **S1** | seed 424242 | identical output on two runs; ids sequential; times non-decreasing; goals at 16' home, 52' away, 78' home; final score 2-1; coordinates within 0–100 and lanes consistent with direction |
| **S2** | the match | every priority-3 kind is a moment at every detail level; `essential` ⊂ `standard` ⊂ `full`; build-ups are runs of one team's pass-like events |
| **S3** | the verifier | accepts template text; rejects a wrong ref, empty or altered refs, a wrong `moment_id` or `lang`, a foreign player name, a stray number, an over-long text |
| **S4** | scenarios | `bad_then_good`: every cue verified after one retry; `always_bad`: failing moments use the fallback, cues are marked `fallback`, track is complete |
| **S5** | the planner | no overlaps, gaps ≥ 250 ms, all priority-3 moments scheduled, high priority never dropped for low, `short` used when `full` does not fit, deterministic |
| **S6** | profiles | cue count `essential` < `standard` < `full` on one window; `it` text with the same event ids as `en`; calm mode keeps only goal and whistle earcons; pan sign follows `x` |
| **S7** | the API | valid `Session`; `404` for an unknown preset; WebVTT well-formed; `/api/tts` `501` unconfigured and audio bytes with a stubbed Azure |
| **S8** | the page | pressing `play` fills `transcript` in order and `timeline` with one block per cue; captions toggle; `screenreader` output writes into `live-region`; `Space` toggles play |
| **S9** | accessibility | axe-core reports no violations on the page in both states |
| **S10** | evaluation harness | across 20 seeds and all detail levels: no overlap, 100% of priority-3 moments scheduled, 100% of planted errors caught |
| **S11** | a fake Foundry client (§11) | correct replies: every moment verified at attempt 1 with one call per chunk of 20; wrong names on the first call: the retry prompt carries the verifier's issues and succeeds; unparsable JSON, a reply with missing or unknown moments, a timeout or an exception counts as a failed attempt; three bad attempts: template fallback; over the call cap: templates and the budget trace; the prompt holds only the facts listed in §11 (no other player, no refs); refs in a reply are ignored and the code's refs are used; hostile replies (the adversarial alterations of S19) never become `verified`; a repeated window costs no call; a missing setting or package answers `503 llm_not_configured` |
| **S12** | a real Foundry deployment (manual) | `python -m app.foundry_run --write` runs on every preset and detail level in both languages and `docs/evidence/foundry-run.md` records, with the date and the model name, the first-attempt pass rate, retries, fallbacks, the rejection reasons and the median and p95 call latency |
| **S13** | both orchestrators (§12) | same cues, statuses and report for `scripted`, `bad_then_good`, `always_bad`, a model that lies once and a recorded-reply store; the trace names the executors that ran, in order, and the retry loop shows as `Describer`/`Verifier` pairs; a describer that raises once is retried; a missing package is named with the command that installs it; the API serves the workflow's session when `SOUNDPITCH_ORCHESTRATOR=workflow` (skipped without the optional package) |
| **S14** | a real Azure Speech key (manual, §14) | `check_speech` writes a playable mp3 for `en` and `it`; the page plays it; evidence in `docs/evidence/` |
| **S15** | the cue sheet (§13) | validates with the contract for every preset, detail level and language; the committed schema equals the generated one and is served; items sorted; ids unique; descriptions never overlap; a caption has the timing and text of its description; the descriptions are the session's cues and the ball sounds its earcons; unknown fields and unknown item types are refused by the contract |
| **S16** | the deployed URL (§15) | `python -m app.smoke <url>` exits 0 against the public URL; the page loads in a clean browser; the service stays up until 10 Nov 2026 |
| **S17** | MCP (§16, optional) | tools return valid contracts; an unknown preset is a tool error |
| **S18** | player focus (§17, optional) | with a focus, moments of that player are raised by one priority up to 2, others are unchanged; earcon gain x1.5 capped at 1.0; no focus: identical to today; an invalid shirt gives `422` |
| **S19** | grounding (§5), false acceptance | across every moment of several seeds, both languages, all detail levels, each generated alteration of a valid description is rejected, counted per category: a wrong team, a wrong or swapped player, the scorer and the assister exchanged, a changed or swapped score, a changed digit, another lane, zone or direction, a lane or team that the moment's refs do not carry, a word of another event kind or never used, a relation word turned round (`on`, `at`, `against`, `su`, `contro` before a team or player), a name or a phrase moved out of its place (player and team exchanged, "Foul of Costa by Harbour", "Goal! Northgate finds Marsh", the score where a team belongs, the assist clause as a subject), a word other kinds of event share used alone, a lone part of a compound word, an invented name, a symbol, emoji or control character, text that says nothing, text over the length cap (including 100,000 characters and 5,000 digits, which must not crash the check), a missing required fact, wrong or empty refs, `moment_id` or `lang`, and text taken from a different moment (accepted only if it is true for this one); a describer that lies, an object that answers differently each time it is read, and a check that raises, still end in the template fallback with no `verified` cue |
| **S20** | grounding (§5), false rejection and fallback | every template variant of every moment (both languages) is accepted; random sentences made only of allowed pieces (the key's words, articles, the moment's player and team, canonical phrases) are accepted; upper case, NFD, typographic apostrophes and hyphen-or-space spellings of a valid sentence are accepted; the acceptance of hand-written corpora (written with and without the word list) and the share of moments that end in the template fallback are **reported with denominators, not hidden**, in `docs/evaluation.md` |
| **S21** | the usage ledger (§11), with a temporary database and a fake client | concurrent reservations over a cap grant exactly the cap, also across processes; a new ledger on the same file continues the counts; day and month roll over with the UTC clock; a failed, timed-out or cancelled call keeps its worst case and a settled call frees the margin; reservations in flight count; a database that cannot be opened or written refuses the call before the client is touched; refused work ends in verified templates with the reason in the trace; the environment cannot raise the monthly ceiling above 4.00 EUR; a stored reply is not paid for twice, also after a restart |
| **S22** | the `/api/tts` guard (§8), Azure stubbed | text not returned in a session: `403 tts_text_not_issued`, Azure not called; a cue text of a returned session (also one that is not kept) is spoken, only in its own language; a repeated request is served from memory; the per-client, per-process, per-day and per-month limits refuse before Azure is called and the day and month roll over with the UTC clock; a failed call keeps its characters counted and is not remembered; bad settings fall back to the defaults; the issued set and the audio cache are bounded; the client is the connection's address, or the last `X-Forwarded-For` entry only with `SOUNDPITCH_TRUST_PROXY=1` |
| **S23** | the page language (§9) | the transcript, the captions and the live region carry the language of the commentary (`lang="it"` for Italian), also each cue text, while the clock and the status badge of a cue stay `en`; the page language stays that of the controls; the language options carry their own `lang` |
| **S24** | the replay mode (§11), with a fake model | replies stored by the Foundry describer and exported to the replay file are replayed into the same cues without any model; a recorded reply that lies is rejected by the verifier like any other and never spoken; a request without a recorded reply, a missing, invalid or unparsable file is described by the templates and the trace says so; the export reads a ledger and `--check` reports the coverage of every preset, detail level and language; the API reports `replies` in `/api/health`; replay needs neither the SDK nor a network; once the committed file has content it covers every window |
| **S25** | response headers (§8) | the headers above are on the page, the API and error responses; the documentation pages have no policy; no policy violation in the browser while the page loads, plays, switches language and uses the screen-reader output |
| **S26** | stored clips and the clip tool (§8), Speech stubbed | the dry run counts the sentences, characters and estimated cost with no key and no network call; the generation writes one mp3 for each missing sentence and the manifest, does not repeat an existing clip, honours `--limit` and the character cap, retries `429` with a growing wait, stops at `401` and `403`, and never prints the key; `/api/tts` serves the stored clip of an issued text with no Speech key and `X-Audio-Rate: 1`, refuses text that was not issued with `403`, and ignores a clip whose manifest entry or file does not match; once clips are committed every sentence the demo can speak has one (skipped while the manifest is empty) |
| **S27** | the client address (§8) | the last entry of the last `X-Forwarded-For` line is read in the five forms of §8 and a client that changes port stays one client; a value that is not an address, or a missing header, falls back to the connection's address; the header is ignored without `SOUNDPITCH_TRUST_PROXY=1`; `SOUNDPITCH_LOG_FORWARDED=1` logs at most five distinct shapes with the digits replaced and never an address |
| **S28** | the page and the synthetic voice (§9) | a stored clip is played with `playbackRate` equal to the effective rate divided by `X-Audio-Rate` and pitch preserved; a response without the header is played at rate 1; the note that the Azure voice is synthetic is visible and describes the Voice control; axe stays clean |
| **S29** | `/api/voice` and the Voice control (§8, §9) | without clips and without a key the server answers zeros and `false`; with clips for one language only that language counts; a manifest entry whose file is missing or empty does not count; a key and a region make `live` true and the key value is never in the answer; the page disables the `azure` option and says so when neither exists, enables it when either does, and goes back to the browser voice when the language changes to one without clips; the default output is `browser`; axe stays clean |
| **S30** | the browser voice (§9) | with no speech synthesis, or no voice for the language of the commentary, Play still plays: the status says that nothing will be spoken aloud and names the other ways to follow the match, the captions and the transcript keep filling and the screen-reader output still announces; with a voice for the language there is no such message |

## §11 Foundry describer (`SOUNDPITCH_LLM=foundry`)

- Settings: `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, and the cost limits of the last bullet (`SOUNDPITCH_LLM_CALLS_PER_MINUTE` 2, `SOUNDPITCH_LLM_CALLS_PER_DAY` 20, `SOUNDPITCH_LLM_TOKENS_PER_DAY` 120000, `SOUNDPITCH_LLM_EUR_PER_MONTH` 2.00, `SOUNDPITCH_USAGE_DB`). Authentication uses the default Azure credential (`az login` locally, a managed identity in Azure). No key in the code or the image. A missing setting, or a missing optional package, stops the request with `503 llm_not_configured` and a message that names it; the other modes need neither.
- Package: `backend/requirements-agents.txt` (Microsoft Agent Framework's `FoundryChatClient`, pinned; D10). The core `requirements.txt`, the tests and the offline modes never import it.
- One model call per attempt covers all pending moments of the window, in chunks of at most 20 (a reply of 20 moments is about 600 tokens; the output cap is 1,000). The call runs on one long-lived event loop owned by the adapter, so the client, its connection and its token are reused and never shared across threads or loops.
- The prompt holds the style rules of §5, the language, and for each moment only: its template key, the player's surname, the team's short name, the canonical phrases of §5 (score, assist clause, chain, lane, zone, direction, minute), the vocabulary of its key, the places a name or a phrase may stand (`verifier.position_contexts`), one or two example sentences made of those same facts, and, on a retry, the verifier's issues for that moment. Nothing else about the match: no other player, no other event, no refs.
- The reply is a JSON object `{items: [{moment_id, full, short}]}` (structured output with a Pydantic model; the text is parsed again whatever the SDK returned). The model never sends refs: the code attaches the refs of `describer.facts`. An item for an unknown moment, a duplicate, or a missing field is dropped; a moment without a valid item is a failed attempt for that moment, as is a reply that does not parse, a call that raises and a call that takes more than 20 s.
- Every wording passes through the pipeline's own verifier and retries (§5), unchanged: valid JSON or a conforming schema never makes a sentence verified.
- Cost guards, outermost first.
  1. *Azure.* The deployment's tokens-per-minute allocation (8,000): a **throughput** ceiling, not a spending limit. The service estimates a request as its prompt (from the characters) plus `max_tokens`, even if unused, and answers 429 above the allocation. And a budget of 5 EUR a month on the resource group, which only **alerts**: cost data arrives 8 to 24 hours late, budgets are evaluated every 24 hours, nothing is stopped. Neither is a cutoff.
  2. *The usage ledger* (`backend/app/usage.py`, SQLite, D11) decides before every model call. It lives in one file (`SOUNDPITCH_USAGE_DB`, default `backend/data/usage.sqlite`) and survives restarts and concurrent threads and processes on the same host. Per UTC period it allows at most `SOUNDPITCH_LLM_CALLS_PER_MINUTE` calls (default 2) in a minute, `SOUNDPITCH_LLM_CALLS_PER_DAY` (default 20) and `SOUNDPITCH_LLM_TOKENS_PER_DAY` (default 120,000) in a day, and an estimated spend of `SOUNDPITCH_LLM_EUR_PER_MONTH` (default 2.00) in a month; the environment may change these, but the monthly ceiling can never be set above 4.00, so it always sits below the 5 EUR budget. Before the call it **reserves** the worst case in one atomic step: the prompt estimated at one token per two characters, the full 1,000 output tokens, three SDK attempts, at the list price **in US dollars** (gpt-4.1-mini Global Standard on 2026-10-20: 0.40 per million input tokens, 1.60 per million output) **counted 1:1 as euros** (a stated policy, not a market rate: it over-counts while a dollar is worth less than a euro) plus a 25% margin, so 0.50 and 2.00 per million tokens. After the call it replaces the reservation with the usage the service reports. A call that fails, times out or is cancelled keeps its worst-case reservation, because it may have been billed; only a call that never left the process is released. Reservations in flight count. If the database cannot be opened, read or written, the call is refused (fail closed).
  3. *Per request.* At most 1,000 output tokens, 20 moments, an estimated prompt of 12,000 tokens, 2 calls in flight.
  A refused call never reaches Azure: the chunk is described by the template describer, the trace says `llm budget exhausted: templates (reason)` and the log gets one line without secrets. Replies that parse are kept in the same database (key: match seed, language, attempt, the moments, the issues sent, a hash of the instructions), so a window asked once is never paid for again, across restarts; identical requests in flight share one call. The API keeps a session only if no model call failed and no budget was exhausted while building it.
  What this does **not** guarantee. The ledger is per host: replicas, or a container disk that is replaced at each deployment, neither share nor keep it (T06 must run one replica with a persistent volume). The estimate is only as good as the price and the token estimate; Azure bills what it processed, which the application sees only through the usage it reports. There is no spending cutoff in Azure for pay-as-you-go: an automatic stop would have to be built (a budget action group calling a function that deletes the deployment) and was not.
- Evidence against the real service: `python -m app.foundry_run --write` runs every preset at every detail level in both languages and writes `docs/evidence/foundry-run.md` (date, model name, first-attempt pass rate, retries, fallbacks, rejection reasons, median and p95 call latency). Without settings it exits 2 and says which are missing.

### Replay mode (`SOUNDPITCH_LLM=replay`), the judges' path (D12)

- The public demo must work for any judge, free and without restriction (rules 4.8), without a live model call and without a datastore. `replay` answers a request with the reply Foundry gave to the *same request* earlier, read from `backend/app/replay_data/foundry_replies.json` (`{version, model, recorded, replies: {key: reply}}`). The key is the one of the reply cache above (match seed, language, attempt, moments, issues, instructions), so a changed prompt, a new window or a retry with new issues has no recorded reply.
- A recorded reply is data, not a verdict. It becomes `Description`s with the code's refs, like a live reply, and the pipeline's verifier checks every session, so a stale, edited or hostile record ends in the template fallback. A request with no recorded reply, and a missing, invalid or unparsable file, are described by the templates and the trace says `no recorded reply: templates`; nothing fails.
- The file is made offline from the replies a live Foundry run stored in the usage ledger: `python -m app.foundry_run` (billable, needs the owner's approval and the raised limits of §11), then `python -m app.replay_export --db <ledger> --model <model> --recorded <date>`; `python -m app.replay_export --check` reports how many requests (preset x detail x language, first attempt) the file covers. Nothing in the replay path contacts Azure, imports the SDK, or writes a file, so it runs as the non-root user of the container and on a read-only file system.
- What it is not. It is not a live model: the words are those of one recorded run, and the evidence of how that model fares is `docs/evidence/foundry-run.md`.

## §12 Agent Framework workflow (`SOUNDPITCH_ORCHESTRATOR=workflow`)

The describe, verify, retry, fallback and timing flow of §5 and §6 is also expressed as a Microsoft Agent Framework workflow: a graph of executors with a conditional retry edge. It builds the same `Session` as the plain pipeline; it adds an orchestration that can be drawn, traced executor by executor and extended, not new behaviour.

| Executor | Kind | Role |
|---|---|---|
| `MomentDetector` | code | the window's events to moments |
| `Describer` | the profile's describer: templates, or a model on Foundry (§11), or recorded replies | pending moments and the verifier's feedback to descriptions; a describer that raises costs an attempt |
| `Verifier` | code | accepts descriptions, or keeps the moments pending with the issues as feedback |
| `Fallback` | code | the verified template description of the moments still pending after the last attempt |
| `TimingPlanner` | code | cues, earcons, ball track and the report; the workflow's output is the `Session` |

Edges: `MomentDetector -> Describer -> Verifier`; `Verifier -> Describer` while moments are pending and attempts < 3 (a conditional edge carrying the feedback); `Verifier -> Fallback` when moments are pending and the attempts are used up; `Verifier -> TimingPlanner` when nothing is pending; `Fallback -> TimingPlanner`.

- `plain` (default) keeps the dependency-free pipeline. `workflow` needs the optional `requirements-agents.txt` and answers `503 llm_not_configured` naming the package when it is missing. The Agent Framework version is pinned (D10, D13).
- The messages between executors are immutable (a frozen dataclass copied at each step): edge conditions are evaluated when a message is delivered, and a message changed by the executor that sent it would make the wrong edge fire (found with the installed version, D13).
- For the same describer both orchestrators return the same cues, statuses and report (`Session.trace` differs: each step of the workflow names its executor in `TraceStep.executor`; the plain pipeline leaves it empty).
- What it is not. The model is not an autonomous agent with tools: code decides what is true and when it is said (§5), so only the `Describer` touches a model and the other executors are deterministic code. The workflow does not make the answers better; it makes the control flow explicit.
- Selection is by the environment at request time. It applies to `/api/session`, `/api/session.vtt` and `/api/cuesheet` alike.

## §13 Cue sheet (machine-readable output)

`GET /api/cuesheet?preset&detail&lang&earcons&calm&rate` returns a `CueSheet`, JSON, for a graphics or captioning system. It is the `Session` of the same parameters (§8) in a flat, versioned shape; it is built from the session, so it carries the same verified words and the same timings.

- Fields: `schema_version` (1), `preset`, `lang`, `match_clock_from` (`mm:ss` of match time at the window start), `duration_ms`, `items`.
- `items` are sorted by `at_ms` (relative to the window start), then `audio_description`, `caption`, `ball_sound`, then `id`. Every item has `id` (a string, unique in the sheet), `type` and `at_ms`.
  - `audio_description` and `caption` add `duration_ms`, `priority` (0..3), `event_ids`, `text` and `status` (`verified` or `fallback`). A `caption` has the same `at_ms`, `duration_ms` and `text` as its `audio_description`; the two items of one cue have ids `ad-{cue id}` and `cap-{cue id}`.
  - `ball_sound` adds `sound` (the kinds of §7), `pan` (-1..1), `pitch` and `gain` (0..1). It has no duration: the player decides how long a sound lasts.
- `audio_description` items never overlap one another.
- The JSON Schema is served at `GET /api/cuesheet.schema.json` and committed as `docs/contracts/cuesheet.v1.schema.json`; both are generated from `contracts.py` (`python -m app.cuesheet --write docs/contracts/cuesheet.v1.schema.json`). The schema is a discriminated union on `type` and forbids unknown fields. The sheet is validated with the Pydantic models that generate the schema; no second validator is a dependency.
- Compatible changes only add optional fields. Any other change increments `schema_version` and the schema file name.

## §14 Azure AI Speech with a real key

- `python -m app.check_speech "Goal! Marsh scores for Northgate."` calls the synthesis function of §8 directly, writes `out.mp3`, prints its size and exits 0; on error it prints the message and exits 1.
- The page's `azure` output plays the audio of each cue, prefetching with at most 3 requests in flight. It is offered only when `/api/voice` says the server has clips for the language or a live key (S29). On `501` it falls back to the browser voice and says so in `status`.
- Voices: `en-GB-RyanNeural`, `it-IT-DiegoNeural`.

## §15 Hosting and cost guards

- One container image serves the page and the API (`Dockerfile`), runs as a non-root user, listens on 8000 and answers `GET /api/health`.
- Target: Azure Container Apps, Consumption only (no Dedicated or Flexible profile, no private endpoint, no planned maintenance), minimum replicas 0, maximum replicas 1, 0.25 vCPU and 0.5 GiB, logs destination none, **until the end of judging (10 Nov 2026, 23:59 Pacific)** (rules 4.8). The public app holds no secret, no Foundry credential and no Speech key (`SOUNDPITCH_LLM=replay`, stored clips): it makes no outbound request and needs no persistence. Fallback if the Environment meters of Azure cannot be explained or controlled: Render Free (`docs/DEPLOY.md`).
- Guards: no live model and no live Speech in the public app; one replica at most; a cost checkpoint after the first day (`docs/DEPLOY.md`); an Azure budget alert (an alert, not a cutoff).
- `python -m app.smoke <base-url>` checks `/api/health`, `/api/presets` and a session for every preset (valid, no overlap, must-say moments present) and exits non-zero otherwise.
- `docs/DEPLOY.md` lists the commands, the resources created and how to delete them.

## §16 MCP server (optional)

`python -m app.mcp_server` exposes the match as read-only MCP tools: `list_presets`, `get_moments(preset, detail)`, `get_session(preset, detail, lang)`. Results are the contract objects of `contracts.py` as JSON. An unknown preset is a tool error with code `preset_not_found`. The describer agent may call `get_moments` instead of receiving facts in its prompt; that must not change what the verifier accepts.

## §17 Player focus (optional)

`Profile.focus` is a shirt number and `Profile.focus_team` its side. With a focus, moments that involve that player (actor or receiver) have their priority raised by one, up to 2 (priority 3 stays reserved for must-say moments), and their earcons have gain x1.5, capped at 1.0. Descriptions do not change. Without a focus nothing changes. An invalid shirt gives `422`.
