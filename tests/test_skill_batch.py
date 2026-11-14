"""Batch and command checks using small temporary SQLite databases."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from birdseye.skill_batch import BatchResult, process_postings
from birdseye.skill_management import add_skill
from birdseye.skill_storage import initialize_storage
from extract_skills import main


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "postings.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE postings(job_id INTEGER, description TEXT)")
        conn.executemany("INSERT INTO postings VALUES (?, ?)", [
            (1, "Python PYTHON Postgres"), (2, "JavaScript"),
            (3, None), (4, ""), (5, "No matching vocabulary"),
        ])
    return path


def read_links(path):
    with sqlite3.connect(path) as conn:
        return conn.execute("""
            SELECT job_id, name FROM posting_skills JOIN skills USING(skill_id)
            ORDER BY job_id, name
        """).fetchall()


def test_batch_reads_chunks_and_reports_results(database):
    progress = []
    assert process_postings(database, batch_size=2, progress=progress.append) == BatchResult(5, 2, 3, 1)
    assert [result.processed for result in progress] == [2, 4, 5]
    assert read_links(database) == [(1, "PostgreSQL"), (1, "Python"), (2, "JavaScript")]


def test_reruns_replace_changed_matches_without_duplicates(database):
    process_postings(database)
    process_postings(database)
    assert len(read_links(database)) == 3
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE postings SET description = 'SQL' WHERE job_id = 1")
        conn.execute("UPDATE postings SET description = NULL WHERE job_id = 2")
    assert process_postings(database) == BatchResult(5, 1, 1, 2)
    assert read_links(database) == [(1, "SQL")]


def test_failure_rolls_back_previous_chunks(database):
    process_postings(database)
    before = read_links(database)
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE postings SET description = 'SQL' WHERE job_id = 1")
    def fail_after_first_chunk(result):
        raise RuntimeError("interrupted")
    with pytest.raises(RuntimeError, match="interrupted"):
        process_postings(database, batch_size=1, progress=fail_after_first_chunk)
    assert read_links(database) == before


def test_empty_database(database):
    with sqlite3.connect(database) as conn:
        conn.execute("DELETE FROM postings")
    assert process_postings(database) == BatchResult()
    assert read_links(database) == []


@pytest.mark.parametrize("size", [0, -1, True, 1.5])
def test_invalid_chunk_size(database, size):
    with pytest.raises(ValueError, match="positive integer"):
        process_postings(database, batch_size=size)


def test_missing_database_is_not_created(tmp_path, capsys):
    path = tmp_path / "missing.db"
    assert main(["--db", str(path)]) == 1
    assert not path.exists()
    error = capsys.readouterr().err
    assert "Skill extraction failed" in error
    assert "Build the database with python scripts/clean_data.py first." in error


def test_command_invalid_batch_size_has_no_database_hint(database, capsys):
    assert main(["--db", str(database), "--batch-size", "0"]) == 1
    error = capsys.readouterr().err
    assert "batch_size must be a positive integer" in error
    assert "clean_data" not in error
    assert "Close other programs" not in error


def test_command_locked_database_has_specific_hint(database, capsys):
    with sqlite3.connect(database) as conn:
        conn.execute("BEGIN EXCLUSIVE")
        assert main(["--db", str(database)]) == 1
    error = capsys.readouterr().err
    assert "database is locked" in error
    assert "Close other programs using the database and try again." in error
    assert "clean_data" not in error


def test_command_other_database_error_has_no_rebuild_hint(tmp_path, capsys):
    path = tmp_path / "corrupt.db"
    path.write_text("not a SQLite database")
    assert main(["--db", str(path)]) == 1
    error = capsys.readouterr().err
    assert "file is not a database" in error
    assert "clean_data" not in error
    assert "Close other programs" not in error


def test_missing_schema_has_helpful_error(tmp_path, capsys):
    path = tmp_path / "empty.db"
    sqlite3.connect(path).close()
    assert main(["--db", str(path)]) == 1
    assert "requires postings with job_id and description" in capsys.readouterr().err


def test_command_runs_as_documented(database):
    script = Path(__file__).resolve().parents[1] / "scripts/extract_skills.py"
    result = subprocess.run(
        [sys.executable, str(script), "--db", str(database), "--batch-size", "2"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Processed 2 postings" in result.stdout
    assert "Saved 3 skill links from 5 postings; 2 postings matched; 1 descriptions missing." in result.stdout
    assert len(read_links(database)) == 3


def test_invalid_records_are_logged_and_do_not_stop_valid_records(database, caplog):
    process_postings(database)
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE postings SET description = ? WHERE job_id = 1", (b"Python",))
        conn.execute("INSERT INTO postings VALUES (NULL, 'Java')")
        conn.execute("INSERT INTO postings VALUES (6, 'SQL')")
    result = process_postings(database, batch_size=2)
    assert result == BatchResult(7, 2, 2, 1, 2)
    assert read_links(database) == [(2, "JavaScript"), (6, "SQL")]
    assert "invalid or missing job_id" in caplog.text
    assert "non-text description" in caplog.text
    assert "no description" in caplog.text


def test_batch_uses_reviewed_database_additions(database):
    with sqlite3.connect(database) as conn:
        initialize_storage(conn)
        add_skill(conn, "Technical Writing", aliases=("Documentation Writing",))
        conn.execute("UPDATE postings SET description='Documentation Writing' WHERE job_id=1")
    process_postings(database)
    assert (1, "Technical Writing") in read_links(database)
