"""Azure AI Speech text-to-speech over the REST API, behind a guard (SPEC §8, S22).

The guard exists because the endpoint is public: it speaks only text the server itself issued in a session,
keeps the audio it has already paid for, and refuses a request before Azure is called when a client, the
process or a day or month of characters is over its limit. Everything here lives in the memory of one process
and restarts at zero: it is a brake, not a spending cap (the pricing tier of the Speech resource is the cap).
"""

import datetime
import os
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Iterable
from dataclasses import dataclass
from xml.sax.saxutils import escape

import httpx

from app import clips
from app.contracts import Lang

VOICES: dict[Lang, tuple[str, str]] = {
    "en": ("en-GB", "en-GB-RyanNeural"),
    "it": ("it-IT", "it-IT-DiegoNeural"),
}
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"

ISSUED_MAX = 4096  # (lang, text) pairs remembered
AUDIO_MAX = 256  # audio clips kept in memory
CLIENTS_MAX = 1024  # clients whose recent requests are tracked
DEFAULT_PER_CLIENT_PER_MINUTE = 30
DEFAULT_PER_MINUTE = 120
DEFAULT_CHARS_PER_DAY = 60_000
DEFAULT_CHARS_PER_MONTH = 300_000

CLOCK = time.time  # seconds since the epoch; tests replace it


class NotConfigured(Exception):
    pass


class NotIssued(Exception):
    pass


class RateLimited(Exception):
    pass


class TtsFailed(Exception):
    pass


_lock = threading.Lock()
_issued: OrderedDict[tuple[str, str], None] = OrderedDict()
_audio: OrderedDict[tuple[str, str, int], bytes] = OrderedDict()
_clients: OrderedDict[str, deque[float]] = OrderedDict()
_sent: deque[float] = deque()  # times of requests that went to Azure
_chars: dict[str, list] = {"day": ["", 0], "month": ["", 0]}  # [period, characters sent in it]


def _limit(name: str, default: int) -> int:
    """A whole number of at least 1 from the environment; anything else is ignored."""
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value >= 1 else default


def issue(lang: str, texts: Iterable[str]) -> None:
    """Remember the texts of a session that was returned to a client; only these can be spoken."""
    with _lock:
        for text in texts:
            _issued[(lang, text)] = None
            _issued.move_to_end((lang, text))
        while len(_issued) > ISSUED_MAX:
            _issued.popitem(last=False)


def issued_count() -> int:
    with _lock:
        return len(_issued)


def audio_count() -> int:
    with _lock:
        return len(_audio)


def reset(keep_issued: bool = False) -> None:
    with _lock:
        if not keep_issued:
            _issued.clear()
        _audio.clear()
        _clients.clear()
        _sent.clear()
        _chars["day"], _chars["month"] = ["", 0], ["", 0]


def _slide(window: deque[float], now: float) -> None:
    while window and now - window[0] > 60:
        window.popleft()


def _per_client_allowed(client: str, now: float) -> bool:
    window = _clients.setdefault(client, deque())
    _clients.move_to_end(client)
    while len(_clients) > CLIENTS_MAX:
        _clients.popitem(last=False)
    _slide(window, now)
    if len(window) >= _limit("SOUNDPITCH_TTS_PER_CLIENT_PER_MINUTE", DEFAULT_PER_CLIENT_PER_MINUTE):
        return False
    window.append(now)
    return True


def _reserve_characters(count: int, now: float) -> str:
    """Count characters about to be sent; return the name of the limit they would pass, or ''."""
    moment = datetime.datetime.fromtimestamp(now, datetime.UTC)
    for name, period, cap in (
        ("day", moment.strftime("%Y-%m-%d"), _limit("SOUNDPITCH_TTS_CHARS_PER_DAY", DEFAULT_CHARS_PER_DAY)),
        ("month", moment.strftime("%Y-%m"), _limit("SOUNDPITCH_TTS_CHARS_PER_MONTH", DEFAULT_CHARS_PER_MONTH)),
    ):
        if _chars[name][0] != period:
            _chars[name] = [period, 0]
        if _chars[name][1] + count > cap:
            return name
    _chars["day"][1] += count
    _chars["month"][1] += count
    return ""


def make_client() -> httpx.Client:
    return httpx.Client(timeout=10)


def ssml(text: str, lang: Lang, rate: float) -> str:
    locale, voice = VOICES[lang]
    percent = round((rate - 1) * 100)
    body = escape(text) if percent == 0 else f"<prosody rate='{percent:+d}%'>{escape(text)}</prosody>"  # markup is billed
    return f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice}'>{body}</voice></speak>"


class TtsHttpError(TtsFailed):
    """Azure answered with an error status (or, with `status` None, could not be reached)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def call_azure(key: str, region: str, text: str, lang: Lang, rate: float) -> bytes:
    """One synthesis request. Raises TtsHttpError; the message never contains the key."""
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
        "User-Agent": "soundpitch",
    }
    try:
        with make_client() as http:
            response = http.post(
                f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                content=ssml(text, lang, rate).encode("utf-8"),
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise TtsHttpError(f"Azure AI Speech is unreachable ({type(exc).__name__})") from exc
    if response.status_code != 200:
        raise TtsHttpError(f"Azure AI Speech returned {response.status_code}", response.status_code)
    return response.content


@dataclass(frozen=True)
class Audio:
    data: bytes
    rate: float  # the speech rate already in the audio: 1 for a stored clip, the requested rate when synthesised


def live_configured() -> bool:
    """True when a Speech key and region are set; reads no value out (S29)."""
    return bool(os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION"))


def synthesize(text: str, lang: Lang, rate: float, client: str = "local") -> Audio:
    percent = round((rate - 1) * 100)
    with _lock:
        if (lang, text) not in _issued:
            raise NotIssued("Only the text of a returned session can be spoken")
        if not _per_client_allowed(client, CLOCK()):
            raise RateLimited("Too many speech requests from this client, try again in a minute")
    stored = clips.get(lang, text)
    if stored is not None:
        return Audio(stored, 1.0)
    key, region = os.environ.get("AZURE_SPEECH_KEY"), os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        raise NotConfigured("Azure AI Speech is not configured")
    clip = (lang, text, percent)
    with _lock:
        if clip in _audio:
            _audio.move_to_end(clip)
            return Audio(_audio[clip], 1 + percent / 100)
        now = CLOCK()
        _slide(_sent, now)
        if len(_sent) >= _limit("SOUNDPITCH_TTS_PER_MINUTE", DEFAULT_PER_MINUTE):
            raise RateLimited("Too many speech requests, try again in a minute")
        over = _reserve_characters(len(text), now)
        if over:
            raise RateLimited(f"The speech character limit for the {over} was reached")
        _sent.append(now)
    data = call_azure(key, region, text, lang, rate)
    with _lock:
        _audio[clip] = data
        while len(_audio) > AUDIO_MAX:
            _audio.popitem(last=False)
    return Audio(data, 1 + percent / 100)
