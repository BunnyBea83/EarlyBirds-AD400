"""The skill match section on the page (TA4-48, TA4-50). Skipped when Streamlit's test runner is unavailable."""

import pytest

PROFILE = [
    {"skill": "SQL", "percentage": 80.0},
    {"skill": "Python", "percentage": 60.0},
    {"skill": "Tableau", "percentage": 20.0},
]


def _gap_app(role, profile, have_skills):
    from birdseye.skill_gap_view import render_skill_gap

    render_skill_gap(role, profile, have_skills)


@pytest.fixture
def make_app():
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    return lambda role, profile, have: AppTest.from_function(_gap_app, args=(role, profile, have)).run()


def test_no_role_chosen_asks_for_one(make_app):
    app = make_app(None, None, {"SQL"})
    assert not app.exception
    assert [info.value for info in app.info] == [
        'Choose a role under "Role skill profile" to compare your skills with it.']
    assert len(app.metric) == 0


def test_no_skills_chosen_asks_for_skills(make_app):
    app = make_app("Data Analyst", PROFILE, set())
    assert [info.value for info in app.info] == [
        'Add your skills under "Your skills" to see how well they match this role.']
    assert len(app.metric) == 0


def test_a_role_without_a_stored_profile_shows_nothing_here(make_app):
    app = make_app("Data Analyst", None, {"SQL"})
    assert not app.exception and len(app.metric) == 0 and len(app.info) == 0


def test_a_role_whose_skills_are_all_too_rare_explains_the_minimum_share(make_app):
    app = make_app("Data Analyst", [], {"SQL"})
    assert [info.value for info in app.info] == ["No skills meet the minimum posting share for this role."]
    assert len(app.metric) == 0


def test_the_match_is_shown_as_a_count_with_the_word_match(make_app):
    app = make_app("Data Analyst", PROFILE, {"SQL", "Tableau"})
    assert not app.exception
    assert app.metric[0].label == "Your match with Data Analyst"
    assert app.metric[0].value == "2 out of 3"
    assert "%" not in app.metric[0].value


def test_skills_are_split_into_have_and_missing_ordered_by_demand(make_app):
    app = make_app("Data Analyst", PROFILE, {"Tableau", "SQL"})
    assert [header.value for header in app.subheader] == ["You have (2)", "Missing (1)"]
    have, missing = app.dataframe[0].value, app.dataframe[1].value
    assert have["Skill"].tolist() == ["SQL", "Tableau"]
    assert missing["Skill"].tolist() == ["Python"]
    assert missing["Share of Data Analyst postings"].tolist() == ["60%"]


def test_having_every_skill_leaves_nothing_missing(make_app):
    app = make_app("Data Analyst", PROFILE, {"SQL", "Python", "Tableau"})
    assert app.metric[0].value == "3 out of 3"
    assert [header.value for header in app.subheader] == ["You have (3)", "Missing (0)"]
    assert len(app.dataframe) == 1