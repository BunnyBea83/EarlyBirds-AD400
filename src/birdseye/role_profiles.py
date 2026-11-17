"""Store each role's top-20 skill profile in one table (TA4-51).

role_profiles(role, skill, share): one row per skill in a role's profile, for
every role in one table. share is the percentage (0-100) of that role's
postings that mention the skill, the same figure the dashboard charts show.
A profile holds up to 20 skills: a role that mentions fewer than 20 different
skills has a shorter profile, and a role with no skills found has no rows.

The table is derived from postings and posting_skills, so rebuild it after
cleaning, skill extraction, or any change to the skill catalog
(python scripts/build_role_profiles.py).

To stop stale numbers from being shown, each build also saves a fingerprint of
the data it was built from in role_profile_meta. Reading a profile recomputes the
fingerprint and refuses to return rows if it no longer matches (StaleRoleProfiles).
"""

import hashlib
import json
import sqlite3
import zlib
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path

from birdseye.roles import ROLE_RULES
from birdseye.skill_summary import read_summary

MAX_PROFILE_SKILLS = 20
REBUILD_COMMAND = "python scripts/build_role_profiles.py --db data/processed/birdseye.db"


class MissingRoleProfiles(sqlite3.OperationalError):
    """The database still needs the role profile build step."""


class StaleRoleProfiles(MissingRoleProfiles):
    """The stored profiles no longer match the postings and skills they were built from."""


def profile_rows(
    roles: Mapping[str, dict], size: int = MAX_PROFILE_SKILLS
) -> list[tuple[str, str, float]]:
    """Return (role, skill, share) rows holding each role's top `size` skills.

    Skills are ranked by share, ties alphabetical, exactly as in skill_summary.
    Only skills that appear in at least one of the role's postings are included.
    """
    return [
        (role, row["skill"], row["percentage"])
        for role, entry in roles.items()
        for row in entry["skills"][:size]
    ]


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def source_fingerprint(conn: sqlite3.Connection, size: int = MAX_PROFILE_SKILLS) -> str | None:
    """Summarize the data the profiles are built from as a short text fingerprint.

    It covers the postings (IDs and titles), the skill links, the skill names, the role
    rules and the profile size, so it changes when any of them changes, whichever script
    made the change. The same data always gives the same fingerprint, so re-running
    extraction to an identical result makes the stored profiles current again.
    The sums are a change detector, not a cryptographic guarantee.

    Returns None when the postings or skill tables don't exist.
    """
    if not {"postings", "skills", "posting_skills"} <= _tables(conn):
        return None
    conn.create_function(
        "title_checksum", 1, lambda title: zlib.crc32((title or "").encode()), deterministic=True
    )
    postings = conn.execute(
        "SELECT COUNT(*), TOTAL(job_id), TOTAL(title_checksum(title)) FROM postings"
    ).fetchone()
    links = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM((job_id * 1000003 + skill_id * 7919) % 2147483629), 0) "
        "FROM posting_skills"
    ).fetchone()
    skills = [f"{skill_id}:{name}" for skill_id, name in
              conn.execute("SELECT skill_id, name FROM skills ORDER BY skill_id")]
    parts = {"rules": ROLE_RULES, "size": size, "postings": postings, "links": links, "skills": skills}
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=list).encode()).hexdigest()


def build_role_profiles(conn: sqlite3.Connection, size: int = MAX_PROFILE_SKILLS) -> int:
    """Rebuild the role_profiles table from posting_skills and return its row count.

    The previous contents are replaced in one transaction, so an error leaves the
    old table as it was. The fingerprint of the source data is saved in the same
    transaction. Requires skill extraction to have been run.
    """
    rows = profile_rows(read_summary(conn)["roles"], size)
    fingerprint = source_fingerprint(conn, size)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS role_profile_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                source_fingerprint TEXT NOT NULL,
                built_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("DELETE FROM role_profile_meta")
        conn.execute("INSERT INTO role_profile_meta(id, source_fingerprint) VALUES (1, ?)", (fingerprint,))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS role_profiles (
                role TEXT NOT NULL,
                skill TEXT NOT NULL,
                share REAL NOT NULL CHECK (share > 0 AND share <= 100),
                PRIMARY KEY (role, skill)
            )
        """)
        conn.execute("DELETE FROM role_profiles")
        conn.executemany("INSERT INTO role_profiles(role, skill, share) VALUES (?, ?, ?)", rows)
    return len(rows)


def profiles_are_current(conn: sqlite3.Connection, size: int = MAX_PROFILE_SKILLS) -> bool:
    """True when the stored profiles were built from the data as it is now."""
    if not {"role_profiles", "role_profile_meta"} <= _tables(conn):
        return False
    row = conn.execute("SELECT source_fingerprint FROM role_profile_meta WHERE id = 1").fetchone()
    current = source_fingerprint(conn, size)
    return row is not None and current is not None and row[0] == current


def read_role_profile(conn: sqlite3.Connection, role: str) -> list[dict]:
    """Return a role's stored profile, highest share first (empty if it has none).

    Each item has "skill" and "percentage" so top_skills_chart can draw it.
    Raises MissingRoleProfiles if the profiles were never built, and StaleRoleProfiles
    (a MissingRoleProfiles) if the postings or skills changed since they were built.
    The message says how to rebuild.
    """
    if "role_profiles" not in _tables(conn):
        raise MissingRoleProfiles(
            "Build the role profiles with scripts/build_role_profiles.py to see this section."
        )
    if not profiles_are_current(conn):
        raise StaleRoleProfiles(
            "The stored role profiles are out of date, because the postings or skills changed "
            f"after they were built. Rebuild them with: {REBUILD_COMMAND}"
        )
    rows = conn.execute(
        "SELECT skill, share FROM role_profiles WHERE role = ? "
        "ORDER BY share DESC, skill COLLATE NOCASE",
        (role,),
    )
    return [{"skill": skill, "percentage": share} for skill, share in rows]


def load_role_profile(database, role: str) -> list[dict]:
    """Open the database read-only and return read_role_profile()."""
    with closing(sqlite3.connect(f"{Path(database).resolve().as_uri()}?mode=ro", uri=True)) as conn:
        return read_role_profile(conn, role)