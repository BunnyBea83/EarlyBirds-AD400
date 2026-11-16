"""Role comparison dropdown behaviour (TA4-60). Skipped when Streamlit's test runner is unavailable."""

import pytest

ROLES = {
    "Data Analyst": {"total_postings": 2, "skills": [
        {"skill": "SQL", "posting_count": 2}, {"skill": "Python", "posting_count": 1}]},
    "Data Scientist": {"total_postings": 2, "skills": [
        {"skill": "Python", "posting_count": 2}, {"skill": "Machine Learning", "posting_count": 1}]},
    "Marketing Manager": {"total_postings": 1, "skills": [{"skill": "Writing", "posting_count": 1}]},
}


def _comparison_app(roles):
    from birdseye.role_comparison_view import render_role_comparison

    render_role_comparison(roles)


@pytest.fixture
def app():
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    return AppTest.from_function(_comparison_app, args=(ROLES,)).run()


def test_both_dropdowns_list_every_role_alphabetically_at_first(app):
    assert not app.exception
    expected = ["Data Analyst", "Data Scientist", "Marketing Manager"]
    assert list(app.selectbox[0].options) == expected
    assert list(app.selectbox[1].options) == expected
    assert app.selectbox[0].value is None and app.selectbox[1].value is None
    assert [info.value for info in app.info] == ["Choose two roles to compare their skills."]


def test_a_role_chosen_in_one_dropdown_cannot_be_chosen_in_the_other(app):
    app.selectbox[0].select("Data Analyst").run()
    assert "Data Analyst" not in app.selectbox[1].options
    assert list(app.selectbox[1].options) == ["Data Scientist", "Marketing Manager"]
    app.selectbox[1].select("Marketing Manager").run()
    assert "Marketing Manager" not in app.selectbox[0].options
    assert app.selectbox[0].value == "Data Analyst"  # the first choice survives the second


def test_changing_either_role_updates_the_comparison(app):
    app.selectbox[0].select("Data Analyst").run()
    app.selectbox[1].select("Data Scientist").run()
    assert not app.exception
    assert list(app.info) == []
    assert app.caption[0].value == "Shared skills: 1. Only in Data Analyst: 1. Only in Data Scientist: 1."
    app.selectbox[1].select("Marketing Manager").run()
    assert app.caption[0].value == "Shared skills: 0. Only in Data Analyst: 2. Only in Marketing Manager: 1."
    app.selectbox[0].select("Data Scientist").run()
    assert app.caption[0].value == "Shared skills: 0. Only in Data Scientist: 2. Only in Marketing Manager: 1."