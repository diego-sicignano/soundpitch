"""HTTP API and the static one-page UI (SPEC §8, §9)."""

import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app import tts
from app.contracts import (
    Detail,
    ErrorResponse,
    Lang,
    MatchHeader,
    Preset,
    Profile,
    Session,
    TtsRequest,
)
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, build_session, describer_from_env
from app.render import webvtt

app = FastAPI(title="SoundPitch")
MATCH = generate_match(SEED)
PRESETS = {p.id: p for p in build_presets(MATCH)}
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorResponse(code=code, message=message).model_dump())  # type: ignore[arg-type]


@lru_cache(maxsize=256)
def _session(preset_id: str, profile: Profile) -> Session:
    return build_session(MATCH, PRESETS[preset_id], profile, describer_from_env())


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "llm": os.environ.get("SOUNDPITCH_LLM") or "scripted"}


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
    return _session(preset, Profile(detail=detail, lang=lang, earcons=earcons, calm=calm, rate=rate))


@app.get("/api/session", response_model=Session, responses={404: {"model": ErrorResponse}})
def get_session(
    preset: str = "goal_1",
    detail: Detail = "standard",
    lang: Lang = "en",
    earcons: bool = True,
    calm: bool = False,
    rate: float = Query(1.0, ge=0.5, le=2.0),
):
    return _lookup(preset, detail, lang, earcons, calm, rate)


@app.get("/api/session.vtt", responses={404: {"model": ErrorResponse}})
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


@app.post("/api/tts", responses={501: {"model": ErrorResponse}})
def post_tts(request: TtsRequest):
    try:
        audio = tts.synthesize(request.text, request.lang, request.rate)
    except tts.NotConfigured as exc:
        return _error(501, "tts_not_configured", str(exc))
    except tts.RateLimited as exc:
        return _error(429, "rate_limited", str(exc))
    except tts.TtsFailed as exc:
        return _error(502, "tts_failed", str(exc))
    return Response(audio, media_type="audio/mpeg")


if FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
