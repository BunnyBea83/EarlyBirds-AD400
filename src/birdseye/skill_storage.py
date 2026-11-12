"""SQLite persistence for canonical skills and extracted posting skills.

Call initialize_storage on a fresh connection to an existing cleaned database.
The caller owns the connection and must close it when finished.
"""

import sqlite3
from collections.abc import Iterable

from birdseye.skills_catalog import SKILLS


def initialize_storage(conn: sqlite3.Connection) -> None:
    """Create tables and seed the catalog without changing existing skill IDs.

    Requires a postings table with unique, non-null job IDs. Run outside an
    existing transaction so SQLite can enable foreign-key enforcement.
    """
    if conn.in_transaction:
        raise ValueError("initialize_storage requires no active transaction")
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        if conn.execute("SELECT 1 FROM postings WHERE job_id IS NULL LIMIT 1").fetchone():
            raise ValueError("postings contains a missing job_id")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_postings_job_id ON postings(job_id)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                skill_id INTEGER PRIMARY KEY,
                category TEXT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE
                    CHECK (length(trim(name)) > 0)
            )
        """)
        # Support databases created by the earlier version of this service.
        if "category" not in {row[1] for row in conn.execute("PRAGMA table_info(skills)")}:
            conn.execute("ALTER TABLE skills ADD COLUMN category TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_aliases (
                alias TEXT PRIMARY KEY COLLATE NOCASE,
                skill_id INTEGER NOT NULL REFERENCES skills(skill_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posting_skills (
                job_id INTEGER NOT NULL REFERENCES postings(job_id) ON DELETE CASCADE,
                skill_id INTEGER NOT NULL REFERENCES skills(skill_id),
                PRIMARY KEY (job_id, skill_id)
            )
        """)
        for skill in SKILLS:
            # A reviewed rename/merge retains the former canonical name as an
            # alias. Do not recreate that skill on the next initialization.
            if conn.execute(
                "SELECT 1 FROM skill_aliases WHERE alias = ?",
                (" ".join(skill.name.casefold().split()),),
            ).fetchone():
                continue
            conn.execute(
                "INSERT INTO skills(name, category) VALUES (?, ?) ON CONFLICT(name) DO NOTHING",
                (skill.name, skill.category),
            )
            skill_id = conn.execute("SELECT skill_id FROM skills WHERE name = ?", (skill.name,)).fetchone()[0]
            for term in (skill.name, *skill.aliases):
                alias = " ".join(term.casefold().split())
                existing = conn.execute("SELECT skill_id FROM skill_aliases WHERE alias = ?", (alias,)).fetchone()
                if existing and existing[0] != skill_id:
                    raise ValueError(f"Catalog alias belongs to another skill: {term}")
                conn.execute(
                    "INSERT INTO skill_aliases VALUES (?, ?) ON CONFLICT(alias) DO NOTHING",
                    (alias, skill_id),
                )


def save_posting_skills(
    conn: sqlite3.Connection, job_id: int, skill_names: Iterable[str]
) -> None:
    """Replace a posting's skills atomically with canonical catalog names.

    Duplicate names are harmless. Empty results clear old matches. Unknown
    names or job IDs raise ValueError before changing existing relationships.
    The connection must have been initialized with initialize_storage.
    """
    if isinstance(skill_names, (str, bytes)):
        raise TypeError("skill_names must be an iterable of canonical names")
    names = set(skill_names)
    catalog = dict(conn.execute("SELECT name, skill_id FROM skills"))
    unknown = names - catalog.keys()
    if unknown:
        raise ValueError(f"Unknown canonical skills: {sorted(unknown)}")
    if conn.execute("SELECT 1 FROM postings WHERE job_id = ?", (job_id,)).fetchone() is None:
        raise ValueError(f"Unknown job_id: {job_id}")
    # A savepoint also preserves any transaction the caller already owns.
    conn.execute("SAVEPOINT save_posting_skills")
    try:
        conn.execute("DELETE FROM posting_skills WHERE job_id = ?", (job_id,))
        conn.executemany(
            "INSERT INTO posting_skills(job_id, skill_id) VALUES (?, ?)",
            ((job_id, catalog[name]) for name in names),
        )
    except Exception:
        conn.execute("ROLLBACK TO save_posting_skills")
        conn.execute("RELEASE save_posting_skills")
        raise
    conn.execute("RELEASE save_posting_skills")
