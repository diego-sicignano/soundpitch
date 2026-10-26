"use strict";

// SoundPitch player. One page, no build step. The server decides what is said and when;
// this file only plays the plan: speech, ball sound, captions, a pitch and a timeline.

const $ = (id) => document.getElementById(id);
const query = new URLSearchParams(location.search);
const SPEED = Number(query.get("speed")) || 1; // clock multiplier, for demos and tests
const SPEECH_OFF = query.get("speech") === "off";

const state = { match: null, presets: [], session: null, playing: false, clock: 0, last: 0, cue: 0, ear: 0, stats: -1 };
// A timer, not requestAnimationFrame: browsers pause animation frames in a background tab, which would stop the
// commentary for a listener who switches tabs (a background timer still runs, about once a second).
const TICK_MS = 50;
let timer = 0;
let audioContext = null;
let currentAudio = null;
let audioByCue = new Map();
let loadToken = 0;
let voiceSupport = null; // GET /api/voice: what the Azure voice can do on this server (S29)
const VOICE_NOTE = $("voice-note").textContent;
const LANGUAGE_NAME = { en: "English", it: "Italian" };
const ROLE_NAME = { gk: "goalkeeper", def: "defender", mid: "midfielder", fwd: "forward" };
const STATS_ROWS = [
  ["possession", "Possession", (s) => `${s.possession}%`],
  ["recent_possession", "Possession, last 5 minutes", (s) => `${s.recent_possession}%`],
  ["passes", "Passes completed", (s) => `${s.passes_completed} of ${s.passes}`],
  ["pass_accuracy", "Pass accuracy", (s) => `${s.pass_accuracy}%`],
  ["avg_pass_m", "Average pass", (s) => `${s.avg_pass_m.toFixed(1)} m`],
  ["shots", "Shots", (s) => String(s.shots)],
  ["shots_on_target", "Shots on target", (s) => String(s.shots_on_target)],
  ["ball_won", "Balls won", (s) => String(s.ball_won)],
];

const clockText = (seconds) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
const say = (text) => ($("status").textContent = text);

function settingsQuery() {
  const params = new URLSearchParams({
    preset: $("preset").value,
    detail: $("detail").value,
    lang: $("lang").value,
    earcons: $("toggle-earcons").checked,
    calm: $("toggle-calm").checked,
    rate: $("rate").value,
  });
  if ($("focus").value) {
    const [team, shirt] = $("focus").value.split(":"); // "home" for a club, "home:7" for a player
    params.set("focus_team", team);
    if (shirt) params.set("focus", shirt);
  }
  return params;
}

// "Follow" (SPEC §17): each club, then its players.
function offerPlayers(match) {
  const groups = [match.home, match.away].map((team) => {
    const group = document.createElement("optgroup");
    group.label = team.name;
    group.append(new Option(`${team.name}, the whole team`, team.side));
    group.append(...team.players.map((p) => new Option(`${p.name}, ${ROLE_NAME[p.role]}, number ${p.shirt}`, `${team.side}:${p.shirt}`)));
    return group;
  });
  $("focus").append(...groups);
}

// Match stats (SPEC §18): one row per statistic, one column per team; the values follow the clock.
function renderStats() {
  $("stats-home").textContent = state.match.home.short;
  $("stats-away").textContent = state.match.away.short;
  $("stats-body").replaceChildren(
    ...STATS_ROWS.map(([field, label]) => {
      const row = document.createElement("tr");
      const name = document.createElement("th");
      name.scope = "row";
      name.textContent = label;
      const cells = ["home", "away"].map((side) => {
        const cell = document.createElement("td");
        cell.id = `stats-${field}-${side}`;
        cell.setAttribute("data-testid", cell.id);
        return cell;
      });
      row.append(name, ...cells);
      return row;
    }),
  );
  state.stats = -1;
}

function drawStats() {
  const points = state.session.stats;
  let index = 0;
  while (index + 1 < points.length && points[index + 1].t_ms <= state.clock) index++;
  if (index === state.stats) return;
  state.stats = index;
  for (const [field, , format] of STATS_ROWS) {
    for (const side of ["home", "away"]) $(`stats-${field}-${side}`).textContent = format(points[index][side]);
  }
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${url} answered ${response.status}`);
  return response.json();
}

async function init() {
  try {
    const [match, presets, voice] = await Promise.all([
      getJson("/api/match"),
      getJson("/api/presets"),
      getJson("/api/voice").catch(() => null), // unknown: the Azure option stays offered, and a 501 falls back to the browser voice
    ]);
    state.match = match;
    state.presets = presets;
    voiceSupport = voice;
    // the neural voice by default where the server holds its clips (SPEC §9); else the browser's own voice
    if (voice && voice.stored_clips[$("lang").value] > 0) $("output").value = "azure";
    if (window.speechSynthesis) window.speechSynthesis.getVoices(); // some browsers load their voices only after this call
    $("preset").replaceChildren(...presets.map((p) => new Option(p.title, p.id)));
    offerPlayers(match);
    $("preset").value = query.get("preset") || "goal_1";
    if (!$("preset").value) $("preset").value = "goal_1"; // an unknown ?preset= falls back to the first goal
    await loadSession();
  } catch (error) {
    say("The match could not be loaded. Is the server running?");
  }
}

// The controls are English, the commentary is in the chosen language: mark it so a screen reader
// switches voice (WCAG 3.1.2). The page language stays that of the controls.
function markLanguage(lang) {
  for (const id of ["transcript", "captions", "live-region"]) $(id).setAttribute("lang", lang);
}

// The Azure voice is offered only where the server can speak it: a stored clip for this language or a live key.
// Returns a sentence when the choice had to go back to the browser voice.
function offerVoices() {
  const lang = $("lang").value;
  const available = !voiceSupport || voiceSupport.live || voiceSupport.stored_clips[lang] > 0;
  $("output").querySelector('option[value="azure"]').disabled = !available;
  $("voice-note").textContent = available
    ? VOICE_NOTE
    : "The Azure neural voice is not available on this server for this language. Use the browser voice or your own screen reader.";
  if (available || $("output").value !== "azure") return "";
  $("output").value = "browser";
  return `The Azure voice is not available in ${LANGUAGE_NAME[lang]}, so the browser voice is used.`;
}

async function loadSession() {
  const token = ++loadToken;
  stop();
  $("play").textContent = "Play";
  $("play").disabled = true; // a click now would play the old settings' session
  const voiceChanged = offerVoices();
  const restarted = state.session && state.clock > 0 ? " It starts again from the beginning." : "";
  say("Preparing the commentary");
  let session;
  try {
    session = await getJson(`/api/session?${settingsQuery()}`);
  } catch (error) {
    if (token === loadToken) {
      state.session = null; // never play the old settings' session under the new ones
      $("play").disabled = false;
    }
    say("The commentary could not be prepared.");
    return;
  }
  if (token !== loadToken) return; // a newer request replaced this one
  state.session = session;
  markLanguage(session.lang);
  state.clock = 0;
  state.cue = 0;
  state.ear = 0;
  audioByCue = new Map();
  $("transcript").replaceChildren();
  $("summary").hidden = true; // shown only once the clip has finished: it would tell what is about to happen
  $("captions").textContent = "";
  $("live-region").textContent = "";
  renderTimeline();
  renderReport();
  renderStats();
  draw();
  $("play").textContent = "Play";
  $("play").disabled = false;
  say(`Ready: ${session.title}. ${session.cues.length} descriptions.${restarted} ${voiceChanged}`.trim());
  if ($("output").value === "azure" && !SPEECH_OFF) prefetchAzure(session, token);
}

// --- timeline, report ------------------------------------------------------------------

function renderTimeline() {
  const { cues, duration_ms: duration } = state.session;
  const blocks = cues.map((cue) => {
    const block = document.createElement("div");
    block.className = `block${cue.priority === 3 ? " must" : ""}${cue.status === "fallback" ? " fallback" : ""}`;
    block.setAttribute("data-testid", `timeline-cue-${cue.id}`);
    block.style.left = `${(cue.start_ms / duration) * 100}%`;
    block.style.width = `${((cue.end_ms - cue.start_ms) / duration) * 100}%`;
    block.title = cue.text;
    return block;
  });
  $("timeline").replaceChildren(...blocks, $("playhead"));
}

function renderReport() {
  const { report, trace } = state.session;
  const speechShare = Math.round((report.speech_ms / (report.speech_ms + report.silence_ms)) * 100);
  const rows = [
    ["Described", report.cues],
    ["Verified", report.verified],
    ["Template fallback", report.fallback],
    ["Attempts", report.attempts],
    ["Left out", report.dropped],
    ["Overlaps", report.overlaps],
    ["Speaking", `${speechShare}%`],
  ];
  const passed = report.verified === report.cues;
  $("report-summary").textContent = passed
    ? `All ${report.cues} ${report.cues === 1 ? "description" : "descriptions"} passed the check as written.`
    : `${report.verified} of ${report.cues} descriptions passed the check as written; ${report.fallback} ${report.fallback === 1 ? "was" : "were"} replaced by a template that always passes.`;
  $("report").replaceChildren(
    ...rows.map(([name, value]) => {
      const row = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = name;
      dd.textContent = value;
      row.append(dt, dd);
      return row;
    }),
  );
  $("trace").replaceChildren(
    ...trace.map((step) => {
      const li = document.createElement("li");
      const by = step.executor ? `${step.executor} (Agent Framework executor): ` : ""; // SPEC §12
      li.textContent = `${by}${step.step}, attempt ${step.attempt}: ${step.status}, ${step.detail}`;
      return li;
    }),
  );
}

// --- drawing the pitch, score and playhead ---------------------------------------------

function draw() {
  const { session } = state;
  if (!session) return;
  let point = null;
  for (const candidate of session.track) {
    if (candidate.t_ms > state.clock) break;
    point = candidate;
  }
  const home = point ? point.home_score : session.start_home_score;
  const away = point ? point.away_score : session.start_away_score;
  $("scoreline").textContent = `${state.match.home.short} ${home} – ${away} ${state.match.away.short}`;
  const first = session.track[0];
  const at = point || first;
  if (at) {
    $("ball").setAttribute("cx", String((at.x / 100) * 105));
    $("ball").setAttribute("cy", String((at.y / 100) * 68));
  }
  $("playhead").style.left = `${Math.min(100, (state.clock / session.duration_ms) * 100)}%`;
  const preset = state.presets.find((p) => p.id === session.preset);
  if (preset) $("match-clock").textContent = `Match time ${clockText(preset.from_s + state.clock / 1000)}`;
  drawStats();
}

// --- output ----------------------------------------------------------------------------

function effectiveRate() {
  const rate = Number($("rate").value);
  return $("toggle-calm").checked ? Math.min(rate, 0.9) : rate;
}

function announce(text) {
  const region = $("live-region");
  region.textContent = "";
  setTimeout(() => (region.textContent = text), TICK_MS); // a frame callback would wait while the tab is hidden
}

// Says honestly when the browser voice cannot speak (S30): the captions, the transcript and the screen-reader output remain.
function browserVoiceProblem() {
  const advice = "Read the captions and the transcript, or choose “My own screen reader (text only)” under Voice.";
  if (!window.speechSynthesis) return `This browser cannot speak aloud. ${advice}`;
  const lang = state.session.lang;
  if (!window.speechSynthesis.getVoices().some((voice) => voice.lang.toLowerCase().startsWith(lang))) {
    return `This browser reports no ${LANGUAGE_NAME[lang]} voice, so nothing may be spoken aloud. ${advice}`;
  }
  return "";
}

function browserSpeak(text) {
  if (!("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = state.session.lang === "it" ? "it-IT" : "en-GB";
  utterance.rate = effectiveRate();
  window.speechSynthesis.speak(utterance);
}

async function fetchAzure(cue) {
  const response = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: cue.text, lang: state.session.lang, rate: effectiveRate() }),
  });
  if (response.status === 501) {
    $("output").value = "browser";
    say("Azure voice is not configured on this server. Using the browser voice.");
    return null;
  }
  if (!response.ok) return null;
  const blob = await response.blob();
  // A stored clip is at normal speed (X-Audio-Rate: 1) and is sped up here; a live clip already has the speed.
  const audioRate = Number(response.headers.get("X-Audio-Rate"));
  blob.playbackFactor = audioRate > 0 ? effectiveRate() / audioRate : 1;
  return blob;
}

function prefetchAzure(session, token) {
  const queue = [...session.cues];
  const worker = async () => {
    while (queue.length && token === loadToken && $("output").value === "azure") {
      const cue = queue.shift();
      audioByCue.set(cue.id, fetchAzure(cue).catch(() => null));
      await audioByCue.get(cue.id);
    }
  };
  for (let i = 0; i < 3; i++) worker(); // three requests at a time
}

async function speak(cue) {
  const output = $("output").value;
  if (output === "screenreader") return announce(cue.text);
  if (SPEECH_OFF) return;
  if (output === "azure") {
    const token = loadToken;
    const blob = await (audioByCue.get(cue.id) || fetchAzure(cue).catch(() => null));
    if (token !== loadToken || !state.playing) return; // paused or reloaded while the clip was fetched
    if (blob) {
      currentAudio = new Audio(URL.createObjectURL(blob));
      currentAudio.onended = (event) => URL.revokeObjectURL(event.target.src);
      currentAudio.preservesPitch = true;
      currentAudio.playbackRate = blob.playbackFactor || 1;
      return currentAudio.play().catch(() => browserSpeak(cue.text));
    }
  }
  browserSpeak(cue.text);
}

// Ball sound: stereo position follows the ball, pitch rises towards the opponent's goal.
function earcon(sound) {
  if (!audioContext || SPEECH_OFF) return;
  const now = audioContext.currentTime;
  const base = 330 + sound.pitch * 440;
  const voices = {
    tick: [[base, 0.04, "sine"]],
    turnover: [[base, 0.05, "triangle"], [base * 0.75, 0.07, "triangle"]],
    shot: [[base, 0.08, "sawtooth"], [base * 1.5, 0.1, "sawtooth"]],
    save: [[180, 0.18, "triangle"]],
    goal: [[523, 0.18, "sine"], [659, 0.18, "sine"], [784, 0.3, "sine"]],
    set_piece: [[300, 0.12, "square"]],
    whistle: [[2800, 0.15, "sine"]],
    whistle_long: [[2800, 0.55, "sine"]],
  }[sound.kind];
  let offset = 0;
  for (const [frequency, length, type] of voices) {
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    const panner = audioContext.createStereoPanner();
    oscillator.type = type;
    oscillator.frequency.value = frequency;
    panner.pan.value = sound.pan;
    gain.gain.setValueAtTime(0.0001, now + offset);
    gain.gain.exponentialRampToValueAtTime(0.4 * sound.gain, now + offset + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + length);
    oscillator.connect(gain).connect(panner).connect(audioContext.destination);
    oscillator.start(now + offset);
    oscillator.stop(now + offset + length + 0.02);
    offset += length * 0.9;
  }
}

function show(cue) {
  const item = document.createElement("li");
  item.setAttribute("data-testid", `transcript-cue-${cue.id}`);
  const preset = state.presets.find((p) => p.id === state.session.preset);
  const time = document.createElement("span");
  time.className = "time";
  time.lang = "en"; // interface words (the clock, the badge) are not part of the commentary
  time.textContent = clockText(preset.from_s + cue.start_ms / 1000);
  const text = document.createElement("span");
  text.lang = state.session.lang;
  text.className = "cue-text";
  const badges = document.createElement("span");
  badges.className = "badges";
  const badge = document.createElement("span");
  badge.className = `badge${cue.status === "fallback" ? " fallback" : ""}`;
  badge.lang = "en";
  badge.textContent = cue.status === "verified" ? "checked" : "template";
  badges.append(badge);
  if (cue.context && cue.text.endsWith(cue.context)) {
    // the closing sentence is written by code from the score, not by the describer: keep it apart (SPEC §5, S31)
    const context = document.createElement("span");
    context.className = "context";
    context.setAttribute("data-testid", `transcript-context-${cue.id}`);
    context.textContent = cue.context;
    text.append(cue.text.slice(0, cue.text.length - cue.context.length), context);
    const note = document.createElement("span");
    note.className = "badge context-badge";
    note.lang = "en";
    note.textContent = "score context";
    badges.append(note);
  } else {
    text.textContent = cue.text;
  }
  item.append(time, text, badges);
  const scroller = $("transcript").parentElement;
  const atBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 40; // measured before the new line
  $("transcript").append(item);
  if (atBottom) scroller.scrollTop = scroller.scrollHeight; // do not pull away a reader who scrolled back
  if ($("toggle-captions").checked) $("captions").textContent = cue.text;
}

// --- clock -----------------------------------------------------------------------------

function tick(now) {
  if (!state.playing) return;
  state.clock += (now - state.last) * SPEED;
  state.last = now;
  const { cues, earcons, duration_ms: duration } = state.session;
  while (state.ear < earcons.length && earcons[state.ear].t_ms <= state.clock) earcon(earcons[state.ear++]);
  while (state.cue < cues.length && cues[state.cue].start_ms <= state.clock) {
    const cue = cues[state.cue++];
    show(cue);
    speak(cue);
  }
  draw();
  if (state.clock >= duration) return finish();
  schedule();
}

function schedule() {
  clearTimeout(timer); // one clock loop, however fast Play and Pause are pressed
  timer = setTimeout(() => tick(performance.now()), TICK_MS);
}

function play() {
  if (!state.session) {
    say("Nothing to play yet: the commentary is not ready. Change a setting to try again.");
    return;
  }
  if (state.clock >= state.session.duration_ms) {
    state.clock = 0;
    state.cue = 0;
    state.ear = 0;
    $("transcript").replaceChildren();
    $("captions").textContent = "";
    $("summary").hidden = true;
  }
  if (!audioContext && !SPEECH_OFF && window.AudioContext) audioContext = new AudioContext();
  if (audioContext && audioContext.state === "suspended") audioContext.resume();
  if (window.speechSynthesis) window.speechSynthesis.resume();
  if (currentAudio && !currentAudio.ended) currentAudio.play().catch(() => {}); // an ended clip would start again
  state.playing = true;
  state.last = performance.now();
  $("play").textContent = "Pause";
  const problem = $("output").value === "browser" && !SPEECH_OFF ? browserVoiceProblem() : "";
  say(problem ? `Playing. ${problem}` : "Playing");
  schedule();
}

function pause() {
  state.playing = false;
  if (window.speechSynthesis) window.speechSynthesis.pause();
  if (currentAudio) currentAudio.pause();
  $("play").textContent = "Play";
  say("Paused");
}

function stop() {
  state.playing = false;
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  if (currentAudio) currentAudio.pause();
}

function finish() {
  state.playing = false;
  $("play").textContent = "Play again";
  say("The clip has finished.");
  showSummary();
}

// The code-written summary of the match so far (SPEC §19): shown, and heard, once the clip has finished.
function showSummary() {
  const { lines, lang } = state.session.recap;
  $("summary-lines").setAttribute("lang", lang);
  $("summary-lines").replaceChildren(
    ...lines.map((line, n) => {
      const item = document.createElement("li");
      item.setAttribute("data-testid", `summary-line-${n + 1}`);
      item.textContent = line;
      return item;
    }),
  );
  const { analysis } = state.session;
  $("analysis-by").textContent =
    analysis.by === "model"
      ? "Written by an AI agent on Microsoft Foundry; every name and number was checked against the line it cites."
      : "Written by code from the summary.";
  $("analysis-points").setAttribute("lang", lang);
  $("analysis-points").replaceChildren(
    ...analysis.points.map((point, n) => {
      const item = document.createElement("li");
      item.setAttribute("data-testid", `analysis-point-${n + 1}`);
      item.textContent = point.text;
      return item;
    }),
  );
  $("summary").hidden = false;
  // code points repeat the summary, so only the agent's points are heard after it
  const heard = analysis.by === "model" ? ["Studio analysis.", ...analysis.points.map((p) => p.text)] : [];
  const text = [...lines, ...heard].join(" ");
  if ($("output").value === "screenreader") announce(text);
  else if ($("output").value === "azure" && !SPEECH_OFF) speakClips([...lines, ...heard.slice(1)]);
  else if (!SPEECH_OFF) browserSpeak(text);
}

// The Azure voice reads the summary one stored clip per line (each line is issued text, SPEC §8).
async function speakClips(lines) {
  const token = loadToken;
  for (const line of lines) {
    const blob = await fetchAzure({ text: line }).catch(() => null);
    if (token !== loadToken || state.playing) return; // reloaded, or the match was started again
    if (!blob) return browserSpeak(lines.slice(lines.indexOf(line)).join(" "));
    currentAudio = new Audio(URL.createObjectURL(blob));
    currentAudio.preservesPitch = true;
    currentAudio.playbackRate = blob.playbackFactor || 1;
    await new Promise((done) => {
      currentAudio.onended = (event) => {
        URL.revokeObjectURL(event.target.src);
        done();
      };
      currentAudio.play().catch(done);
    });
  }
}

// --- wiring ----------------------------------------------------------------------------

$("play").addEventListener("click", () => (state.playing ? pause() : play()));
document.addEventListener("keydown", (event) => {
  if (event.code !== "Space" || event.repeat) return;
  if (["INPUT", "SELECT", "TEXTAREA", "BUTTON", "SUMMARY"].includes(event.target.tagName)) return;
  if (event.target.closest(".scroller")) return; // Space scrolls the transcript there
  event.preventDefault();
  $("play").click();
});
// An inline onsubmit is blocked by the page's content security policy, so Enter in a field would reload the page.
$("settings").addEventListener("submit", (event) => event.preventDefault());
for (const id of ["preset", "detail", "focus", "lang", "toggle-earcons", "toggle-calm"]) {
  $(id).addEventListener("change", loadSession);
}
$("rate").addEventListener("input", () => ($("rate-value").textContent = Number($("rate").value).toFixed(1)));
$("rate").addEventListener("change", loadSession);
$("output").addEventListener("change", loadSession);
$("toggle-captions").addEventListener("change", () => {
  if (!$("toggle-captions").checked) $("captions").textContent = "";
});

init();
