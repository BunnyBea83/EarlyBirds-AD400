"""Role comparison grouping checks (TA4-59, subtask TA4-61)."""

import re
import sqlite3
from contextlib import closing

import pytest

from birdseye.role_comparison import (
    TOP_SKILLS, compare_roles, comparison_rows, describe_comparison, role_choices,
)
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


# --- Side-by-side table rows (TA4-62) ---

def test_table_has_a_column_per_role_named_after_the_role(database):
    rows = comparison_rows(compare(database))
    assert list(rows[0]) == ["Group", "Skill", "Data Analyst", "Data Scientist"]
    assert all(list(row) == list(rows[0]) for row in rows)


def test_rows_are_grouped_shared_first_then_each_roles_unique_skills(database):
    rows = comparison_rows(compare(database))
    assert [(row["Group"], row["Skill"]) for row in rows] == [
        ("Shared", "Python"), ("Shared", "SQL"),
        ("Unique to Data Analyst", "Microsoft Excel"), ("Unique to Data Analyst", "Tableau"),
        ("Unique to Data Scientist", "Machine Learning"), ("Unique to Data Scientist", "PyTorch"),
    ]


def test_table_shows_each_skills_share_of_each_roles_own_postings(database):
    by_skill = {row["Skill"]: row for row in comparison_rows(compare(database))}
    assert (by_skill["Python"]["Data Analyst"], by_skill["Python"]["Data Scientist"]) == (50.0, 100.0)
    assert (by_skill["SQL"]["Data Analyst"], by_skill["SQL"]["Data Scientist"]) == (75.0, 50.0)
    assert (by_skill["Tableau"]["Data Analyst"], by_skill["Tableau"]["Data Scientist"]) == (25.0, 0.0)
    assert (by_skill["PyTorch"]["Data Analyst"], by_skill["PyTorch"]["Data Scientist"]) == (0.0, 50.0)


def test_each_group_runs_from_most_to_least_in_demand(database):
    rows = comparison_rows(compare(database))
    scientist_only = [row["Data Scientist"] for row in rows if row["Group"] == "Unique to Data Scientist"]
    assert scientist_only == sorted(scientist_only, reverse=True) == [100.0, 50.0]


def test_a_group_with_no_skills_has_no_rows():
    one_sided = {"A": {"total_postings": 1, "skills": [{"skill": "SQL", "posting_count": 1}]},
                 "B": {"total_postings": 1, "skills": []}}
    rows = comparison_rows(compare_roles("A", "B", one_sided))
    assert [(row["Group"], row["Skill"]) for row in rows] == [("Unique to A", "SQL")]


# --- Plain-language paragraph (TA4-63) ---

def skill_row(skill, share_a=0.0, share_b=0.0):
    return {"skill": skill, "share_a": share_a, "share_b": share_b, "combined_share": 0.0}


def comparison(role_a, role_b, shared=(), only_a=(), only_b=()):
    return {"role_a": role_a, "role_b": role_b, "shared": list(shared),
            "only_a": list(only_a), "only_b": list(only_b)}


def sentence_count(text):
    return text.count(". ") + 1  # skill names here have no ". " inside them


TYPICAL = comparison(
    "Data Analyst", "Data Scientist",
    shared=[skill_row("Python", 50, 100), skill_row("SQL", 75, 50)] + [skill_row(f"Shared {n}", 10, 10) for n in range(6)],
    only_a=[skill_row("Tableau", 25, 0), skill_row("Microsoft Excel", 25, 0)],
    only_b=[skill_row("Machine Learning", 0, 100), skill_row("PyTorch", 0, 50)],
)
LITTLE = comparison(
    "Data Analyst", "Registered Nurse",
    shared=[skill_row("Communication", 30, 80)],
    only_a=[skill_row("SQL", 75, 0), skill_row("Python", 50, 0)],
    only_b=[skill_row("Patient Care", 0, 90), skill_row("Documentation", 0, 60)],
)
NONE_SHARED = comparison(
    "Data Analyst", "Registered Nurse",
    only_a=[skill_row("SQL", 75, 0), skill_row("Python", 50, 0)],
    only_b=[skill_row("Patient Care", 0, 90), skill_row("Documentation", 0, 60)],
)
ONE_SIDED = comparison(
    "Data Analyst", "Data Scientist",
    shared=[skill_row("Python", 50, 100), skill_row("SQL", 75, 50)] + [skill_row(f"S{n}", 5, 5) for n in range(3)],
    only_a=[skill_row("Tableau", 25, 0)],
)
IDENTICAL = comparison("Data Analyst", "Data Scientist", shared=[skill_row("Python", 50, 100), skill_row("SQL", 75, 50)])
NO_SKILLS = comparison("Project Manager", "Marketing Manager", only_b=[skill_row("Writing", 0, 100)])

# Phrases that claim more than the top-20 overlap shows (reviewer feedback on TA4-59).
# Whole words only, so skill names such as "Machine Learning" don't trip it.
OVERREACHING = (r"\beasier\b", r"\bharder\b", r"\bswitch\w*", r"\blearn\b", r"\bsafest\b", r"\bshould\b",
                r"\bexpect\b", r"\bmove\b", r"mostly new", r"little in common", r"good next", r"\bstart(ing)? with\b")


def test_typical_pair_gets_the_reviewed_paragraph():
    assert describe_comparison(TYPICAL) == (
        "Data Analyst and Data Scientist job postings overlap quite a bit: 8 of the 20 skills most often "
        "requested for each role are the same. Both roles frequently ask for Python (mentioned in 50% of "
        "Data Analyst postings and 100% of Data Scientist postings) and SQL (75% and 50%). Data Analyst "
        "postings also stand out for Tableau (25% of Data Analyst postings) and Microsoft Excel (25%), "
        "which are not among the top 20 for Data Scientist. Data Scientist postings stand out for Machine "
        "Learning (100% of Data Scientist postings) and PyTorch (50%), which are not among the top 20 for "
        "Data Analyst. If you are comparing these roles, the shared skills are the ones postings for both "
        "roles ask for, and it may be worth looking into learning the most requested skill found in only "
        "one role's top 20 for the role you want: Tableau for Data Analyst or Machine Learning for Data "
        "Scientist."
    )


def test_pair_with_one_shared_skill_gets_the_reviewed_paragraph():
    assert describe_comparison(LITTLE) == (
        "Data Analyst and Registered Nurse job postings share few of their most requested skills: only 1 of "
        "the 20 skills most often requested for each role is the same. Both roles ask for Communication "
        "(mentioned in 30% of Data Analyst postings and 80% of Registered Nurse postings). Data Analyst "
        "postings stand out for SQL (75% of Data Analyst postings) and Python (50%), which are not among "
        "the top 20 for Registered Nurse. Registered Nurse postings stand out for Patient Care (90% of "
        "Registered Nurse postings) and Documentation (60%), which are not among the top 20 for Data "
        "Analyst. If you are comparing these roles, the shared skills are the ones postings for both roles "
        "ask for, and it may be worth looking into learning the most requested skill found in only one "
        "role's top 20 for the role you want: SQL for Data Analyst or Patient Care for Registered Nurse."
    )


def test_paragraph_is_three_to_five_sentences_and_names_two_shared_and_two_unique_skills_with_shares():
    text = describe_comparison(TYPICAL)
    assert 3 <= sentence_count(text) <= 5
    for skill in ("Python", "SQL", "Tableau", "Microsoft Excel", "Machine Learning", "PyTorch"):
        assert skill in text
    assert text.count("%") == 8  # two shared skills x two roles, plus two unique skills per role
    assert text.rstrip(".").split(". ")[-1].startswith("If you are comparing these roles")  # closing sentence


def test_roles_with_no_shared_skills_say_so_without_predicting_anything():
    text = describe_comparison(NONE_SHARED)
    assert text == (
        "These two roles share none of the 20 skills most often requested for each. Data Analyst postings "
        "stand out for SQL (75% of Data Analyst postings) and Python (50%), which are not among the top 20 "
        "for Registered Nurse. Registered Nurse postings stand out for Patient Care (90% of Registered "
        "Nurse postings) and Documentation (60%), which are not among the top 20 for Data Analyst. If you "
        "are comparing these roles, it may be worth looking into learning the most requested skill found "
        "in only one role's top 20 for the role you want: SQL for Data Analyst or Patient Care for "
        "Registered Nurse."
    )
    assert "also stand out" not in text
    assert 3 <= sentence_count(text) <= 5


def test_a_role_with_no_unique_skills_is_described_by_the_overlap_only():
    text = describe_comparison(ONE_SIDED)
    assert "job postings have some skills in common: 5 of the 20" in text
    assert "Data Analyst postings also stand out for Tableau (25% of Data Analyst postings), which is not among " \
           "the top 20 for Data Scientist." in text
    assert "Every one of the top 20 skills for Data Scientist is also among the top 20 for Data Analyst." in text
    assert text.endswith(
        "if you are interested in Data Analyst, it may be worth looking into learning Tableau, the most "
        "requested skill in its top 20 that is not in the top 20 for Data Scientist."
    )


def test_roles_with_identical_top_skills_say_so_and_nothing_more():
    assert describe_comparison(IDENTICAL) == (
        "Data Analyst and Data Scientist job postings ask for the same most requested skills. Both roles "
        "frequently ask for Python (mentioned in 50% of Data Analyst postings and 100% of Data Scientist "
        "postings) and SQL (75% and 50%). If you are comparing these roles, the shared skills are the ones "
        "postings for both roles ask for."
    )


@pytest.mark.parametrize("case, suggested, not_suggested", [
    (TYPICAL, ["Tableau for Data Analyst", "Machine Learning for Data Scientist"], ["Microsoft Excel", "PyTorch"]),
    (LITTLE, ["SQL for Data Analyst", "Patient Care for Registered Nurse"], ["Python", "Documentation"]),
    (NONE_SHARED, ["SQL for Data Analyst", "Patient Care for Registered Nurse"], ["Python", "Documentation"]),
], ids=["many shared", "one shared", "none shared"])
def test_the_closing_sentence_suggests_only_each_roles_most_requested_unique_skill(case, suggested, not_suggested):
    closing_sentence = describe_comparison(case).split(". ")[-1]
    assert "it may be worth looking into learning the most requested skill found in only one role's top 20" \
        in closing_sentence
    for skill_for_role in suggested:
        assert skill_for_role in closing_sentence
    for skill in not_suggested:  # the second-ranked unique skills are named earlier, not suggested
        assert skill not in closing_sentence


def test_identical_top_skills_leave_nothing_to_suggest():
    assert "worth looking into" not in describe_comparison(IDENTICAL)


@pytest.mark.parametrize("case", [TYPICAL, LITTLE, NONE_SHARED, ONE_SIDED, IDENTICAL],
                         ids=["typical", "one shared", "none shared", "one side has no unique", "identical"])
def test_the_paragraph_only_reports_the_overlap_and_makes_no_predictions_or_advice(case):
    text = describe_comparison(case).lower()
    for pattern in OVERREACHING:
        assert not re.search(pattern, text), pattern


def test_a_role_with_no_skills_found_gets_one_explanatory_sentence():
    assert describe_comparison(NO_SKILLS) == (
        "We didn't find any skills in the Project Manager postings yet, so a comparison with "
        "Marketing Manager isn't possible."
    )
    both_missing = comparison("Project Manager", "Registered Nurse")
    assert describe_comparison(both_missing) == (
        "We didn't find any skills in the Project Manager or Registered Nurse postings yet, "
        "so a comparison isn't possible."
    )


@pytest.mark.parametrize("share, text", [
    (0.0, "0%"), (0.2, "less than 1%"), (0.49, "less than 1%"), (0.5, "1%"), (12.5, "13%"),
    (49.6, "50%"), (99.6, "100%"), (100.0, "100%"),
])
def test_percentages_are_whole_numbers(share, text):
    result = comparison("A", "B", only_a=[skill_row("SQL", share, 0)], only_b=[skill_row("Git", 0, 5)])
    assert f"SQL ({text} of A postings)" in describe_comparison(result)


def test_paragraph_matches_the_figures_in_the_table(database):
    result = compare(database)
    text = describe_comparison(result)
    assert text == (
        "Data Analyst and Data Scientist job postings share few of their most requested skills: only 2 of "
        "the 20 skills most often requested for each role are the same. Both roles frequently ask for "
        "Python (mentioned in 50% of Data Analyst postings and 100% of Data Scientist postings) and SQL "
        "(75% and 50%). Data Analyst postings also stand out for Microsoft Excel (25% of Data Analyst "
        "postings) and Tableau (25%), which are not among the top 20 for Data Scientist. Data Scientist "
        "postings stand out for Machine Learning (100% of Data Scientist postings) and PyTorch (50%), which "
        "are not among the top 20 for Data Analyst. If you are comparing these roles, the shared skills are "
        "the ones postings for both roles ask for, and it may be worth looking into learning the most "
        "requested skill found in only one role's top 20 for the role you want: Microsoft Excel for Data "
        "Analyst or Machine Learning for Data Scientist."
    )
    by_skill = {row["Skill"]: row for row in comparison_rows(result)}
    assert by_skill["SQL"]["Data Analyst"] == 75.0 and by_skill["Machine Learning"]["Data Scientist"] == 100.0