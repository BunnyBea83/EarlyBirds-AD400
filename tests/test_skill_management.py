"""Equivalent names, reviewed merges, and catalog maintenance acceptance tests."""

import sqlite3

import pytest

from birdseye.skill_extraction import extract_skills
from birdseye.skill_management import add_skill, update_skill, consolidate_skills, load_skills
from birdseye.skill_storage import initialize_storage, save_posting_skills


@pytest.fixture
def conn():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE postings(job_id INTEGER)")
    db.executemany("INSERT INTO postings VALUES (?)", [(1,), (2,)])
    db.commit()
    initialize_storage(db)
    yield db
    db.close()


def test_known_equivalent_returns_existing_id_and_distinct_terms_stay_distinct(conn):
    assert add_skill(conn, " postgres ") == add_skill(conn, "PostgreSQL")
    assert add_skill(conn, "Java") != add_skill(conn, "JavaScript")
    assert add_skill(conn, "SQL") != add_skill(conn, "PostgreSQL")


def test_new_reviewed_skill_and_alias_are_matchable_with_category(conn):
    skill_id = add_skill(conn, "Technical   Writing", aliases=("Documentation Writing",), category="Professional")
    assert extract_skills("documentation\nwriting", catalog=load_skills(conn)) == ["Technical Writing"]
    save_posting_skills(conn, 1, ["Technical Writing"])
    assert conn.execute("SELECT category FROM skills WHERE skill_id = ?", (skill_id,)).fetchone() == ("Professional",)


def test_rename_keeps_id_aliases_and_associations_across_initialization(conn):
    skill_id = add_skill(conn, "Python")
    save_posting_skills(conn, 1, ["Python"])
    update_skill(conn, skill_id, name="Python Programming", category="Technical")
    initialize_storage(conn)
    assert add_skill(conn, "Python") == skill_id
    assert extract_skills("Python", catalog=load_skills(conn)) == ["Python Programming"]
    assert conn.execute("SELECT skill_id FROM posting_skills").fetchone() == (skill_id,)


def test_confirmed_merge_preserves_links_and_aliases_without_duplicates(conn):
    source = add_skill(conn, "Python")
    target = add_skill(conn, "Python Programming")
    save_posting_skills(conn, 1, ["Python", "Python Programming"])
    save_posting_skills(conn, 2, ["Python"])
    consolidate_skills(conn, source, target, confirmed=True)
    initialize_storage(conn)
    assert conn.execute("SELECT job_id, skill_id FROM posting_skills ORDER BY job_id").fetchall() == [(1, target), (2, target)]
    assert add_skill(conn, "Python") == target
    assert extract_skills("Python and Python Programming", catalog=load_skills(conn)) == ["Python Programming"]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_uncertain_merge_and_conflicting_alias_are_rejected(conn):
    java, javascript = add_skill(conn, "Java"), add_skill(conn, "JavaScript")
    with pytest.raises(ValueError, match="explicit confirmation"):
        consolidate_skills(conn, java, javascript)
    with pytest.raises(ValueError, match="another skill"):
        add_skill(conn, "New Skill", aliases=("Java",))
    assert conn.execute("SELECT 1 FROM skills WHERE name='New Skill'").fetchone() is None
    assert add_skill(conn, "Java") == java


def test_failed_merge_rolls_back_relationships(conn):
    source, target = add_skill(conn, "Java"), add_skill(conn, "JavaScript")
    save_posting_skills(conn, 1, ["Java"])
    conn.execute("CREATE TRIGGER reject_merge BEFORE DELETE ON skills BEGIN SELECT RAISE(ABORT, 'blocked'); END")
    with pytest.raises(sqlite3.IntegrityError):
        consolidate_skills(conn, source, target, confirmed=True)
    assert conn.execute("SELECT skill_id FROM posting_skills").fetchall() == [(source,)]
    assert add_skill(conn, "Java") == source
