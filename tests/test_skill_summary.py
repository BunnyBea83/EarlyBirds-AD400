import sqlite3

import pytest

from birdseye.skill_summary import MissingSkillTables, read_summary, summarize


def test_counts_deduplicate_rank_and_distinguish_category_denominators():
    rows = [
        {"role": "Data Analyst", "skills": ["SQL", "Python", "Python", "Writing"]},
        {"role": "Data Analyst", "skills": []},
        {"role": "Unknown", "skills": ["SQL"]},
    ]
    result = summarize(rows, {"Python": "Software", "SQL": "Software"})
    analyst = result["roles"]["Data Analyst"]
    assert analyst["total_postings"] == 2
    assert [(s["skill"], s["posting_count"], s["percentage"], s["rank"])
            for s in analyst["top_skills"]] == [
        ("Python", 1, 50, 1), ("SQL", 1, 50, 2), ("Writing", 1, 50, 3),
    ]
    software, uncategorized = analyst["categories"]
    assert (software["posting_count"], software["percentage"], software["match_count"]) == (1, 50, 2)
    assert uncategorized["category"] == "Uncategorized"
    assert sum(category["match_percentage"] for category in analyst["categories"]) == 100
    assert result["unresolved_roles"]["Unknown"] == 1
    assert result["roles"]["Marketing Manager"]["top_skills"] == []


@pytest.mark.parametrize("skill_key", ["skill_id", "id"])
def test_database_reader_keeps_empty_postings_and_all_skills_for_heatmap(skill_key):
    conn = sqlite3.connect(":memory:")
    conn.executescript(f"""
        CREATE TABLE postings (job_id INTEGER, title TEXT);
        CREATE TABLE skills ({skill_key} INTEGER PRIMARY KEY, name TEXT, category TEXT);
        CREATE TABLE posting_skills (job_id INTEGER, skill_id INTEGER);
        INSERT INTO postings VALUES (1, 'Data Analyst'), (2, 'Sr. Data Analyst II');
    """)
    conn.executemany("INSERT INTO skills VALUES (?, ?, 'Software')",
                     [(i, f"Skill {i:02}") for i in range(21)])
    conn.executemany("INSERT INTO posting_skills VALUES (1, ?)", [(i,) for i in range(21)])
    analyst = read_summary(conn)["roles"]["Data Analyst"]
    conn.close()
    assert len(analyst["top_skills"]) == 15
    assert len(analyst["skills"]) == 21
    assert analyst["skills"][20]["percentage"] == 50


def test_cleaned_database_requires_extraction():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE postings (job_id INTEGER, title TEXT)")
        with pytest.raises(MissingSkillTables, match="Run skill extraction"):
            read_summary(conn)
    finally:
        conn.close()
