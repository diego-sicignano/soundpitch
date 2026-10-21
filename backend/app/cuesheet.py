"""The cue sheet: a session in a flat, versioned shape for graphics and captioning systems (SPEC §13).

    python -m app.cuesheet --write ../docs/contracts/cuesheet.v1.schema.json

It only rearranges what the session already holds, so it carries the same verified words and timings.
"""

import argparse
import json
import sys
from pathlib import Path

from app.contracts import (
    CueSheet,
    CueSheetBallSound,
    CueSheetCaption,
    CueSheetDescription,
    CueSheetItem,
    Preset,
    Session,
)

_ORDER = {"audio_description": 0, "caption": 1, "ball_sound": 2}


def build(session: Session, preset: Preset) -> CueSheet:
    items: list[CueSheetItem] = []
    for cue in session.cues:
        timing = {
            "at_ms": cue.start_ms,
            "duration_ms": cue.end_ms - cue.start_ms,
            "priority": cue.priority,
            "event_ids": cue.event_ids,
            "text": cue.text,
            "status": cue.status,
            "context": cue.context,
        }
        items.append(CueSheetDescription(id=f"ad-{cue.id}", type="audio_description", **timing))
        items.append(CueSheetCaption(id=f"cap-{cue.id}", type="caption", **timing))
    for n, sound in enumerate(session.earcons, start=1):
        items.append(
            CueSheetBallSound(
                id=f"ball-{n}",
                type="ball_sound",
                at_ms=sound.t_ms,
                sound=sound.kind,
                pan=sound.pan,
                pitch=sound.pitch,
                gain=sound.gain,
            )
        )
    items.sort(key=lambda i: (i.at_ms, _ORDER[i.type], i.id))
    return CueSheet(
        schema_version=1,
        preset=session.preset,
        lang=session.lang,
        match_clock_from=f"{preset.from_s // 60:02d}:{preset.from_s % 60:02d}",
        duration_ms=session.duration_ms,
        items=items,
    )


def schema() -> dict:
    return CueSheet.model_json_schema()


def schema_text() -> str:
    """The committed form of the schema: stable key order, two spaces, a final newline."""
    return json.dumps(schema(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or write the JSON Schema of the cue sheet.")
    parser.add_argument("--write", type=Path, help="write the schema to this file instead of printing it")
    args = parser.parse_args(argv)
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(schema_text(), encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(schema_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
