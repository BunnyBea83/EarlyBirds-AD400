"""Extract skills from the cleaned SQLite postings database.

Usage: python scripts/extract_skills.py [--db PATH] [--batch-size 1000]
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

from birdseye.skill_batch import BatchResult, process_postings


DEFAULT_DB = Path(__file__).resolve().parent.parent / "data/processed/birdseye.db"


def report_progress(result: BatchResult) -> None:
    print(f"Processed {result.processed:,} postings (not yet committed)", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Existing cleaned SQLite database")
    parser.add_argument("--batch-size", type=int, default=1000, help="Descriptions read per chunk (default: 1000)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        result = process_postings(args.db, batch_size=args.batch_size, progress=report_progress)
    except (sqlite3.Error, ValueError, TypeError, OSError) as err:
        print(f"Skill extraction failed: {err}", file=sys.stderr)
        print("Build the database with python scripts/clean_data.py first.", file=sys.stderr)
        return 1
    print(
        f"Saved {result.skill_links:,} skill links from {result.processed:,} postings; "
        f"{result.matched_postings:,} postings matched; "
        f"{result.missing_descriptions:,} descriptions missing."
    )
    if result.invalid_postings:
        print(f"Skipped {result.invalid_postings:,} invalid postings; see warnings for details.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
