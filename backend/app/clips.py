"""Stored voice clips: the judges' deployment speaks from files, not from a Speech key (SPEC §8, S26, D17).

The page can only say a finite set of sentences, so each one is spoken once by a neural voice at normal
speed and kept as an mp3 under `backend/app/audio/<lang>/<id>.mp3`, listed in `manifest.json`. A clip is
used only if its manifest entry names the same language and text and its file is present and sane, so a
stale, edited or swapped file is treated as absent. Nothing here reaches the network.
"""

import hashlib
import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("soundpitch.clips")

CLIPS_DIR = Path(__file__).resolve().parent / "audio"
MANIFEST = "manifest.json"
VERSION = 1
LANGS = ("en", "it")
MAX_CLIP_BYTES = 1_000_000  # a 400-character sentence at 48 kbps is about 30 KB


def clip_id(lang: str, text: str) -> str:
    return hashlib.sha256(f"{lang}\n{text}".encode()).hexdigest()[:32]


@dataclass(frozen=True)
class ClipStore:
    root: Path
    clips: dict[str, dict] = field(default_factory=dict)

    def get(self, lang: str, text: str) -> bytes | None:
        if lang not in LANGS:
            return None
        key = clip_id(lang, text)
        entry = self.clips.get(key)
        if not isinstance(entry, dict) or entry.get("lang") != lang or entry.get("text") != text:
            return None
        try:
            data = (self.root / lang / f"{key}.mp3").read_bytes()
        except OSError:
            return None
        return data if 0 < len(data) <= MAX_CLIP_BYTES else None

    def count(self, lang: str) -> int:
        """How many clips of `lang` `get` would serve (S29): the manifest lists them and the file is present and sane."""
        found = 0
        for key, entry in self.clips.items():
            if not (isinstance(entry, dict) and entry.get("lang") == lang and isinstance(entry.get("text"), str)):
                continue
            if lang not in LANGS or clip_id(lang, entry["text"]) != key:
                continue
            try:  # a stat, not a read: this runs on every page load and the clips are megabytes in all
                found += 0 < (self.root / lang / f"{key}.mp3").stat().st_size <= MAX_CLIP_BYTES
            except OSError:
                pass
        return found


def read_manifest(root: Path) -> dict:
    """The manifest on disk, or an empty one if it is missing or unusable."""
    try:
        data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        if data["version"] == VERSION and isinstance(data["clips"], dict):
            return data
        raise ValueError("unexpected structure")
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.error("the clip manifest could not be read (%s): no clip is used", type(exc).__name__)
    return {"version": VERSION, "clips": {}}


def write_manifest(root: Path, manifest: dict) -> None:
    """Replace the manifest atomically: a run stopped halfway leaves the previous one intact."""
    root.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=root, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            json.dump(manifest, out, indent=1, ensure_ascii=False, sort_keys=True)
            out.write("\n")
        os.replace(name, root / MANIFEST)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


_STORE: ClipStore | None = None
_LOCK = threading.Lock()


def store() -> ClipStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = ClipStore(CLIPS_DIR, read_manifest(CLIPS_DIR)["clips"])
        return _STORE


def get(lang: str, text: str) -> bytes | None:
    return store().get(lang, text)


def reset() -> None:
    global _STORE
    with _LOCK:
        _STORE = None
