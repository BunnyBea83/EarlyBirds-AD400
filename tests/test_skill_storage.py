"""Storage checks use isolated databases, never the downloaded dataset."""

import sqlite3

import pandas as pd
import pytest

from cleaning_functions import save_to_sqlite
from birdseye.skill_storage import initialize_storage, save_posting_skills
from birdseye.skills_catalog import SKILLS


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE postings(job_id INTEGER, description TEXT)")
    connection.executemany("INSERT INTO postings VALUES (?, ?)", [(1, "Python"), (2, "SQL")])
    connection.commit()
    initialize_storage(connection)
    yield connection
    connection.close()


def matches(conn):
    return conn.execute("""
        SELECT job_id, name FROM posting_skills JOIN skills USING(skill_id)
        ORDER BY job_id, name
    """).fetchall()


def test_catalog_initialization_is_repeatable_with_stable_ids(conn):
    before = conn.execute("SELECT * FROM skills ORDER BY skill_id").fetchall()
    initialize_storage(conn)
    assert conn.execute("SELECT * FROM skills ORDER BY skill_id").fetchall() == before
    assert len(before) == len(SKILLS)


def test_repeated_saves_do_not_duplicate_skills_or_links(conn):
    for _ in range(2):
        save_posting_skills(conn, 1, ["Python", "Python", "SQL"])
    assert matches(conn) == [(1, "Python"), (1, "SQL")]
    assert conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == len(SKILLS)


def test_reprocessing_replaces_old_matches_and_preserves_other_postings(conn):
    save_posting_skills(conn, 1, ["Python"])
    save_posting_skills(conn, 2, ["SQL"])
    save_posting_skills(conn, 1, ["PostgreSQL"])
    assert matches(conn) == [(1, "PostgreSQL"), (2, "SQL")]
    save_posting_skills(conn, 1, [])
    assert matches(conn) == [(2, "SQL")]


def test_unknown_skill_or_posting_does_not_change_existing_links(conn):
    save_posting_skills(conn, 1, ["Python"])
    with pytest.raises(ValueError, match="Unknown canonical"):
        save_posting_skills(conn, 1, ["SQL", "Postgres"])
    with pytest.raises(ValueError, match="Unknown job_id"):
        save_posting_skills(conn, 999, ["SQL"])
    assert matches(conn) == [(1, "Python")]


def test_database_constraints_reject_duplicates_and_orphans(conn):
    save_posting_skills(conn, 1, ["Python"])
    skill_id = conn.execute("SELECT skill_id FROM skills WHERE name='Python'").fetchone()[0]
    for statement, params in [
        ("INSERT INTO skills(name) VALUES (?)", ("PYTHON",)),
        ("INSERT INTO posting_skills VALUES (?, ?)", (1, skill_id)),
        ("INSERT INTO posting_skills VALUES (?, ?)", (999, skill_id)),
        ("INSERT INTO posting_skills VALUES (?, ?)", (1, 999)),
    ]:
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(statement, params)


def test_save_participates_in_callers_transaction(conn):
    conn.execute("BEGIN")
    save_posting_skills(conn, 1, ["Python"])
    conn.rollback()
    assert matches(conn) == []


def test_failed_insert_restores_previous_matches(conn):
    save_posting_skills(conn, 1, ["Python"])
    conn.execute("""
        CREATE TRIGGER reject_matches BEFORE INSERT ON posting_skills
        BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END
    """)
    with pytest.raises(sqlite3.IntegrityError, match="simulated write failure"):
        save_posting_skills(conn, 1, ["SQL"])
    assert matches(conn) == [(1, "Python")]


def test_rejects_string_instead_of_skill_list(conn):
    with pytest.raises(TypeError):
        save_posting_skills(conn, 1, "Python")


def test_cleaning_rebuild_clears_matches_even_for_same_job_id(tmp_path):
    db_path = tmp_path / "birdseye.db"
    frame = pd.DataFrame({"job_id": [1], "description": ["Python"]})
    save_to_sqlite(frame, db_path)
    with sqlite3.connect(db_path) as connection:
        initialize_storage(connection)
        save_posting_skills(connection, 1, ["Python"])
        original_catalog = connection.execute("SELECT * FROM skills").fetchall()
    frame["description"] = "SQL"
    save_to_sqlite(frame, db_path)
    with sqlite3.connect(db_path) as connection:
        initialize_storage(connection)
        assert matches(connection) == []
        assert connection.execute("SELECT * FROM skills").fetchall() == original_catalog
        save_posting_skills(connection, 1, ["SQL"])
        assert matches(connection) == [(1, "SQL")]


@pytest.mark.parametrize("ids", [[1, 1], [None]])
def test_initialization_rejects_invalid_posting_ids(ids):
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE postings(job_id INTEGER)")
        connection.executemany("INSERT INTO postings VALUES (?)", [(i,) for i in ids])
        connection.commit()
        with pytest.raises((ValueError, sqlite3.IntegrityError)):
            initialize_storage(connection)
