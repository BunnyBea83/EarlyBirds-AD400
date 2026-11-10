"""Smoke checks for TA4-74: confirm the environment is set up correctly.

These do not test features. They only check that the package imports
and that SQLite (the planned database) is available.
"""

import sqlite3

import birdseye


def test_package_imports():
    assert birdseye.__version__


def test_sqlite_available():
    conn = sqlite3.connect(":memory:")
    try:
        assert conn.execute("SELECT 1").fetchone() == (1,)
    finally:
        conn.close()
