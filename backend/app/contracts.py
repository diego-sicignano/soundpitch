"""Wire contracts for SoundPitch (SPEC §3-§8). Every model rejects unknown fields."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Team = Literal["home", "away"]
Lane = Literal["left", "centre", "right"]
Lang = Literal["en", "it"]
Detail = Literal["essential", "standard", "full"]
Role = Literal["gk", "def", "mid", "fwd"]
Kind = Literal[
    "kickoff",
    "pass",
    "dribble",
    "long_ball",
    "clearance",
    "tackle",
    "interception",
    "foul",
    "free_kick",
    "throw_in",
    "corner",
    "shot_on_target",
    "shot_off_target",
    "shot_blocked",
    "save",
    "goal",
    "halftime",
    "fulltime",
]
MomentKind = Literal[
    "kickoff",
    "goal",
    "halftime",
    "fulltime",
    "shot",
    "save",
    "corner",
    "free_kick",
    "turnover",
    "foul",
    "throw_in",
    "buildup",
    "score_update",
]


class Player(Contract):
    shirt: int
    name: str
    role: Role


class TeamInfo(Contract):
    side: Team
    name: str
    short: str
    players: list[Player]


class Event(Contract):
    id: int
    t: int  # seconds since kickoff, 0..5399
    minute: int  # 1..90
    half: Literal[1, 2]
    team: Team | None
    player: int | None  # shirt of the actor
    target: int | None  # shirt of the receiver, same team
    kind: Kind
    x: int = Field(ge=0, le=100)
    y: int = Field(ge=0, le=100)
    lane: Lane | None
    home_score: int
    away_score: int


class Match(Contract):
    seed: int
    home: TeamInfo
    away: TeamInfo
    events: list[Event]


class Moment(Contract):
    id: int
    t: int  # seconds, when the moment is complete
    priority: int = Field(ge=0, le=3)
    kind: MomentKind
    team: Team | None
    event_ids: list[int]


class FactRef(Contract):
    event_id: int
    field: Literal["team", "player", "target", "kind", "lane", "minute", "home_score", "away_score"]
    value: str | int | None


class Description(Contract):
    moment_id: int
    lang: Lang
    full: str
    short: str
    refs: list[FactRef]


class Profile(Contract):
    detail: Detail = "standard"
    lang: Lang = "en"
    earcons: bool = True
    calm: bool = False
    rate: float = Field(default=1.0, ge=0.5, le=2.0)


class Cue(Contract):
    id: int
    moment_id: int
    start_ms: int
    end_ms: int
    text: str
    variant: Literal["full", "short"]
    priority: int
    status: Literal["verified", "fallback"]
    event_ids: list[int]
    pan: float


EarconKind = Literal["tick", "turnover", "shot", "save", "goal", "set_piece", "whistle", "whistle_long"]


class Earcon(Contract):
    t_ms: int
    kind: EarconKind
    pan: float
    pitch: float
    gain: float


class Dropped(Contract):
    moment_id: int
    priority: int
    reason: str


class BallPoint(Contract):
    t_ms: int
    x: int
    y: int
    home_score: int
    away_score: int


class TraceStep(Contract):
    step: Literal["moment_detector", "describer", "verifier", "timing"]
    status: Literal["ok", "failed"]
    attempt: int
    detail: str
    executor: str | None = None  # the workflow executor that ran the step (SPEC §12); None in the plain pipeline


class PriorityStats(Contract):
    total: int
    scheduled: int


class Report(Contract):
    moments: int
    cues: int
    dropped: int
    verified: int
    fallback: int
    attempts: int
    speech_ms: int
    silence_ms: int
    overlaps: int
    by_priority: dict[str, PriorityStats]


class Session(Contract):
    preset: str
    title: str
    lang: Lang
    profile: Profile
    duration_ms: int
    start_home_score: int
    start_away_score: int
    cues: list[Cue]
    earcons: list[Earcon]
    dropped: list[Dropped]
    track: list[BallPoint]
    trace: list[TraceStep]
    report: Report


class _TimedText(Contract):
    id: str
    at_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    priority: int = Field(ge=0, le=3)
    event_ids: list[int]
    text: str
    status: Literal["verified", "fallback"]


class CueSheetDescription(_TimedText):
    type: Literal["audio_description"]


class CueSheetCaption(_TimedText):
    type: Literal["caption"]


class CueSheetBallSound(Contract):
    id: str
    type: Literal["ball_sound"]
    at_ms: int = Field(ge=0)
    sound: EarconKind
    pan: float = Field(ge=-1, le=1)
    pitch: float = Field(ge=0, le=1)
    gain: float = Field(ge=0, le=1)


CueSheetItem = Annotated[
    CueSheetDescription | CueSheetCaption | CueSheetBallSound, Field(discriminator="type")
]


class CueSheet(Contract):
    """The flat, versioned output for graphics and captioning systems (SPEC §13)."""

    schema_version: Literal[1]  # required, so a consumer can enforce the version
    preset: str
    lang: Lang
    match_clock_from: str = Field(pattern=r"^\d{2,}:\d{2}$")
    duration_ms: int = Field(gt=0)
    items: list[CueSheetItem]


class MatchHeader(Contract):
    seed: int
    home: TeamInfo
    away: TeamInfo
    home_goals: int
    away_goals: int
    goals: list[Event]


class Preset(Contract):
    id: str
    title: str
    from_s: int
    to_s: int


class TtsRequest(Contract):
    text: str = Field(min_length=1, max_length=400)
    lang: Lang = "en"
    rate: float = Field(default=1.0, ge=0.5, le=2.0)


class VoiceSupport(Contract):
    """What the Azure voice can do on this server (SPEC §8, S29): stored clips per language, and whether Speech is configured."""

    stored_clips: dict[Lang, int]
    live: bool


class ErrorResponse(Contract):
    code: Literal[
        "preset_not_found",
        "tts_not_configured",
        "tts_text_not_issued",
        "tts_failed",
        "rate_limited",
        "llm_not_configured",
        "internal_error",
    ]
    message: str
