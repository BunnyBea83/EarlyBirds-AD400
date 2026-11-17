"""Top-skills ranking checks using small temporary SQLite databases (TA4-54)."""

import sqlite3
from contextlib import closing

import pytest

from birdseye.skill_ranking import TOP_N, combine_roles, load_top_skills, rank_skills, top_skills_all_postings
from birdseye.skill_storage import initialize_storage, save_posting_skills
from birdseye.skill_summary import load_summary
from birdseye.skills_catalog import SKILLS


def build_database(path, postings, links):
    """Create a cleaned-style database. postings is (job_id, title); links is {job_id: [skills]}."""
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE postings(job_id INTEGER, title TEXT, description TEXT)")
        conn.executemany("INSERT INTO postings(job_id, title) VALUES (?, ?)", postings)
        conn.commit()  # initialize_storage refuses to run inside an open transaction
        initialize_storage(conn)
        for job_id, names in links.items():
            save_posting_skills(conn, job_id, names)
        conn.commit()
    return path


def direct_counts(path, job_ids=None):
    """Count posting_skills rows with plain SQL, optionally for certain postings only."""
    query = "SELECT s.name, COUNT(*) FROM posting_skills AS ps JOIN skills AS s USING(skill_id)"
    params = ()
    if job_ids is not None:
        query += f" WHERE ps.job_id IN ({','.join('?' * len(job_ids))})"
        params = tuple(job_ids)
    with closing(sqlite3.connect(path)) as conn:
        return dict(conn.execute(query + " GROUP BY s.name", params))


def ranked(path):
    with closing(sqlite3.connect(path)) as conn:
        return top_skills_all_postings(conn)


@pytest.fixture
def database(tmp_path):
    return build_database(
        tmp_path / "birdseye.db",
        [(1, "Data Analyst"), (2, "Senior Data Analyst"), (3, "Data Analyst"),
         (4, "Registered Nurse"), (5, "Barista"), (6, "Marketing Manager")],
        {1: ["SQL", "Python", "Tableau"], 2: ["SQL", "Python"], 3: ["SQL"],
         4: ["Communication"], 5: ["Communication", "Python"]},
    )


def test_all_postings_figures_match_posting_skills_counts(database):
    result = ranked(database)
    expected = direct_counts(database)
    assert {row["skill"]: row["posting_count"] for row in result["top_skills"]} == expected
    assert result["total_postings"] == 6
    for row in result["top_skills"]:
        assert row["percentage"] == pytest.approx(100 * expected[row["skill"]] / 6)


def test_skills_are_ranked_by_count_then_alphabetically(database):
    result = ranked(database)
    assert [(row["rank"], row["skill"], row["posting_count"]) for row in result["top_skills"]] == [
        (1, "Python", 3), (2, "SQL", 3), (3, "Communication", 2), (4, "Tableau", 1),
    ]


def test_postings_without_skills_or_a_role_count_in_the_denominator(database):
    roles = load_summary(database)["roles"]
    all_postings = load_top_skills(database)
    assert all_postings["total_postings"] == 6
    assert sum(role["total_postings"] for role in roles.values()) == 5  # Barista has no role
    communication = next(row for row in all_postings["top_skills"] if row["skill"] == "Communication")
    assert communication["posting_count"] == 2  # includes the posting with no role


def test_only_the_top_15_are_returned(tmp_path):
    names = [skill.name for skill in SKILLS[:20]]
    path = build_database(tmp_path / "many.db", [(1, "A"), (2, "B")], {1: names, 2: names[:5]})
    result = ranked(path)
    assert TOP_N == 15 and len(result["top_skills"]) == 15
    counts = direct_counts(path)
    expected = sorted(counts, key=lambda name: (-counts[name], name.casefold()))[:15]
    assert [row["skill"] for row in result["top_skills"]] == expected


def test_database_without_postings_has_no_ranking(tmp_path):
    path = build_database(tmp_path / "empty.db", [], {})
    assert load_top_skills(path) == {"total_postings": 0, "top_skills": []}


def test_role_figures_match_posting_skills_counts(database):
    analyst = load_summary(database)["roles"]["Data Analyst"]  # jobs 1, 2 and 3
    expected = direct_counts(database, job_ids=(1, 2, 3))
    assert analyst["total_postings"] == 3
    assert {row["skill"]: row["posting_count"] for row in analyst["top_skills"]} == expected
    assert analyst["top_skills"][0]["percentage"] == pytest.approx(100.0)  # SQL is in all 3


def test_rank_skills_with_no_postings_does_not_divide_by_zero():
    assert rank_skills({"SQL": 0}, 0) == {"total_postings": 0, "top_skills": []}


def test_combine_roles_adds_up_role_counts():
    roles = {
        "A": {"total_postings": 2, "skills": [
            {"skill": "SQL", "posting_count": 2}, {"skill": "Git", "posting_count": 1}]},
        "B": {"total_postings": 2, "skills": [{"skill": "SQL", "posting_count": 1}]},
    }
    result = combine_roles(roles)
    assert result["total_postings"] == 4
    assert [(row["skill"], row["posting_count"], row["percentage"]) for row in result["top_skills"]] == [
        ("SQL", 3, 75.0), ("Git", 1, 25.0),
    ]