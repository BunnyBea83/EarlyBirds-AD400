"""Rank the most requested skills across all postings (TA4-54).

Counts come straight from the posting_skills table, so the figures can be
checked against it with a plain SQL query. Each result has the same shape as
one role's entry in skill_summary.summarize(), so top_skills_chart() can draw it.
"""

import sqlite3
from collections import Counter
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path

TOP_N = 15


def rank_skills(counts: Mapping[str, int], total_postings: int, limit: int = TOP_N) -> dict:
    """Return the top skills by posting count, with each skill's share of postings.

    Ties are broken alphabetically (ignoring case), matching skill_summary. With
    no postings there is nothing to rank, so the list is empty.
    """
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold(), item[0]))
    ranked = [
        {"skill": skill, "posting_count": count, "percentage": 100 * count / total_postings,
         "rank": rank}
        for rank, (skill, count) in enumerate(ordered[:limit], 1)
    ] if total_postings else []
    return {"total_postings": total_postings, "top_skills": ranked}


def top_skills_all_postings(conn: sqlite3.Connection, limit: int = TOP_N) -> dict:
    """Top skills across every posting, including postings with no skills or no role.

    The share is out of all rows in postings, so a posting that mentions no
    skill still counts in the denominator.
    """
    total = conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
    counts = dict(conn.execute("""
        SELECT s.name, COUNT(DISTINCT ps.job_id)
        FROM posting_skills AS ps
        JOIN postings AS p ON p.job_id = ps.job_id
        JOIN skills AS s ON s.skill_id = ps.skill_id
        GROUP BY s.skill_id
    """))
    return rank_skills(counts, total, limit)


def load_top_skills(database, limit: int = TOP_N) -> dict:
    """Open the database read-only and return top_skills_all_postings()."""
    with closing(sqlite3.connect(f"{Path(database).resolve().as_uri()}?mode=ro", uri=True)) as conn:
        return top_skills_all_postings(conn, limit)


def combine_roles(roles: Mapping[str, dict], limit: int = TOP_N) -> dict:
    """Add up skill_summary's per-role results (used for the synthetic demo data).

    Unlike top_skills_all_postings, postings without a resolved role are not in
    skill_summary's results, so they are not counted here.
    """
    counts: Counter = Counter()
    total = 0
    for role in roles.values():
        total += role["total_postings"]
        for row in role["skills"]:
            counts[row["skill"]] += row["posting_count"]
    return rank_skills(counts, total, limit)