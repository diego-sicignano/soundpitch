"""Make the voice clips the demo speaks from (SPEC §8, S26, D17).

    python -m app.clips_build                      # DRY RUN: count the sentences, the characters, the estimated cost
    python -m app.clips_build --generate --limit 1 # one test request, then check the clip
    python -m app.clips_build --generate           # every missing clip

The plain command needs no key and sends nothing. `--generate` calls Azure AI Speech and SPENDS MONEY (the
estimated cost is printed first, and it needs `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`). It only makes
clips that are missing, at normal speed and with no markup, stops by itself at `--max-chars` characters, and
never prints the key. The sentences are those the pipeline accepts for every window, detail level and
language, with the recorded model words of the replay mode (`app.replay`), `full` and `short` alike.
"""

import argparse
import datetime
import os
import sys
import time
from typing import get_args

from app import clips, tts
from app.contracts import Detail, Lang, Profile
from app.match_gen import SEED, generate_match
from app.pipeline import build_presets, verified_descriptions
from app.replay import ReplayDescriber, load_store

# Standard neural voices, USD per million characters: Microsoft Learn, "Azure AI Speech quotas and limits"
# (read 2026-10-20); the public pricing page did not show the figure. Confirm it before relying on the estimate.
PRICE_USD_PER_MILLION = 15.0
ATTEMPTS = 5  # per clip, for 429 and 5xx
RETRY_STATUS = {None, 429, 500, 502, 503, 504}
PAUSE_S = 0.25  # between requests, far below the 30 requests a second of the standard tier


def sentences() -> list[tuple[str, str]]:
    """Every (language, text) the demo can speak, sorted."""
    match = generate_match(SEED)
    describer = ReplayDescriber(load_store())
    found: set[tuple[str, str]] = set()
    for preset in build_presets(match):
        for detail in get_args(Detail):
            for lang in get_args(Lang):
                accepted = verified_descriptions(match, preset, Profile(detail=detail, lang=lang), describer)
                for description, _status in accepted.values():
                    found.add((lang, description.full))
                    found.add((lang, description.short))
    return sorted(found)


def _cost(characters: int) -> float:
    return characters * PRICE_USD_PER_MILLION / 1e6


def _clip_one(key: str, region: str, lang: str, text: str) -> bytes:
    """One clip, retrying what is worth retrying with a growing wait. Raises TtsHttpError when it gives up."""
    for attempt in range(ATTEMPTS):
        try:
            return tts.call_azure(key, region, text, lang, 1.0)  # type: ignore[arg-type]
        except tts.TtsHttpError as exc:
            if exc.status not in RETRY_STATUS or attempt == ATTEMPTS - 1:
                raise
            time.sleep(min(60, 2 * 2**attempt))
    raise AssertionError("unreachable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--generate", action="store_true", help="call Speech for the missing clips (spends money)")
    parser.add_argument("--limit", type=int, help="make at most this many clips")
    parser.add_argument("--max-chars", type=int, default=10_000, help="refuse to send more characters than this")
    parser.add_argument("--date", default="", help="date to record in the manifest (default: today)")
    args = parser.parse_args(argv)

    universe = sentences()
    root = clips.CLIPS_DIR
    manifest = clips.read_manifest(root)
    store = clips.ClipStore(root, manifest["clips"])
    missing = [(lang, text) for lang, text in universe if store.get(lang, text) is None]
    chars = sum(len(t) for _, t in universe)
    missing_chars = sum(len(t) for _, t in missing)
    per_lang = ", ".join(f"{lang} {sum(1 for ll, _ in universe if ll == lang)}" for lang in get_args(Lang))
    print(f"the demo can speak {len(universe)} sentences ({per_lang}), {chars} characters")
    print(f"stored clips: {len(universe) - len(missing)} of {len(universe)}; missing: {len(missing)} ({missing_chars} characters)")
    print(
        f"estimated cost of the missing clips at USD {PRICE_USD_PER_MILLION:g} per million characters: "
        f"{_cost(missing_chars):.2f} USD (the price is to be confirmed before use)"
    )
    if not args.generate:
        print("dry run: nothing was sent. Add --generate to call Azure AI Speech (it spends money).")
        return 0

    key, region = os.environ.get("AZURE_SPEECH_KEY"), os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        print("cannot generate: AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are not both set", file=sys.stderr)
        return 2
    todo = missing[: args.limit] if args.limit is not None else missing
    todo_chars = sum(len(t) for _, t in todo)
    if todo_chars > args.max_chars:
        print(f"cannot generate: {todo_chars} characters is more than --max-chars {args.max_chars}", file=sys.stderr)
        return 2

    manifest.update(
        version=clips.VERSION,
        format=tts.OUTPUT_FORMAT,
        voices={lang: voice for lang, (_, voice) in tts.VOICES.items()},
        rate=1.0,
        generated=args.date or datetime.date.today().isoformat(),
        service="Azure AI Speech, neural voices, standard tier; synthetic speech",
    )
    made = 0
    for lang, text in todo:
        try:
            data = _clip_one(key, region, lang, text)
        except tts.TtsHttpError as exc:
            print(f"stopped after {made} clips: {exc}", file=sys.stderr)
            clips.write_manifest(root, manifest)
            return 1
        (root / lang).mkdir(parents=True, exist_ok=True)
        (root / lang / f"{clips.clip_id(lang, text)}.mp3").write_bytes(data)
        manifest["clips"][clips.clip_id(lang, text)] = {"lang": lang, "text": text, "bytes": len(data)}
        clips.write_manifest(root, manifest)  # after each clip, so a stopped run can be resumed
        made += 1
        time.sleep(PAUSE_S)
    print(f"made {made} clips; {len(missing) - made} still missing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
