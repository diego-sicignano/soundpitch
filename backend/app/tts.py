"""Azure AI Speech text-to-speech over the REST API, with a per-minute cost guard."""

import os
import time
from collections import deque
from xml.sax.saxutils import escape

import httpx

from app.contracts import Lang

VOICES: dict[Lang, tuple[str, str]] = {
    "en": ("en-GB", "en-GB-RyanNeural"),
    "it": ("it-IT", "it-IT-DiegoNeural"),
}
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"


class NotConfigured(Exception):
    pass


class RateLimited(Exception):
    pass


class TtsFailed(Exception):
    pass


class RateLimiter:
    """Sliding one-minute window; protects the Speech quota when the demo is public."""

    def __init__(self) -> None:
        self.hits: deque[float] = deque()

    def allow(self, limit: int) -> bool:
        now = time.monotonic()
        while self.hits and now - self.hits[0] > 60:
            self.hits.popleft()
        if len(self.hits) >= limit:
            return False
        self.hits.append(now)
        return True

    def reset(self) -> None:
        self.hits.clear()


LIMITER = RateLimiter()


def make_client() -> httpx.Client:
    return httpx.Client(timeout=10)


def ssml(text: str, lang: Lang, rate: float) -> str:
    locale, voice = VOICES[lang]
    percent = f"{round((rate - 1) * 100):+d}%"
    return (
        f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice}'>"
        f"<prosody rate='{percent}'>{escape(text)}</prosody></voice></speak>"
    )


def synthesize(text: str, lang: Lang, rate: float) -> bytes:
    key, region = os.environ.get("AZURE_SPEECH_KEY"), os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        raise NotConfigured("Azure AI Speech is not configured")
    if not LIMITER.allow(int(os.environ.get("SOUNDPITCH_TTS_PER_MINUTE", "120"))):
        raise RateLimited("Too many speech requests, try again in a minute")
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
        "User-Agent": "soundpitch",
    }
    try:
        with make_client() as client:
            response = client.post(
                f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                content=ssml(text, lang, rate).encode("utf-8"),
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise TtsFailed(f"Azure AI Speech is unreachable ({type(exc).__name__})") from exc
    if response.status_code != 200:
        raise TtsFailed(f"Azure AI Speech returned {response.status_code}")
    return response.content
