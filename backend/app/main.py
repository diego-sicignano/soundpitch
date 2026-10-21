"""HTTP API and the static one-page UI (SPEC §8, §9)."""

import ipaddress
import logging
import os
import re
import threading
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app import clips, cuesheet, tts
from app.contracts import (
    CueSheet,
    Detail,
    ErrorResponse,
    Lang,
    MatchHeader,
    Preset,
    Profile,
    Session,
    TtsRequest,
    VoiceSupport,
)
from app.foundry import BUDGET_NOTE, FoundryNotConfigured
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, build_session, describer_from_env, llm_mode
from app.render import webvtt

log = logging.getLogger("soundpitch.api")
app = FastAPI(title="SoundPitch")
MATCH = generate_match(SEED)
PRESETS = {p.id: p for p in build_presets(MATCH)}
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}
# The page has no inline script or style and makes no external request, so nothing is relaxed (SPEC §8, S25).
POLICY = (
    "default-src 'self'; media-src 'self' blob:; img-src 'self' data:; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")  # the interactive documentation loads its own scripts


@app.middleware("http")
async def security_headers(request: Request, call_next):
    _note_forwarded(request)
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error on %s", request.url.path)
        response = _error(500, "internal_error", "Internal server error")
    response.headers.update(HEADERS)
    if not request.url.path.startswith(DOCS_PATHS):
        response.headers["Content-Security-Policy"] = POLICY
    return response


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorResponse(code=code, message=message).model_dump())  # type: ignore[arg-type]


SESSIONS: OrderedDict[tuple[str, Profile, str], Session] = OrderedDict()
SESSIONS_LOCK = threading.Lock()
SESSIONS_KEPT = 256


def _keepable(session: Session) -> bool:
    """A session built during an outage or over the model's call cap is not kept: it would stay a
    template session after the service is back. The sessions of a healthy model are, as before."""
    return not any(
        step.step == "describer" and (step.status == "failed" or BUDGET_NOTE in step.detail)
        for step in session.trace
    )


def _builder(mode: str):
    """`plain` is the dependency-free pipeline, `workflow` the same steps as an Agent Framework workflow (§12)."""
    if mode == "plain":
        return build_session
    if mode == "workflow":
        from app import (
            workflow,  # the optional framework is imported only when its session is built
        )

        return workflow.build_session
    raise FoundryNotConfigured("SOUNDPITCH_ORCHESTRATOR is not a supported mode (use plain or workflow)")  # never the value


def _session(preset_id: str, profile: Profile) -> Session:
    mode = os.environ.get("SOUNDPITCH_ORCHESTRATOR") or "plain"
    key = (preset_id, profile, mode)
    with SESSIONS_LOCK:
        if key in SESSIONS:
            SESSIONS.move_to_end(key)
            return SESSIONS[key]
    session = _builder(mode)(MATCH, PRESETS[preset_id], profile, describer_from_env())
    if _keepable(session):
        with SESSIONS_LOCK:
            SESSIONS[key] = session
            while len(SESSIONS) > SESSIONS_KEPT:
                SESSIONS.popitem(last=False)
    return session


_session.cache_clear = SESSIONS.clear  # type: ignore[attr-defined]


@app.get("/api/health", response_model=None, responses={503: {"model": ErrorResponse}})
def health() -> dict[str, str | int] | JSONResponse:
    try:
        mode = llm_mode()
    except FoundryNotConfigured as exc:  # a mistyped setting is not healthy: fail closed, never echo the value
        return _error(503, "llm_not_configured", str(exc))
    if mode == "replay":  # how many recorded model replies this server holds: 0 means the templates speak
        from app.replay import shared_replay

        return {"status": "ok", "llm": mode, "replies": len(shared_replay().store.replies)}
    return {"status": "ok", "llm": mode}


@app.get("/api/match", response_model=MatchHeader)
def get_match() -> MatchHeader:
    last = MATCH.events[-1]
    return MatchHeader(
        seed=MATCH.seed,
        home=MATCH.home,
        away=MATCH.away,
        home_goals=last.home_score,
        away_goals=last.away_score,
        goals=[e for e in MATCH.events if e.kind == "goal"],
    )


@app.get("/api/presets", response_model=list[Preset])
def get_presets() -> list[Preset]:
    return list(PRESETS.values())


def _lookup(
    preset: str, detail: Detail, lang: Lang, earcons: bool, calm: bool, rate: float
) -> Session | JSONResponse:
    if preset not in PRESETS:
        return _error(404, "preset_not_found", f"Unknown preset: {preset}")
    try:
        session = _session(preset, Profile(detail=detail, lang=lang, earcons=earcons, calm=calm, rate=rate))
    except FoundryNotConfigured as exc:
        return _error(503, "llm_not_configured", str(exc))
    tts.issue(session.lang, (cue.text for cue in session.cues))  # only returned text can be spoken (S22)
    return session


@app.get(
    "/api/session",
    response_model=Session,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_session(
    preset: str = "goal_1",
    detail: Detail = "standard",
    lang: Lang = "en",
    earcons: bool = True,
    calm: bool = False,
    rate: float = Query(1.0, ge=0.5, le=2.0),
):
    return _lookup(preset, detail, lang, earcons, calm, rate)


@app.get("/api/session.vtt", responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def get_session_vtt(
    preset: str = "goal_1",
    detail: Detail = "standard",
    lang: Lang = "en",
    earcons: bool = True,
    calm: bool = False,
    rate: float = Query(1.0, ge=0.5, le=2.0),
):
    session = _lookup(preset, detail, lang, earcons, calm, rate)
    if isinstance(session, JSONResponse):
        return session
    return Response(webvtt(session.cues), media_type="text/vtt")


def _address_of(entry: str) -> str | None:
    """The address in one X-Forwarded-For entry, whatever form the proxy wrote it in: `1.2.3.4`, `1.2.3.4:5678`,
    `[2001:db8::1]:5678`, `2001:db8::1` or `[2001:db8::1]`. None if it is not an address."""
    entry = entry.strip()
    if entry.startswith("["):
        if "]" not in entry:
            return None
        host = entry[1:].split("]", 1)[0]
    elif entry.count(":") == 1:
        host = entry.split(":", 1)[0]
    else:
        host = entry
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None


def _client_id(request: Request) -> str:
    """The caller's address: the last entry of the last X-Forwarded-For line when a trusted proxy wrote it
    (SOUNDPITCH_TRUST_PROXY=1), else the connection's address. Anything that is not an address falls back too."""
    if os.environ.get("SOUNDPITCH_TRUST_PROXY") == "1":
        lines = request.headers.getlist("x-forwarded-for")
        if lines:
            address = _address_of(lines[-1].rsplit(",", 1)[-1])
            if address:
                return address
    return request.client.host if request.client else "unknown"


SHAPES: set[str] = set()


def _note_forwarded(request: Request) -> None:
    """With SOUNDPITCH_LOG_FORWARDED=1, log the shape of X-Forwarded-For (digits as 9, hex letters as x), never an
    address, for up to five distinct shapes: enough to settle how a real proxy writes it."""
    if os.environ.get("SOUNDPITCH_LOG_FORWARDED") != "1" or len(SHAPES) >= 5:
        return
    for line in request.headers.getlist("x-forwarded-for"):
        shape = re.sub(r"[^ -~]", "?", re.sub(r"[0-9]", "9", re.sub(r"[a-fA-F]", "x", line)))[:60]
        if shape not in SHAPES and len(SHAPES) < 5:
            SHAPES.add(shape)
            log.warning("X-Forwarded-For shape: %s", shape)  # a warning: no logging is configured, so INFO would not show


@app.get(
    "/api/cuesheet",
    response_model=CueSheet,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_cuesheet(
    preset: str = "goal_1",
    detail: Detail = "standard",
    lang: Lang = "en",
    earcons: bool = True,
    calm: bool = False,
    rate: float = Query(1.0, ge=0.5, le=2.0),
):
    session = _lookup(preset, detail, lang, earcons, calm, rate)
    if isinstance(session, JSONResponse):
        return session
    return cuesheet.build(session, PRESETS[preset])


@app.get("/api/cuesheet.schema.json")
def get_cuesheet_schema() -> JSONResponse:
    return JSONResponse(cuesheet.schema())


@app.get("/api/voice", response_model=VoiceSupport)
def get_voice() -> VoiceSupport:
    """What the Azure voice can do here, so the page offers only a voice that exists (S29)."""
    stored = clips.store()
    return VoiceSupport(stored_clips={lang: stored.count(lang) for lang in clips.LANGS}, live=tts.live_configured())  # type: ignore[misc]


@app.post("/api/tts", responses={501: {"model": ErrorResponse}})
def post_tts(request: Request, body: TtsRequest):
    try:
        audio = tts.synthesize(body.text, body.lang, body.rate, _client_id(request))
    except tts.NotConfigured as exc:
        return _error(501, "tts_not_configured", str(exc))
    except tts.NotIssued as exc:
        return _error(403, "tts_text_not_issued", str(exc))
    except tts.RateLimited as exc:
        return _error(429, "rate_limited", str(exc))
    except tts.TtsFailed as exc:
        return _error(502, "tts_failed", str(exc))
    return Response(audio.data, media_type="audio/mpeg", headers={"X-Audio-Rate": f"{audio.rate:g}"})


if FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
