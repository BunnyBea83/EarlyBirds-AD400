"""TA4-38 schema acceptance checks."""

import sqlite3
from contextlib import closing

import pytest

from birdseye.skill_storage import initialize_storage
from birdseye.skills_catalog import SKILLS


def test_schema_seeds_unique_skills_aliases_and_optional_categories():
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.execute("CREATE TABLE postings(job_id INTEGER)")
        initialize_storage(conn)
        before = conn.execute("SELECT * FROM skills ORDER BY skill_id").fetchall()
        initialize_storage(conn)
        assert conn.execute("SELECT * FROM skills ORDER BY skill_id").fetchall() == before
        assert len(before) == len(SKILLS)
        assert "category" in {row[1] for row in conn.execute("PRAGMA table_info(skills)")}
        assert conn.execute("SELECT COUNT(*) FROM skill_aliases").fetchone()[0] == 59
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute("INSERT INTO skills(name) VALUES ('PYTHON')")
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute("INSERT INTO posting_skills VALUES (999, 1)")


def test_existing_schema_gains_optional_category_without_changing_ids():
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.execute("CREATE TABLE postings(job_id INTEGER)")
        conn.execute("CREATE TABLE skills(skill_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE)")
        conn.execute("INSERT INTO skills VALUES (100, 'Python')")
        conn.commit()
        initialize_storage(conn)
        assert conn.execute("SELECT skill_id, category FROM skills WHERE name='Python'").fetchone() == (100, None)
