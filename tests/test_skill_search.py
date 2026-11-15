"""Skill Input checks using a small temporary SQLite database."""

import sqlite3
from contextlib import closing

import pytest

from birdseye.skill_search import clean_selection, list_skills, normalize_term, search_skills
from birdseye.skill_storage import initialize_storage
from birdseye.skills_catalog import SKILLS


@pytest.fixture
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "skills.db")
    connection.execute("CREATE TABLE postings(job_id INTEGER, description TEXT)")
    initialize_storage(connection)
    yield connection
    connection.close()


def names(skills):
    return [skill.name for skill in skills]


def test_skills_are_listed_alphabetically_ignoring_case(conn):
    listed = names(list_skills(conn))
    assert listed == sorted(listed, key=str.casefold)
    assert listed.index("pandas") < listed.index("PostgreSQL")  # not ASCII order


def test_every_catalog_skill_is_listed_once(conn):
    listed = names(list_skills(conn))
    assert len(listed) == len(set(listed)) == len(SKILLS)


def test_new_database_skills_appear_in_alphabetical_position(conn):
    with conn:
        cursor = conn.execute("INSERT INTO skills(name) VALUES ('Technical Writing')")
        conn.execute("INSERT INTO skill_aliases VALUES ('documentation writing', ?)", (cursor.lastrowid,))
    listed = names(list_skills(conn))
    assert listed == sorted(listed, key=str.casefold)
    assert names(search_skills(conn, "Documentation Writing")) == ["Technical Writing"]


@pytest.mark.parametrize("query, expected", [
    ("MS Excel", ["Microsoft Excel"]),
    ("Excel", ["Microsoft Excel"]),
    ("Postgres", ["PostgreSQL"]),
    ("k8s", ["Kubernetes"]),
    ("C Sharp", ["C#"]),
    ("  ms   EXCEL ", ["Microsoft Excel"]),
])
def test_typing_a_synonym_finds_the_standard_skill(conn, query, expected):
    assert names(search_skills(conn, query)) == expected


def test_skill_with_several_matching_aliases_appears_once(conn):
    # "react" matches the name and the aliases React.js and ReactJS.
    assert names(search_skills(conn, "react")) == ["React"]


def test_search_results_are_alphabetical(conn):
    results = names(search_skills(conn, "sql"))
    assert {"MySQL", "PostgreSQL", "SQL", "SQLite"} <= set(results)
    assert results == sorted(results, key=str.casefold)


@pytest.mark.parametrize("query", ["", "   ", "\t"])
def test_blank_search_lists_every_skill(conn, query):
    assert search_skills(conn, query) == list_skills(conn)


@pytest.mark.parametrize("query", ["zzz-not-a-skill", "%", "_", "\\"])
def test_no_match_returns_nothing_and_wildcards_are_literal(conn, query):
    assert search_skills(conn, query) == []


def test_normalize_matches_catalog_rules():
    assert normalize_term("  MS   Excel ") == "ms excel"


def test_clean_selection_removes_duplicates_and_unknown_ids_in_order():
    assert clean_selection([3, 1, 3, 99, 2, 1], valid_ids=[1, 2, 3]) == [3, 1, 2]
    assert clean_selection([], valid_ids=[1]) == []


# --- Streamlit behaviour (skipped when Streamlit's test runner is unavailable) ---

def _skill_input_app(db_path):
    import sqlite3
    from contextlib import closing

    from birdseye.skill_input import render_skill_input

    with closing(sqlite3.connect(db_path)) as connection:
        render_skill_input(connection)


@pytest.fixture
def app(tmp_path):
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    path = tmp_path / "ui.db"
    with closing(sqlite3.connect(path)) as setup:
        setup.execute("CREATE TABLE postings(job_id INTEGER, description TEXT)")
        initialize_storage(setup)
    return AppTest.from_function(_skill_input_app, args=(str(path),)), path


def test_empty_selection_shows_a_prompt(app):
    at, _ = app
    at.run()
    assert not at.exception
    assert [info.value for info in at.info] == ["Select at least one skill to see how you compare."]


def test_several_skills_can_be_selected_and_the_prompt_goes_away(app):
    at, path = app
    with closing(sqlite3.connect(path)) as check:
        ids = [skill.skill_id for skill in list_skills(check) if skill.name in {"Python", "Microsoft Excel"}]
    at.session_state["selected_skill_ids"] = ids
    at.run()
    assert not at.exception
    assert list(at.info) == []
    assert at.multiselect[0].value == ids


def test_removing_one_selected_skill_keeps_the_others(app):
    at, path = app
    with closing(sqlite3.connect(path)) as check:
        ids = [skill.skill_id for skill in list_skills(check)][:3]
    at.session_state["selected_skill_ids"] = ids
    at.run()
    at.session_state["selected_skill_ids"] = ids[:1] + ids[2:]
    at.run()
    assert at.multiselect[0].value == ids[:1] + ids[2:]
    at.session_state["selected_skill_ids"] = []
    at.run()
    assert len(at.info) == 1


def test_selection_survives_searching_for_something_else(app):
    at, path = app
    with closing(sqlite3.connect(path)) as check:
        python_id = next(s.skill_id for s in list_skills(check) if s.name == "Python")
    at.session_state["selected_skill_ids"] = [python_id]
    at.run()
    at.text_input[0].set_value("MS Excel").run()
    assert not at.exception
    assert at.multiselect[0].value == [python_id]