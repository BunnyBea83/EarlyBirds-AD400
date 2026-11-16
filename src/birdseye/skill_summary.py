"""Summarize canonical skills from the Birdseye SQLite database."""

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from birdseye.roles import NEEDS_REVIEW, ROLE_RULES, UNKNOWN, map_roles


def summarize(postings, categories, roles=ROLE_RULES):
    """Return posting prevalence and skill-match composition for each role."""
    summaries = {role: {"total_postings": 0, "skills": Counter(),
                        "category_postings": Counter(), "category_matches": Counter()}
                 for role in roles}
    unresolved = dict.fromkeys((UNKNOWN, NEEDS_REVIEW), 0)
    for posting in postings:
        role = posting["role"]
        if role not in summaries:
            outcome = NEEDS_REVIEW if role == NEEDS_REVIEW else UNKNOWN
            unresolved[outcome] += 1
            continue
        row = summaries[role]
        row["total_postings"] += 1
        skills = set(posting["skills"])
        row["skills"].update(skills)
        matches = [categories.get(skill) or "Uncategorized" for skill in skills]
        row["category_postings"].update(set(matches))
        row["category_matches"].update(matches)

    result = {}
    for role, row in summaries.items():
        total = row["total_postings"]
        match_total = sum(row["category_matches"].values())
        skills = sorted(row["skills"].items(), key=lambda item: (-item[1], item[0].casefold(), item[0]))
        ranked = [{"skill": skill, "posting_count": count, "percentage": 100 * count / total,
                   "rank": rank} for rank, (skill, count) in enumerate(skills, 1)]
        category_totals = [
            {"category": category, "posting_count": count, "percentage": 100 * count / total,
             "match_count": row["category_matches"][category],
             "match_percentage": 100 * row["category_matches"][category] / match_total}
            for category, count in sorted(row["category_postings"].items())
        ]
        result[role] = {"total_postings": total, "skills": ranked,
                        "top_skills": ranked[:15], "categories": category_totals}
    return {"roles": result, "unresolved_roles": unresolved}


class MissingSkillTables(sqlite3.OperationalError):
    """The cleaned database still needs skill extraction."""


def read_summary(conn):
    """Use the TA4-25 SQLite schema while retaining postings without skills."""
    postings, _ = map_roles(dict(job_id=job_id, title=title)
                            for job_id, title in conn.execute("SELECT job_id, title FROM postings"))
    tables = {name for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )}
    if not {"skills", "posting_skills"} <= tables:
        raise MissingSkillTables("Run skill extraction on the selected database before opening the dashboard.")
    names_by_job = defaultdict(set)
    categories = {}
    skill_columns = {column[1] for column in conn.execute("PRAGMA table_info(skills)")}
    # The extractor uses skill_id. Earlier dashboard databases may use id.
    skill_key = "skill_id" if "skill_id" in skill_columns else "id"
    for job_id, name, category in conn.execute(f"""
        SELECT ps.job_id, s.name, s.category
        FROM posting_skills AS ps JOIN skills AS s ON s.{skill_key} = ps.skill_id
    """):
        names_by_job[job_id].add(name)
        categories[name] = category
    return summarize(
        ({**posting, "skills": names_by_job[posting["job_id"]]} for posting in postings),
        categories,
    )


def load_summary(database):
    with closing(sqlite3.connect(f"{Path(database).resolve().as_uri()}?mode=ro", uri=True)) as conn:
        return read_summary(conn)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(load_summary(args.database), indent=2))
    except sqlite3.Error as error:
        parser.exit(1, f"Build the cleaned database and run skill extraction first: {error}\n")


if __name__ == "__main__":
    main()
