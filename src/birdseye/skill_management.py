"""Reviewed catalog changes and exact equivalent-name resolution (TA4-44).

No fuzzy score silently merges skills. Add reviewed aliases, or explicitly
confirm a merge of existing records. The caller owns the initialized connection.
"""

import sqlite3
from contextlib import contextmanager

from birdseye.skills_catalog import Skill


def _name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Skill names must be nonempty strings")
    return " ".join(value.split())


@contextmanager
def _atomic(conn):
    conn.execute("SAVEPOINT catalog_change")
    try:
        yield
    except Exception:
        conn.execute("ROLLBACK TO catalog_change")
        conn.execute("RELEASE catalog_change")
        raise
    conn.execute("RELEASE catalog_change")


def _check_aliases(conn, terms, skill_id=None):
    for term in terms:
        owner = conn.execute("SELECT skill_id FROM skill_aliases WHERE alias = ?", (term,)).fetchone()
        if owner and owner[0] != skill_id:
            raise ValueError(f"Alias already belongs to another skill: {term}")


def add_skill(conn: sqlite3.Connection, name: str, *, aliases=(), category=None) -> int:
    """Resolve known equivalents or add a reviewed skill with optional aliases.

    A known alias returns the existing skill ID. Conflicting aliases are rejected
    rather than automatically consolidating distinct records.
    """
    name = _name(name)
    if isinstance(aliases, (str, bytes)):
        raise TypeError("aliases must be a sequence of names")
    terms = {_name(term).casefold() for term in (name, *aliases)}
    with _atomic(conn):
        row = conn.execute("SELECT skill_id FROM skill_aliases WHERE alias = ?", (name.casefold(),)).fetchone()
        skill_id = row[0] if row else None
        _check_aliases(conn, terms, skill_id)
        if skill_id is None:
            skill_id = conn.execute("INSERT INTO skills(name, category) VALUES (?, ?)", (name, category)).lastrowid
        conn.executemany(
            "INSERT INTO skill_aliases VALUES (?, ?) ON CONFLICT(alias) DO NOTHING",
            ((term, skill_id) for term in terms),
        )
    return skill_id


def update_skill(conn: sqlite3.Connection, skill_id: int, *, name: str, category=None) -> None:
    """Rename/categorize a skill without changing its ID or losing old aliases."""
    name = _name(name)
    with _atomic(conn):
        if not conn.execute("SELECT 1 FROM skills WHERE skill_id = ?", (skill_id,)).fetchone():
            raise ValueError(f"Unknown skill_id: {skill_id}")
        _check_aliases(conn, {name.casefold()}, skill_id)
        conn.execute("UPDATE skills SET name = ?, category = ? WHERE skill_id = ?", (name, category, skill_id))
        conn.execute("INSERT INTO skill_aliases VALUES (?, ?) ON CONFLICT(alias) DO NOTHING", (name.casefold(), skill_id))


def consolidate_skills(
    conn: sqlite3.Connection, source_id: int, target_id: int, *, confirmed: bool = False
) -> None:
    """Merge reviewed equivalent records, preserving all aliases and job links."""
    if confirmed is not True:
        raise ValueError("Skill consolidation requires explicit confirmation")
    if source_id == target_id:
        raise ValueError("Choose two distinct skill IDs")
    with _atomic(conn):
        for skill_id in (source_id, target_id):
            if not conn.execute("SELECT 1 FROM skills WHERE skill_id = ?", (skill_id,)).fetchone():
                raise ValueError(f"Unknown skill_id: {skill_id}")
        conn.execute("""
            INSERT OR IGNORE INTO posting_skills(job_id, skill_id)
            SELECT job_id, ? FROM posting_skills WHERE skill_id = ?
        """, (target_id, source_id))
        conn.execute("DELETE FROM posting_skills WHERE skill_id = ?", (source_id,))
        conn.execute("UPDATE skill_aliases SET skill_id = ? WHERE skill_id = ?", (target_id, source_id))
        conn.execute("DELETE FROM skills WHERE skill_id = ?", (source_id,))


def load_skills(conn: sqlite3.Connection) -> tuple[Skill, ...]:
    """Retrieve the stored catalog, including reviewed additions and aliases."""
    skills = []
    for skill_id, name, category in conn.execute("SELECT skill_id, name, category FROM skills ORDER BY skill_id"):
        aliases = tuple(row[0] for row in conn.execute(
            "SELECT alias FROM skill_aliases WHERE skill_id = ? ORDER BY alias", (skill_id,)
        ) if row[0] != name.casefold())
        skills.append(Skill(name, aliases, category))
    return tuple(skills)
