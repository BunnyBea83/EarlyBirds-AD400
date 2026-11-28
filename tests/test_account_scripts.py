"""Tests for the setup and admin scripts, run against a temporary database."""

import sys
from contextlib import closing

import pytest

import manage_accounts
import setup_accounts
from birdseye import accounts


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A temporary accounts file and fast hashing."""
    # Lower the scrypt cost so hashing is fast; monkeypatch undoes it after the test.
    monkeypatch.setattr(accounts, "SCRYPT_N", 2**10)
    # A path in this test's own temporary folder.
    return tmp_path / "accounts.db"


def run(module, monkeypatch, *argv):
    """Run a script's main() as if called from the command line."""
    # Pretend these were the command-line arguments, which is what argparse reads.
    monkeypatch.setattr(sys, "argv", [module.__name__, *argv])
    return module.main()


def emails(db):
    """Emails saved in the accounts file."""
    with closing(accounts.connect(db)) as conn:
        return [u.email for u in accounts.list_users(conn)]


def test_seed_is_repeatable(db, monkeypatch, capsys):
    """Running --seed twice adds each test user only once."""
    # Seed twice; both runs succeed (exit code 0).
    assert run(setup_accounts, monkeypatch, "--db", str(db), "--seed") == 0
    assert run(setup_accounts, monkeypatch, "--db", str(db), "--seed") == 0

    # Each test user appears once, in order.
    assert emails(db) == [user[2] for user in setup_accounts.TEST_USERS]

    # The second run said it skipped them (capsys captures printed output).
    assert "already exists, skipped" in capsys.readouterr().out


def test_seeded_users_have_the_test_password(db, monkeypatch):
    """Each test user gets the listed password and role."""
    run(setup_accounts, monkeypatch, "--db", str(db), "--seed")

    # For each test user, read the stored hash and role, and check them.
    with closing(accounts.connect(db)) as conn:
        for _, _, email, password, role in setup_accounts.TEST_USERS:
            stored = conn.execute("SELECT password_hash, role FROM users WHERE email = ?", (email,)).fetchone()
            assert accounts.verify_password(password, stored[0]) and stored[1] == role


def test_list_shows_users(db, monkeypatch, capsys):
    """list prints each user's name, email and role."""
    run(setup_accounts, monkeypatch, "--db", str(db), "--seed")
    capsys.readouterr()  # throw away the seed output so only the list is checked

    # Run list; it succeeds.
    assert run(manage_accounts, monkeypatch, "--db", str(db), "list") == 0

    # The output includes a test user's email, name and the admin role.
    out = capsys.readouterr().out
    assert "test@birdseye.dev" in out and "admin" in out
    assert "Test User" in out


def test_reset_password(db, monkeypatch):
    """reset-password saves the new password."""
    run(setup_accounts, monkeypatch, "--db", str(db), "--seed")

    # Pretend the user typed "newpassword9" at both hidden password prompts.
    monkeypatch.setattr(manage_accounts.getpass, "getpass", lambda prompt: "newpassword9")
    assert run(manage_accounts, monkeypatch, "--db", str(db), "reset-password", "test@birdseye.dev") == 0

    # The stored hash now matches the new password.
    with closing(accounts.connect(db)) as conn:
        (stored,) = conn.execute("SELECT password_hash FROM users WHERE email = 'test@birdseye.dev'").fetchone()
    assert accounts.verify_password("newpassword9", stored)


def test_delete_asks_first_and_respects_no(db, monkeypatch):
    """delete keeps the user when the answer is no, and deletes with --yes."""
    run(setup_accounts, monkeypatch, "--db", str(db), "--seed")

    # Answer "n" to the confirmation question: the user is kept.
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    run(manage_accounts, monkeypatch, "--db", str(db), "delete", "test@birdseye.dev")
    assert "test@birdseye.dev" in emails(db)

    # With --yes there's no question, and the user is deleted.
    run(manage_accounts, monkeypatch, "--db", str(db), "delete", "test@birdseye.dev", "--yes")
    assert "test@birdseye.dev" not in emails(db)


def test_unknown_email_is_an_error(db, monkeypatch, capsys):
    """An unknown email prints an error and exits with code 1."""
    # Try to delete an account that doesn't exist; exit code 1 means failure.
    assert run(manage_accounts, monkeypatch, "--db", str(db), "delete", "nobody@x.com", "--yes") == 1

    # The error goes to the error output.
    assert "No account" in capsys.readouterr().err