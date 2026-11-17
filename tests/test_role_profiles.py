"""Role profile checks using small temporary SQLite databases (TA4-51)."""

import importlib.util
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import birdseye.role_profiles as role_profiles_module
from birdseye.role_profiles import (
    MAX_PROFILE_SKILLS, MissingRoleProfiles, StaleRoleProfiles, build_role_profiles,
    load_role_profile, profile_rows, profiles_are_current,
)
from birdseye.roles import ROLE_RULES
from birdseye.skill_storage import initialize_storage, save_posting_skills
from birdseye.skills_catalog import SKILLS

SKILL_NAMES = [skill.name for skill in SKILLS]


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
    """Data Analyst has 3 postings and 25 different skills; Registered Nurse has 1 skill."""
    return build_database(
        tmp_path / "birdseye.db",
        [(1, "Data Analyst"), (2, "Senior Data Analyst"), (3, "Data Analyst"),
         (4, "Registered Nurse"), (5, "Marketing Manager")],
        {1: SKILL_NAMES[:25], 2: SKILL_NAMES[:5], 4: ["Communication"]},
    )


def build(path):
    with closing(sqlite3.connect(path)) as conn:
        return build_role_profiles(conn)


def stored(path):
    """Read the table back as {role: {skill: share}}."""
    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute("SELECT role, skill, share FROM role_profiles").fetchall()
    profiles = {}
    for role, skill, share in rows:
        profiles.setdefault(role, {})[skill] = share
    return profiles


def test_each_role_with_skills_has_a_profile(database):
    build(database)
    # Marketing Manager has a posting but no skills were found, so it has no rows.
    assert set(stored(database)) == {"Data Analyst", "Registered Nurse"}


def test_each_profile_has_up_to_twenty_different_skills(database):
    assert MAX_PROFILE_SKILLS == 20
    build(database)
    profiles = stored(database)
    assert len(profiles["Data Analyst"]) == 20  # 25 skills found, the top 20 are kept
    assert len(profiles["Registered Nurse"]) == 1  # only one skill found, so a shorter profile
    assert all(0 < share <= 100 for skills in profiles.values() for share in skills.values())


def test_all_roles_and_skills_are_in_one_table(database):
    assert build(database) == 21
    with closing(sqlite3.connect(database)) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(role_profiles)")]
        total = conn.execute("SELECT COUNT(*) FROM role_profiles").fetchone()[0]
    assert columns == ["role", "skill", "share"]
    assert total == 21


def test_shares_match_posting_skills_counts(database):
    build(database)
    with closing(sqlite3.connect(database)) as conn:
        counts = dict(conn.execute("""
            SELECT s.name, COUNT(*) FROM posting_skills AS ps JOIN skills AS s USING(skill_id)
            WHERE ps.job_id IN (1, 2, 3) GROUP BY s.name
        """))
    top_twenty = sorted(counts, key=lambda name: (-counts[name], name.casefold()))[:20]
    analyst = stored(database)["Data Analyst"]  # 3 postings
    assert set(analyst) == set(top_twenty)
    for name in top_twenty:
        assert analyst[name] == pytest.approx(100 * counts[name] / 3)


def test_a_role_with_one_skill_keeps_only_that_skill(database):
    build(database)
    assert stored(database)["Registered Nurse"] == {"Communication": 100.0}


def test_rebuilding_replaces_the_old_profiles(database):
    build(database)
    with closing(sqlite3.connect(database)) as conn:
        save_posting_skills(conn, 4, ["Python"])
        conn.commit()
    assert build(database) == 21
    assert stored(database)["Registered Nurse"] == {"Python": 100.0}


def test_load_role_profile_is_ordered_by_share_then_name(database):
    build(database)
    profile = load_role_profile(database, "Data Analyst")
    assert len(profile) == 20
    shares = [row["percentage"] for row in profile]
    assert shares == sorted(shares, reverse=True)
    first_five = sorted(SKILL_NAMES[:5], key=lambda name: (name.casefold(), name))
    assert [row["skill"] for row in profile[:5]] == first_five  # in 2 of 3 postings
    assert shares[0] == pytest.approx(100 * 2 / 3)


def test_a_role_without_skills_loads_as_an_empty_profile(database):
    build(database)
    assert load_role_profile(database, "Marketing Manager") == []


def test_loading_before_the_build_step_explains_what_to_run(database):
    with pytest.raises(MissingRoleProfiles, match="build_role_profiles"):
        load_role_profile(database, "Data Analyst")


def test_profile_rows_keep_the_top_skills_in_ranked_order():
    ranked = [{"skill": name, "percentage": share} for name, share in
              (("SQL", 90.0), ("Git", 50.0), ("Docker", 10.0))]
    roles = {"A": {"skills": ranked}, "B": {"skills": []}}
    assert profile_rows(roles, size=2) == [("A", "SQL", 90.0), ("A", "Git", 50.0)]


def change(path, sql, params=()):
    """Change the database the way cleaning, extraction or a catalog edit would."""
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute(sql, params)


def is_current(path):
    with closing(sqlite3.connect(path)) as conn:
        return profiles_are_current(conn)


def test_profiles_are_current_right_after_a_build(database):
    build(database)
    assert is_current(database)
    assert load_role_profile(database, "Registered Nurse") == [{"skill": "Communication", "percentage": 100.0}]


def test_clearing_the_skill_links_makes_the_stored_profiles_stale(database):
    # The reported bug: cleaning cleared the links, but the profile still showed 100%.
    build(database)
    assert stored(database)["Registered Nurse"] == {"Communication": 100.0}
    change(database, "DELETE FROM posting_skills")
    assert stored(database)["Registered Nurse"] == {"Communication": 100.0}  # the old rows are still there
    with pytest.raises(StaleRoleProfiles, match="out of date") as error:
        load_role_profile(database, "Registered Nurse")
    assert "build_role_profiles.py --db data/processed/birdseye.db" in str(error.value)
    assert not is_current(database)


def test_rebuilding_after_the_data_changed_clears_the_stale_profile(database):
    build(database)
    change(database, "DELETE FROM posting_skills")
    assert build(database) == 0
    assert load_role_profile(database, "Registered Nurse") == []
    assert is_current(database)


def test_stale_profiles_are_current_again_if_extraction_restores_the_same_links(database):
    build(database)
    change(database, "DELETE FROM posting_skills")
    assert not is_current(database)
    with closing(sqlite3.connect(database)) as conn:
        save_posting_skills(conn, 4, ["Communication"])
        save_posting_skills(conn, 1, SKILL_NAMES[:25])
        save_posting_skills(conn, 2, SKILL_NAMES[:5])
        conn.commit()
    assert is_current(database)
    assert load_role_profile(database, "Registered Nurse") == [{"skill": "Communication", "percentage": 100.0}]


@pytest.mark.parametrize("description, sql, params", [
    ("a link is added", "INSERT INTO posting_skills(job_id, skill_id) VALUES (6, 1)", ()),
    ("a posting is removed", "DELETE FROM postings WHERE job_id = 5", ()),
    ("a posting is added", "INSERT INTO postings(job_id, title) VALUES (99, 'Data Analyst')", ()),
    ("a title changes to one of the same length", "UPDATE postings SET title = 'Data Analyzt' WHERE job_id = 1", ()),
    ("a skill is renamed", "UPDATE skills SET name = 'Communication Skills' WHERE name = 'Communication'", ()),
    ("a link moves to another skill", "UPDATE posting_skills SET skill_id = 2 WHERE job_id = 4", ()),
])
def test_any_change_to_the_source_data_makes_the_profiles_stale(database, description, sql, params):
    with closing(sqlite3.connect(database)) as conn:  # job 6 needs a posting row for the first case
        with conn:
            conn.execute("INSERT INTO postings(job_id, title) VALUES (6, 'Barista')")
    build(database)
    assert is_current(database), description
    change(database, sql, params)
    assert not is_current(database), description
    with pytest.raises(StaleRoleProfiles):
        load_role_profile(database, "Data Analyst")


def test_changing_the_role_rules_makes_the_profiles_stale(database, monkeypatch):
    build(database)
    monkeypatch.setattr(role_profiles_module, "ROLE_RULES", {**ROLE_RULES, "Barista": ("barista",)})
    assert not is_current(database)


def test_profiles_built_before_change_tracking_are_treated_as_stale(database):
    build(database)
    change(database, "DROP TABLE role_profile_meta")
    with pytest.raises(StaleRoleProfiles, match="Rebuild them"):
        load_role_profile(database, "Data Analyst")


def test_profiles_are_stale_if_the_source_tables_disappear(database):
    build(database)
    change(database, "DROP TABLE posting_skills")
    assert not is_current(database)
    with pytest.raises(StaleRoleProfiles):
        load_role_profile(database, "Data Analyst")


def test_stale_profiles_are_reported_through_the_error_the_dashboard_already_handles(database):
    assert issubclass(StaleRoleProfiles, MissingRoleProfiles)
    build(database)
    change(database, "DELETE FROM posting_skills")
    try:
        load_role_profile(database, "Data Analyst")
    except MissingRoleProfiles as error:  # app.py catches this and shows str(error)
        assert "Rebuild them with" in str(error)


def test_each_build_keeps_exactly_one_fingerprint(database):
    build(database)
    build(database)
    with closing(sqlite3.connect(database)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM role_profile_meta").fetchone()[0] == 1


def test_a_failed_build_keeps_the_old_profiles_and_fingerprint(database):
    build(database)
    change(database, "DROP TABLE skills")
    with closing(sqlite3.connect(database)) as conn:
        with pytest.raises(sqlite3.Error):
            build_role_profiles(conn)
    assert stored(database)["Registered Nurse"] == {"Communication": 100.0}


def load_script():
    path = Path(__file__).resolve().parents[1] / "scripts/build_role_profiles.py"
    spec = importlib.util.spec_from_file_location("build_role_profiles_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_builds_the_profiles(database, capsys):
    assert load_script().main(["--db", str(database)]) == 0
    assert "Saved 21 profile rows" in capsys.readouterr().out
    assert len(stored(database)) == 2


def test_script_does_not_create_a_missing_database(tmp_path, capsys):
    path = tmp_path / "missing.db"
    assert load_script().main(["--db", str(path)]) == 1
    assert not path.exists()
    assert "Role profile build failed" in capsys.readouterr().err


def test_script_explains_when_skill_extraction_has_not_run(tmp_path, capsys):
    path = tmp_path / "cleaned.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE postings(job_id INTEGER, title TEXT)")
    assert load_script().main(["--db", str(path)]) == 1
    assert "skill extraction" in capsys.readouterr().err