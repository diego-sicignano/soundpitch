"""Check a running SoundPitch server: `python -m app.smoke http://localhost:8000` (SPEC §15, S16).

It reads only: health, presets, and one session for every preset in each language. It exits 1 and lists
every problem if the server is down, a contract is broken, cues overlap or a must-say moment is missing.
"""

import sys

import httpx
from pydantic import ValidationError

from app.contracts import Preset, Session


def check(client) -> list[str]:
    """Problems found through `client` (an httpx.Client or a Starlette TestClient); empty means healthy."""
    problems: list[str] = []
    try:
        health = client.get("/api/health")
        if health.status_code != 200 or health.json().get("status") != "ok":
            return [f"/api/health answered {health.status_code}"]
        presets = [Preset.model_validate(p) for p in client.get("/api/presets").json()]
    except (httpx.HTTPError, ValueError, ValidationError) as exc:
        return [f"the server could not be read ({type(exc).__name__})"]
    if len(presets) < 5:
        problems.append(f"only {len(presets)} presets")
    for preset in presets:
        for lang in ("en", "it"):
            label = f"{preset.id}/{lang}"
            try:
                response = client.get("/api/session", params={"preset": preset.id, "lang": lang})
                session = Session.model_validate(response.json()) if response.status_code == 200 else None
            except (httpx.HTTPError, ValueError, ValidationError) as exc:
                problems.append(f"{label}: unreadable session ({type(exc).__name__})")
                continue
            if session is None:
                problems.append(f"{label}: answered {response.status_code}")
                continue
            must = session.report.by_priority["3"]
            if not session.cues:
                problems.append(f"{label}: no cues")
            if session.report.overlaps:
                problems.append(f"{label}: {session.report.overlaps} overlapping cues")
            if must.scheduled != must.total:
                problems.append(f"{label}: {must.total - must.scheduled} must-say moments missing")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m app.smoke <base-url>")
        return 2
    with httpx.Client(base_url=argv[1], timeout=30, follow_redirects=True) as client:
        problems = check(client)
    for problem in problems:
        print("FAIL", problem)
    print("ok" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
