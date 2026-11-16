"""Store each role's top-20 skill profile in one table (TA4-51).

role_profiles(role, skill, share): one row per skill in a role's profile, for
every role in one table. share is the percentage (0-100) of that role's
postings that mention the skill, the same figure the dashboard charts show.
A profile holds up to 20 skills: a role that mentions fewer than 20 different
skills has a shorter profile, and a role with no skills found has no rows.

The table is derived from posting_skills, so rebuild it after skill extraction
or any change to the skill catalog (python scripts/build_role_profiles.py).
"""

import sqlite3
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path

from birdseye.skill_summary import read_summary

MAX_PROFILE_SKILLS = 20


class MissingRoleProfiles(sqlite3.OperationalError):
    """The database still needs the role profile build step."""


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


def build_role_profiles(conn: sqlite3.Connection, size: int = MAX_PROFILE_SKILLS) -> int:
    """Rebuild the role_profiles table from posting_skills and return its row count.

    The previous contents are replaced in one transaction, so an error leaves the
    old table as it was. Requires skill extraction to have been run.
    """
    rows = profile_rows(read_summary(conn)["roles"], size)
    with conn:
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


def read_role_profile(conn: sqlite3.Connection, role: str) -> list[dict]:
    """Return a role's stored profile, highest share first (empty if it has none).

    Each item has "skill" and "percentage" so top_skills_chart can draw it.
    """
    tables = {name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "role_profiles" not in tables:
        raise MissingRoleProfiles(
            "Build the role profiles with scripts/build_role_profiles.py to see this section."
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