"""Role comparison grouping checks (TA4-59, subtask TA4-61)."""

import sqlite3
from contextlib import closing

import pytest

from birdseye.role_comparison import TOP_SKILLS, compare_roles, role_choices
from birdseye.skill_storage import initialize_storage, save_posting_skills
from birdseye.skill_summary import load_summary

ANALYST_JOBS = (1, 2, 3, 4)
SCIENTIST_JOBS = (5, 6)


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


@pytest.fixture
def database(tmp_path):
    """Data Analyst: 4 postings. Data Scientist: 2 postings."""
    return build_database(
        tmp_path / "birdseye.db",
        [(1, "Data Analyst"), (2, "Data Analyst"), (3, "Data Analyst"), (4, "Data Analyst"),
         (5, "Data Scientist"), (6, "Data Scientist")],
        {1: ["SQL", "Python", "Tableau"], 2: ["SQL", "Python"], 3: ["SQL"],
         4: ["Microsoft Excel"],
         5: ["Python", "Machine Learning", "SQL"], 6: ["Python", "Machine Learning", "PyTorch"]},
    )


def direct_counts(path, job_ids):
    """Count posting_skills rows for some postings with plain SQL."""
    marks = ",".join("?" * len(job_ids))
    with closing(sqlite3.connect(path)) as conn:
        return dict(conn.execute(f"""
            SELECT s.name, COUNT(*) FROM posting_skills AS ps JOIN skills AS s USING(skill_id)
            WHERE ps.job_id IN ({marks}) GROUP BY s.name
        """, job_ids))


def names(rows):
    return [row["skill"] for row in rows]


def compare(database, **kwargs):
    return compare_roles("Data Analyst", "Data Scientist", load_summary(database)["roles"], **kwargs)


def test_skills_are_sorted_into_shared_and_unique_groups(database):
    result = compare(database)
    assert TOP_SKILLS == 20
    assert names(result["shared"]) == ["Python", "SQL"]
    assert names(result["only_a"]) == ["Microsoft Excel", "Tableau"]
    assert names(result["only_b"]) == ["Machine Learning", "PyTorch"]


def test_figures_match_posting_skills_counts(database):
    result = compare(database)
    counts_a = direct_counts(database, ANALYST_JOBS)
    counts_b = direct_counts(database, SCIENTIST_JOBS)
    rows = result["shared"] + result["only_a"] + result["only_b"]
    assert {row["skill"] for row in rows} == set(counts_a) | set(counts_b)
    assert (result["total_a"], result["total_b"]) == (4, 2)
    for row in rows:
        a, b = counts_a.get(row["skill"], 0), counts_b.get(row["skill"], 0)
        assert (row["count_a"], row["count_b"]) == (a, b)
        assert row["share_a"] == pytest.approx(100 * a / 4)  # each role's own posting count
        assert row["share_b"] == pytest.approx(100 * b / 2)
        assert row["combined_share"] == pytest.approx(100 * (a + b) / 6)  # pooled postings


def test_shared_skills_are_sorted_by_combined_demand(database):
    # SQL: 3 of 4 analyst + 1 of 2 scientist postings; Python: 2 of 4 + 2 of 2. Both are 4 of 6.
    shared = compare(database)["shared"]
    assert [row["combined_share"] for row in shared] == pytest.approx([100 * 4 / 6] * 2)
    assert names(shared) == ["Python", "SQL"]  # a tie, so alphabetical


def test_unique_skills_are_sorted_by_their_share_in_their_own_role(database):
    only_b = compare(database)["only_b"]
    assert [row["share_b"] for row in only_b] == [100.0, 50.0]  # Machine Learning, PyTorch


def test_a_skill_outside_the_other_roles_top_list_keeps_its_real_share(database):
    # With a top-2 cutoff the scientist's top two are Machine Learning and Python, so SQL
    # (1 of 2 scientist postings) is unique to the analyst but still shows 50% for the scientist.
    result = compare(database, size=2)
    assert names(result["shared"]) == ["Python"]
    assert names(result["only_a"]) == ["SQL"]
    assert names(result["only_b"]) == ["Machine Learning"]
    sql = result["only_a"][0]
    assert (sql["share_a"], sql["share_b"]) == (75.0, 50.0)
    assert result["only_b"][0]["share_a"] == 0.0  # the analyst never mentions it


def test_swapping_the_roles_swaps_the_groups(database):
    roles = load_summary(database)["roles"]
    forward = compare_roles("Data Analyst", "Data Scientist", roles)
    backward = compare_roles("Data Scientist", "Data Analyst", roles)
    assert names(forward["only_a"]) == names(backward["only_b"])
    assert names(forward["shared"]) == names(backward["shared"])


def test_the_same_role_cannot_be_compared_with_itself(database):
    with pytest.raises(ValueError, match="two different roles"):
        compare_roles("Data Analyst", "Data Analyst", load_summary(database)["roles"])


def test_unknown_roles_are_rejected():
    with pytest.raises(ValueError, match="Unknown role: Astronaut"):
        compare_roles("Astronaut", "Data Analyst", {"Data Analyst": {"total_postings": 0, "skills": []}})


def test_roles_without_postings_compare_without_dividing_by_zero():
    empty = {"total_postings": 0, "skills": []}
    result = compare_roles("A", "B", {"A": empty, "B": empty})
    assert result["shared"] == result["only_a"] == result["only_b"] == []
    assert (result["total_a"], result["total_b"]) == (0, 0)


# --- Role dropdown choices (TA4-60) ---

def test_dropdown_lists_every_role_alphabetically_ignoring_case():
    roles = ["Software Engineer", "data Analyst", "Data Scientist", "Registered Nurse"]
    assert role_choices(roles) == ["data Analyst", "Data Scientist", "Registered Nurse", "Software Engineer"]


def test_the_other_dropdowns_role_is_left_out():
    roles = ["Data Analyst", "Data Scientist", "Registered Nurse"]
    assert role_choices(roles, exclude="Data Scientist") == ["Data Analyst", "Registered Nurse"]
    assert role_choices(roles, exclude=None) == sorted(roles)
    assert role_choices(roles, exclude="Not a role") == sorted(roles)


def test_each_role_is_listed_once():
    assert role_choices(["A", "B", "A"]) == ["A", "B"]


def test_dropdowns_use_the_summary_role_list(database):
    roles = load_summary(database)["roles"]
    assert role_choices(roles) == sorted(roles)  # every ROLE_RULES role, alphabetical
    assert len(role_choices(roles)) == 7