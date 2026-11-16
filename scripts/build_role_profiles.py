"""Build the role_profiles table: each role's top skills (up to 20) and their share of postings.

Run after skill extraction:
    python scripts/build_role_profiles.py --db data/processed/birdseye.db
"""

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from birdseye.role_profiles import MAX_PROFILE_SKILLS, build_role_profiles


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=Path("data/processed/birdseye.db"),
                        help="cleaned Birdseye database (default: data/processed/birdseye.db)")
    args = parser.parse_args(argv)
    if not args.db.is_file():
        print(f"Role profile build failed: database not found at {args.db}", file=sys.stderr)
        return 1
    try:
        with closing(sqlite3.connect(args.db)) as conn:
            rows = build_role_profiles(conn)
    except (sqlite3.Error, ValueError) as error:
        print(f"Role profile build failed: {error}", file=sys.stderr)
        return 1
    print(f"Saved {rows} profile rows (up to {MAX_PROFILE_SKILLS} skills per role).")
    return 0


if __name__ == "__main__":
    sys.exit(main())