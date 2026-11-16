"""Role comparison dropdown and table behaviour (TA4-60, TA4-62). Skipped when Streamlit's test runner is unavailable."""

import pytest

ROLES = {
    "Data Analyst": {"total_postings": 2, "skills": [
        {"skill": "SQL", "posting_count": 2}, {"skill": "Python", "posting_count": 1}]},
    "Data Scientist": {"total_postings": 2, "skills": [
        {"skill": "Python", "posting_count": 2}, {"skill": "Machine Learning", "posting_count": 1}]},
    "Marketing Manager": {"total_postings": 1, "skills": [{"skill": "Writing", "posting_count": 1}]},
    "Project Manager": {"total_postings": 3, "skills": []},
    "Registered Nurse": {"total_postings": 1, "skills": []},
}
ALL_ROLES = sorted(ROLES)


def _comparison_app(roles):
    from birdseye.role_comparison_view import render_role_comparison

    render_role_comparison(roles)


@pytest.fixture
def app():
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    return AppTest.from_function(_comparison_app, args=(ROLES,)).run()


def table(app):
    frame = app.dataframe[0].value
    return list(frame.columns), frame.values.tolist()


def test_both_dropdowns_list_every_role_alphabetically_at_first(app):
    assert not app.exception
    assert list(app.selectbox[0].options) == ALL_ROLES
    assert list(app.selectbox[1].options) == ALL_ROLES
    assert app.selectbox[0].value is None and app.selectbox[1].value is None
    assert [info.value for info in app.info] == ["Choose two roles to compare their skills."]
    assert len(app.dataframe) == 0


def test_a_role_chosen_in_one_dropdown_cannot_be_chosen_in_the_other(app):
    app.selectbox[0].select("Data Analyst").run()
    assert list(app.selectbox[1].options) == [role for role in ALL_ROLES if role != "Data Analyst"]
    app.selectbox[1].select("Marketing Manager").run()
    assert "Marketing Manager" not in app.selectbox[0].options
    assert app.selectbox[0].value == "Data Analyst"  # the first choice survives the second


def test_the_table_has_a_column_per_role_with_grouped_rows(app):
    app.selectbox[0].select("Data Analyst").run()
    app.selectbox[1].select("Data Scientist").run()
    assert not app.exception
    assert list(app.info) == []
    columns, rows = table(app)
    assert columns == ["Group", "Skill", "Data Analyst", "Data Scientist"]
    assert rows == [
        ["Shared", "Python", 50.0, 100.0],
        ["Unique to Data Analyst", "SQL", 100.0, 0.0],
        ["Unique to Data Scientist", "Machine Learning", 0.0, 50.0],
    ]


def test_each_roles_posting_count_is_shown_above_the_table(app):
    app.selectbox[0].select("Data Analyst").run()
    app.selectbox[1].select("Project Manager").run()
    counts = [m.value for m in app.markdown if m.value.startswith("**")]
    assert counts == ["**Data Analyst:** 2 postings · **Project Manager:** 3 postings"]


def test_changing_either_role_updates_the_table(app):
    app.selectbox[0].select("Data Analyst").run()
    app.selectbox[1].select("Data Scientist").run()
    app.selectbox[1].select("Marketing Manager").run()
    columns, rows = table(app)
    assert columns == ["Group", "Skill", "Data Analyst", "Marketing Manager"]
    assert rows == [
        ["Unique to Data Analyst", "SQL", 100.0, 0.0],
        ["Unique to Data Analyst", "Python", 50.0, 0.0],
        ["Unique to Marketing Manager", "Writing", 0.0, 100.0],
    ]
    app.selectbox[0].select("Data Scientist").run()
    assert table(app)[0] == ["Group", "Skill", "Data Scientist", "Marketing Manager"]


def test_roles_without_any_skills_show_a_message_instead_of_a_table(app):
    app.selectbox[0].select("Project Manager").run()
    app.selectbox[1].select("Registered Nurse").run()
    assert not app.exception
    assert len(app.dataframe) == 0
    assert [info.value for info in app.info] == [
        "No skills were found in the postings for these roles, so there is nothing to compare yet."
    ]


def test_a_plain_language_paragraph_comes_before_the_counts_and_table_and_follows_the_roles(app):
    from birdseye.role_comparison import compare_roles, describe_comparison

    app.selectbox[0].select("Data Analyst").run()
    app.selectbox[1].select("Data Scientist").run()
    texts = [m.value for m in app.markdown]
    paragraph = describe_comparison(compare_roles("Data Analyst", "Data Scientist", ROLES))
    assert paragraph in texts
    assert texts.index(paragraph) < texts.index("**Data Analyst:** 2 postings \u00b7 **Data Scientist:** 2 postings")
    app.selectbox[1].select("Marketing Manager").run()
    assert describe_comparison(compare_roles("Data Analyst", "Marketing Manager", ROLES)) in [m.value for m in app.markdown]