"""Turn the replies a Foundry run stored in the usage ledger into the replay file (SPEC §11, D12).

    python -m app.replay_export --db data/usage.sqlite --model gpt-4.1-mini --recorded 2026-10-21
    python -m app.replay_export --check

It only reads a local SQLite file and writes a JSON file; it never contacts Azure. The replies come from
`python -m app.foundry_run` (a live, billable run that needs the owner's approval). `--check` prints how
many requests (preset x detail x language, first attempt) the replay file covers and exits 1 if not all.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from app.replay import STORE_PATH, VERSION, coverage, load_store


def export(db: Path, out: Path, model: str, recorded: str) -> int:
    con = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)  # as_uri escapes # % and spaces
    try:
        rows = con.execute("SELECT key, reply FROM replies ORDER BY key").fetchall()
    finally:
        con.close()
    document = {"version": VERSION, "model": model, "recorded": recorded, "replies": dict(rows)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, help="the usage ledger file that holds the replies")
    parser.add_argument("--out", type=Path, default=STORE_PATH)
    parser.add_argument("--model", default="", help="the model that wrote the replies, for the record")
    parser.add_argument("--recorded", default="", help="the date of the run, YYYY-MM-DD")
    parser.add_argument("--check", action="store_true", help="report the coverage of the replay file and exit")
    args = parser.parse_args(argv)
    if args.check:
        store = load_store(args.out)
        hit, total = coverage(store)
        print(f"{len(store.replies)} recorded replies; {hit} of {total} first-attempt requests covered")
        return 0 if hit == total else 1
    if not args.db or not args.model or not args.recorded:
        parser.error("--db, --model and --recorded are required to export")
    print(f"{export(args.db, args.out, args.model, args.recorded)} replies written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
