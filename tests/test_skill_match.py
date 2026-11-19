"""Skill match checks (TA4-50, TA4-48)."""

import sqlite3
from contextlib import closing

import pytest

from birdseye.skill_match import match_label, match_skills
from birdseye.skill_search import list_skills, search_skills
from birdseye.skill_storage import initialize_storage

PROFILE = [
    {"skill": "Tableau", "percentage": 20.0},
    {"skill": "SQL", "percentage": 80.0},
    {"skill": "Python", "percentage": 60.0},
]


def names(rows):
    return [row["skill"] for row in rows]


def test_the_match_counts_how_many_of_the_profile_skills_the_person_has():
    result = match_skills(PROFILE, ["SQL", "Tableau"])
    assert (result["matched"], result["total"]) == (2, 3)
    assert match_label(result) == "2 out of 3"


def test_skills_are_split_into_have_and_missing():
    result = match_skills(PROFILE, ["SQL", "Tableau"])
    assert names(result["have"]) == ["SQL", "Tableau"]
    assert names(result["missing"]) == ["Python"]
    assert len(result["have"]) + len(result["missing"]) == result["total"]


def test_missing_skills_are_ordered_by_demand_and_so_are_the_skills_you_have():
    assert names(match_skills(PROFILE, [])["missing"]) == ["SQL", "Python", "Tableau"]
    assert names(match_skills(PROFILE, ["Tableau", "Python"])["have"]) == ["Python", "Tableau"]


def test_ties_are_sorted_alphabetically():
    tied = [{"skill": "git", "percentage": 50.0}, {"skill": "Docker", "percentage": 50.0}]
    assert names(match_skills(tied, [])["missing"]) == ["Docker", "git"]


def test_having_no_skills_or_all_skills():
    assert match_label(match_skills(PROFILE, [])) == "0 out of 3"
    assert match_label(match_skills(PROFILE, ["SQL", "Python", "Tableau"])) == "3 out of 3"


def test_skills_outside_the_profile_do_not_count_and_letter_case_is_ignored():
    result = match_skills(PROFILE, ["sql", "Underwater Basket Weaving"])
    assert names(result["have"]) == ["SQL"]
    assert match_label(result) == "1 out of 3"


def test_the_total_follows_the_profile_length_not_a_fixed_twenty():
    short = [{"skill": f"Skill {n}", "percentage": 10.0} for n in range(4)]
    assert match_label(match_skills(short, ["Skill 1"])) == "1 out of 4"
    full = [{"skill": f"Skill {n}", "percentage": 10.0} for n in range(20)]
    assert match_label(match_skills(full, ["Skill 1", "Skill 2"])) == "2 out of 20"


def test_a_role_with_no_profile_has_nothing_to_match():
    assert match_skills([], ["SQL"]) == {"matched": 0, "total": 0, "have": [], "missing": []}


def test_the_input_profile_is_not_changed():
    profile = [dict(row) for row in PROFILE]
    match_skills(profile, ["SQL"])
    assert profile == PROFILE


# --- A synonym picked in the skill picker matches the standard skill name ---

@pytest.fixture
def conn(tmp_path):
    with closing(sqlite3.connect(tmp_path / "skills.db")) as connection:
        connection.execute("CREATE TABLE postings(job_id INTEGER, title TEXT, description TEXT)")
        connection.commit()
        initialize_storage(connection)
        yield connection


def test_ms_excel_and_excel_both_match_the_microsoft_excel_profile_skill(conn):
    profile = [{"skill": "Microsoft Excel", "percentage": 40.0}, {"skill": "SQL", "percentage": 30.0}]
    by_name = {skill.name: skill for skill in list_skills(conn)}
    assert "Microsoft Excel" in by_name  # the catalog has the standard name
    for typed in ("MS Excel", "Excel"):
        found = search_skills(conn, typed)
        assert "Microsoft Excel" in [skill.name for skill in found], typed
        picked = [skill.name for skill in found if skill.name == "Microsoft Excel"]
        result = match_skills(profile, picked)
        assert names(result["have"]) == ["Microsoft Excel"], typed
        assert names(result["missing"]) == ["SQL"]