"""Functional acceptance checks from raw CSVs through persisted skill results.

All inputs and outputs live in pytest's temporary directory. The cleaning
orchestrator and extraction command run without mocking extraction or storage.
"""

import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pandas as pd
import pytest

import clean_data
from cleaning_functions import load_raw, save_to_sqlite
from birdseye.skill_storage import initialize_storage
from birdseye.skill_management import add_skill, consolidate_skills


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    postings = pd.DataFrame([
        (1, 10, "Developer", "Python PYTHON Postgres PostgreSQL", "Seattle, WA"),
        (1, 10, "Duplicate ID", "Java", "Seattle, WA"),
        (2, 10, "Frontend", "JavaScript and React.js", "Seattle, WA"),
        (3, 10, "Backend", "C++, C# and .NET", "Seattle, WA"),
        (4, 10, "Missing text", None, "Seattle, WA"),
        (5, 10, "Other role", "No matching vocabulary here", "Seattle, WA"),
        (6, 10, "Developer", "Python PYTHON Postgres PostgreSQL", "Seattle, WA"),
    ], columns=["job_id", "company_id", "title", "description", "location"])
    postings.to_csv(raw / "postings.csv", index=False)
    for directory in ["companies", "jobs", "mappings"]:
        (raw / directory).mkdir()
    pd.DataFrame({"company_id": [10], "city": ["Seattle"]}).to_csv(
        raw / "companies/companies.csv", index=False
    )
    pd.DataFrame({"job_id": [1, 1, 2, 3, 5], "industry_id": [100, 101, 100, 100, 101]}).to_csv(
        raw / "jobs/job_industries.csv", index=False
    )
    pd.DataFrame({"industry_id": [100, 101], "industry_name": ["Software", "Services"]}).to_csv(
        raw / "mappings/industries.csv", index=False
    )
    database = tmp_path / "processed/birdseye.db"
    monkeypatch.setattr(clean_data, "load_raw", lambda: load_raw(raw))
    monkeypatch.setattr(clean_data, "save_to_sqlite", lambda frame: save_to_sqlite(frame, database))
    monkeypatch.setattr(clean_data, "DB_PATH", database)
    monkeypatch.setattr(clean_data, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(clean_data, "REPORT_PATH", tmp_path / "cleaning_report.md")
    return raw, database


def run_extraction(database):
    script = Path(__file__).resolve().parents[1] / "scripts/extract_skills.py"
    result = subprocess.run(
        [sys.executable, str(script), "--db", str(database), "--batch-size", "2"],
        capture_output=True, text=True, check=False,
        # Verify that explicit database paths work outside the repo directory.
        cwd=database.parent,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def snapshot(database):
    with closing(sqlite3.connect(database)) as conn:
        links = conn.execute("""
            SELECT job_id, name FROM posting_skills JOIN skills USING(skill_id)
            ORDER BY job_id, name
        """).fetchall()
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        catalog = conn.execute("SELECT skill_id, name FROM skills ORDER BY skill_id").fetchall()
        descriptions = conn.execute("SELECT job_id, description FROM postings ORDER BY job_id").fetchall()
    return links, catalog, descriptions


def test_raw_to_cleaned_to_skills_and_repeat_run(workflow):
    _, database = workflow
    assert clean_data.main() == 0
    assert "Saved 7 skill links from 4 postings" in run_extraction(database)
    before = snapshot(database)
    assert before[0] == [
        (1, "PostgreSQL"), (1, "Python"),
        (2, "JavaScript"), (2, "React"),
        (3, ".NET"), (3, "C#"), (3, "C++"),
    ]
    assert [job_id for job_id, _ in before[2]] == [1, 2, 3, 5]
    run_extraction(database)
    assert snapshot(database) == before


def test_raw_changes_and_cleaning_rebuild_remove_stale_matches(workflow):
    raw, database = workflow
    assert clean_data.main() == 0
    run_extraction(database)
    original_catalog = snapshot(database)[1]
    updated = pd.DataFrame([
        (1, 10, "Changed role", "SQL", "Seattle, WA"),
        (7, 10, "New role", "AWS and Docker", "Seattle, WA"),
    ], columns=["job_id", "company_id", "title", "description", "location"])
    updated.to_csv(raw / "postings.csv", index=False)
    assert clean_data.main() == 0
    assert snapshot(database)[0] == []
    assert "Saved 3 skill links from 2 postings" in run_extraction(database)
    links, catalog, descriptions = snapshot(database)
    assert links == [(1, "SQL"), (7, "Amazon Web Services"), (7, "Docker")]
    assert catalog == original_catalog
    assert descriptions == [(1, "SQL"), (7, "AWS and Docker")]


def test_reviewed_new_vocabulary_and_consolidation_survive_full_rerun(workflow):
    _, database = workflow
    assert clean_data.main() == 0
    with closing(sqlite3.connect(database)) as conn:
        initialize_storage(conn)
        source = add_skill(conn, "Technical Writing", aliases=("Documentation Writing",), category="Professional")
        target = add_skill(conn, "Documentation")
        with conn:
            conn.execute("UPDATE postings SET description='Documentation Writing' WHERE job_id=5")
    run_extraction(database)
    assert (5, "Technical Writing") in snapshot(database)[0]
    with closing(sqlite3.connect(database)) as conn:
        initialize_storage(conn)
        consolidate_skills(conn, source, target, confirmed=True)
    run_extraction(database)
    links, _, _ = snapshot(database)
    assert (5, "Documentation") in links
    assert (5, "Technical Writing") not in links


def test_cli_logs_invalid_records_and_still_saves_valid_matches(workflow):
    _, database = workflow
    assert clean_data.main() == 0
    run_extraction(database)
    with closing(sqlite3.connect(database)) as conn:
        with conn:
            conn.execute("UPDATE postings SET description=? WHERE job_id=1", (b"Python",))
            conn.execute("INSERT INTO postings(job_id, description) VALUES(NULL, 'Python')")
    script = Path(__file__).resolve().parents[1] / "scripts/extract_skills.py"
    result = subprocess.run(
        [sys.executable, str(script), "--db", str(database)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Skipped 2 invalid postings" in result.stdout
    assert "WARNING" in result.stderr
    assert "non-text description" in result.stderr
    assert "invalid or missing job_id" in result.stderr
    assert snapshot(database)[0] == [(2, "JavaScript"), (2, "React"), (3, ".NET"), (3, "C#"), (3, "C++")]
