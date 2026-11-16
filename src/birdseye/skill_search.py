"""Skill listing, synonym search, and selection cleanup for Skill Input.

Plain sqlite3 and Python only (no Streamlit), so it can be tested directly.
Selections are skill IDs, never typed names, which is what keeps "MS Excel"
and "Excel" from becoming two different skills.
"""

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillOption:
    """A canonical skill the user can pick."""

    skill_id: int
    name: str


def normalize_term(term: str) -> str:
    """Normalize text the same way the skill catalog normalizes aliases."""
    return " ".join(term.casefold().split())


def list_skills(conn: sqlite3.Connection) -> list[SkillOption]:
    """Return every canonical skill, alphabetically and without duplicates.

    skills.name is UNIQUE (case-insensitive), so each skill appears once.
    """
    rows = conn.execute(
        "SELECT skill_id, name FROM skills ORDER BY name COLLATE NOCASE, skill_id"
    )
    return [SkillOption(skill_id, name) for skill_id, name in rows]


def search_skills(conn: sqlite3.Connection, query: str) -> list[SkillOption]:
    """Return canonical skills whose name or any alias contains the query.

    A synonym finds its standard skill ("ms excel" -> Microsoft Excel). A skill
    with several matching aliases is returned once. A blank query returns the
    full list. Results are alphabetical.
    """
    term = normalize_term(query)
    if not term:
        return list_skills(conn)
    # Treat %, _ and \ typed by the user as literal characters.
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = conn.execute(
        """
        SELECT skill_id, name FROM skills
        WHERE name LIKE :pattern ESCAPE '\\'
           OR skill_id IN (
               SELECT skill_id FROM skill_aliases WHERE alias LIKE :pattern ESCAPE '\\'
           )
        ORDER BY name COLLATE NOCASE, skill_id
        """,
        {"pattern": f"%{escaped}%"},
    )
    return [SkillOption(skill_id, name) for skill_id, name in rows]


def skill_synonyms(conn: sqlite3.Connection) -> dict[int, list[str]]:
    """Map each skill ID to its alternate names, alphabetically.

    The canonical name itself is left out, so a skill with no synonyms has no
    entry. Aliases are stored normalized (lowercase).
    """
    synonyms: dict[int, list[str]] = {}
    rows = conn.execute(
        """
        SELECT a.skill_id, a.alias, s.name
        FROM skill_aliases a JOIN skills s ON s.skill_id = a.skill_id
        ORDER BY a.alias
        """
    )
    for skill_id, alias, name in rows:
        if alias != normalize_term(name):
            synonyms.setdefault(skill_id, []).append(alias)
    return synonyms


def skill_label(name: str, synonyms: Iterable[str] = ()) -> str:
    """Text shown for a skill in the picker, e.g. 'Microsoft Excel (ms excel)'.

    Including the synonyms lets the picker's built-in filtering find a skill by
    any of its names while the user types.
    """
    synonyms = list(synonyms)
    return f"{name} ({', '.join(synonyms)})" if synonyms else name


def clean_selection(selected: Iterable[int], valid_ids: Iterable[int]) -> list[int]:
    """Drop duplicate and unknown skill IDs, keeping the original order."""
    valid = set(valid_ids)
    return [skill_id for skill_id in dict.fromkeys(selected) if skill_id in valid]