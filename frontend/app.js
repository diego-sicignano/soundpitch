"use strict";

// SoundPitch player. One page, no build step. The server decides what is said and when;
// this file only plays the plan: speech, ball sound, captions, a pitch and a timeline.

const $ = (id) => document.getElementById(id);
const query = new URLSearchParams(location.search);
const SPEED = Number(query.get("speed")) || 1; // clock multiplier, for demos and tests
const SPEECH_OFF = query.get("speech") === "off";

const state = { match: null, presets: [], session: null, playing: false, clock: 0, last: 0, cue: 0, ear: 0 };
let audioContext = null;
let currentAudio = null;
let audioByCue = new Map();
let loadToken = 0;

const clockText = (seconds) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
const say = (text) => ($("status").textContent = text);

function settingsQuery() {
  return new URLSearchParams({
    preset: $("preset").value,
    detail: $("detail").value,
    lang: $("lang").value,
    earcons: $("toggle-earcons").checked,
    calm: $("toggle-calm").checked,
    rate: $("rate").value,
  });
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${url} answered ${response.status}`);
  return response.json();
}

async function init() {
  try {
    const [match, presets] = await Promise.all([getJson("/api/match"), getJson("/api/presets")]);
    state.match = match;
    state.presets = presets;
    $("preset").replaceChildren(...presets.map((p) => new Option(p.title, p.id)));
    $("preset").value = query.get("preset") || "goal_1";
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

async function loadSession() {
  const token = ++loadToken;
  stop();
  say("Preparing the commentary");
  let session;
  try {
    session = await getJson(`/api/session?${settingsQuery()}`);
  } catch (error) {
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
  $("captions").textContent = "";
  $("live-region").textContent = "";
  renderTimeline();
  renderReport();
  draw();
  $("play").textContent = "Play";
  say(`Ready: ${session.title}. ${session.cues.length} descriptions.`);
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
      li.textContent = `${step.step}, attempt ${step.attempt}: ${step.status}, ${step.detail}`;
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
}

// --- output ----------------------------------------------------------------------------

function effectiveRate() {
  const rate = Number($("rate").value);
  return $("toggle-calm").checked ? Math.min(rate, 0.9) : rate;
}

function announce(text) {
  const region = $("live-region");
  region.textContent = "";
  requestAnimationFrame(() => (region.textContent = text));
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
  [worker(), worker(), worker()];
}

async function speak(cue) {
  const output = $("output").value;
  if (output === "screenreader") return announce(cue.text);
  if (SPEECH_OFF) return;
  if (output === "azure") {
    const blob = await (audioByCue.get(cue.id) || fetchAzure(cue).catch(() => null));
    if (blob) {
      currentAudio = new Audio(URL.createObjectURL(blob));
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
  text.textContent = cue.text;
  const badge = document.createElement("span");
  badge.className = `badge${cue.status === "fallback" ? " fallback" : ""}`;
  badge.lang = "en";
  badge.textContent = cue.status === "verified" ? "checked" : "template";
  item.append(time, text, badge);
  $("transcript").append(item);
  const scroller = $("transcript").parentElement;
  scroller.scrollTop = scroller.scrollHeight;
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
  requestAnimationFrame(tick);
}

function play() {
  if (!state.session) return;
  if (state.clock >= state.session.duration_ms) {
    state.clock = 0;
    state.cue = 0;
    state.ear = 0;
    $("transcript").replaceChildren();
  }
  if (!audioContext && !SPEECH_OFF && window.AudioContext) audioContext = new AudioContext();
  if (audioContext && audioContext.state === "suspended") audioContext.resume();
  if (window.speechSynthesis) window.speechSynthesis.resume();
  if (currentAudio) currentAudio.play().catch(() => {});
  state.playing = true;
  state.last = performance.now();
  $("play").textContent = "Pause";
  say("Playing");
  requestAnimationFrame(tick);
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
}

// --- wiring ----------------------------------------------------------------------------

$("play").addEventListener("click", () => (state.playing ? pause() : play()));
document.addEventListener("keydown", (event) => {
  if (event.code !== "Space" || event.repeat) return;
  if (["INPUT", "SELECT", "TEXTAREA", "BUTTON", "SUMMARY"].includes(event.target.tagName)) return;
  event.preventDefault();
  $("play").click();
});
for (const id of ["preset", "detail", "lang", "toggle-earcons", "toggle-calm"]) {
  $(id).addEventListener("change", loadSession);
}
$("rate").addEventListener("input", () => ($("rate-value").textContent = Number($("rate").value).toFixed(1)));
$("rate").addEventListener("change", loadSession);
$("output").addEventListener("change", loadSession);
$("toggle-captions").addEventListener("change", () => {
  if (!$("toggle-captions").checked) $("captions").textContent = "";
});

init();
