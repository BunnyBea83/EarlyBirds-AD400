"""SQLite persistence for canonical skills and extracted posting skills.

Call initialize_storage on a fresh connection to an existing cleaned database.
The caller owns the connection and must close it when finished.
"""

import sqlite3

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
        conn.executemany(
            "INSERT INTO skills(name) VALUES (?) ON CONFLICT(name) DO NOTHING",
            ((skill.name,) for skill in SKILLS),
        )
        for skill in SKILLS:
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


