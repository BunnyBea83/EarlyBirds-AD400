"""Skill Input checks using a small temporary SQLite database."""

import sqlite3
from contextlib import closing

import pytest

from birdseye.skill_search import (
    clean_selection, list_skills, normalize_term, search_skills, skill_label, skill_synonyms,
)
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


def test_synonyms_exclude_the_canonical_name(conn):
    by_name = {skill.name: skill.skill_id for skill in list_skills(conn)}
    synonyms = skill_synonyms(conn)
    assert synonyms[by_name["Microsoft Excel"]] == ["ms excel"]
    assert synonyms[by_name["React"]] == ["react.js", "reactjs"]
    assert by_name["Python"] not in synonyms


def test_label_includes_synonyms_so_the_picker_can_filter_on_them():
    assert skill_label("Microsoft Excel", ["ms excel"]) == "Microsoft Excel (ms excel)"
    assert skill_label("Python") == "Python"


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


def skill_ids(path, *wanted):
    with closing(sqlite3.connect(path)) as check:
        by_name = {skill.name: skill.skill_id for skill in list_skills(check)}
    return [by_name[name] for name in wanted]


def test_empty_selection_shows_a_prompt(app):
    at, _ = app
    at.run()
    assert not at.exception
    assert [info.value for info in at.info] == ["Select at least one skill to see how you compare."]
    assert len(at.button) == 0


def test_options_include_synonyms_so_typing_one_finds_the_skill(app):
    at, _ = app
    at.run()
    assert "Microsoft Excel (ms excel)" in at.selectbox[0].options


def test_picking_a_skill_adds_it_as_a_separate_item_and_resets_the_box(app):
    at, path = app
    at.run()
    at.selectbox[0].select("Microsoft Excel (ms excel)").run()
    assert not at.exception
    assert at.session_state["selected_skill_ids"] == skill_ids(path, "Microsoft Excel")
    assert at.selectbox[0].value is None
    assert "Microsoft Excel (ms excel)" not in at.selectbox[0].options  # no duplicates
    assert list(at.info) == []
    assert [button.label for button in at.button] == ["Microsoft Excel"]


def test_several_skills_can_be_added(app):
    at, path = app
    at.run()
    at.selectbox[0].select("Python").run()
    at.selectbox[0].select("Docker").run()
    assert at.session_state["selected_skill_ids"] == skill_ids(path, "Python", "Docker")
    assert [button.label for button in at.button] == ["Docker", "Python"]  # alphabetical


def test_clicking_a_skill_removes_only_that_skill(app):
    at, path = app
    python_id, docker_id, git_id = skill_ids(path, "Python", "Docker", "Git")
    at.session_state["selected_skill_ids"] = [python_id, docker_id, git_id]
    at.run()
    at.button(key=f"remove_skill_{docker_id}").click().run()
    assert at.session_state["selected_skill_ids"] == [python_id, git_id]
    assert "Docker" in at.selectbox[0].options  # can be added again


def test_removing_the_last_skill_brings_back_the_prompt(app):
    at, path = app
    (python_id,) = skill_ids(path, "Python")
    at.session_state["selected_skill_ids"] = [python_id]
    at.run()
    assert list(at.info) == []
    at.button(key=f"remove_skill_{python_id}").click().run()
    assert len(at.info) == 1