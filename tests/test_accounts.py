"""Tests for the users table, password hashing and sign-up rules, using throwaway databases."""

import sqlite3

import pytest

from birdseye import accounts
from birdseye.accounts import AccountError


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch):
    """Use a low scrypt cost so hashing in these tests is fast (real settings take ~0.3 s)."""
    # autouse=True applies this to every test in the file; monkeypatch undoes it afterwards.
    monkeypatch.setattr(accounts, "SCRYPT_N", 2**10)


@pytest.fixture
def conn():
    """A fresh in-memory accounts database for each test."""
    # Open an empty database that only exists in memory.
    connection = accounts.connect(":memory:")
    # Hand it to the test, then close it when the test finishes.
    yield connection
    connection.close()


def stored_hash(conn, user_id):
    """Read a password hash from the table (User objects don't include it)."""
    return conn.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]


# --- Database setup ------------------------------------------------------------

def test_initialization_is_repeatable(conn):
    """Creating the tables again keeps existing accounts."""
    # Create an account.
    accounts.create_user(conn, "John", "Snow", "john@example.com", "password1")

    # Run the table setup a second time.
    accounts.initialize_accounts(conn)

    # The account is still there.
    assert [u.email for u in accounts.list_users(conn)] == ["john@example.com"]


def test_connect_creates_folder_and_file(tmp_path):
    """connect() creates missing folders and saves accounts to disk."""
    # A path inside a folder that doesn't exist yet.
    db_path = tmp_path / "nested" / "accounts.db"

    # Connect (creating the folder and file) and add an account.
    conn = accounts.connect(db_path)
    accounts.create_user(conn, "John", "Snow", "john@example.com", "password1")
    conn.close()

    # Reopen the file with plain sqlite3 to check the account was saved to disk.
    reopened = sqlite3.connect(db_path)
    assert reopened.execute("SELECT email FROM users").fetchall() == [("john@example.com",)]
    reopened.close()


def test_accounts_db_path_follows_the_setting(monkeypatch, tmp_path):
    """BIRDSEYE_ACCOUNTS_DB overrides the default accounts file."""
    # Without the setting, the default file is used.
    monkeypatch.delenv("BIRDSEYE_ACCOUNTS_DB", raising=False)
    assert accounts.accounts_db_path() == accounts.DEFAULT_ACCOUNTS_DB

    # With the setting, its path is used instead.
    monkeypatch.setenv("BIRDSEYE_ACCOUNTS_DB", str(tmp_path / "other.db"))
    assert accounts.accounts_db_path() == tmp_path / "other.db"


# --- Password hashing ---------------------------------------------------------

def test_password_is_stored_only_as_a_hash(conn):
    """Only the hash is saved, and it checks the right password but not a wrong one."""
    # Create an account and read what was stored for its password.
    accounts.create_user(conn, "John", "Snow", "john@example.com", "password1")
    (stored,) = conn.execute("SELECT password_hash FROM users").fetchone()

    # The real password isn't in it, and it's an scrypt hash.
    assert "password1" not in stored
    assert stored.startswith("scrypt$")

    # The hash accepts the right password and rejects a wrong one.
    assert accounts.verify_password("password1", stored)
    assert not accounts.verify_password("password2", stored)


def test_same_password_gets_different_hashes():
    """The random salt makes every hash different, even for the same password."""
    assert accounts.hash_password("password1") != accounts.hash_password("password1")


def test_hash_keeps_its_own_cost_settings(monkeypatch):
    """Changing the cost settings later doesn't break existing passwords."""
    # Hash a password with the current cost.
    stored = accounts.hash_password("password1")

    # Pretend the cost was raised after this hash was made.
    monkeypatch.setattr(accounts, "SCRYPT_N", 2**11)

    # The old hash still checks, because it carries its own settings.
    assert accounts.verify_password("password1", stored)


# Run the test once for each broken hash in the list.
@pytest.mark.parametrize("bad_hash", ["", "plain-text", "bcrypt$1$2$3$4$5", "scrypt$x$8$1$aa$bb"])
def test_malformed_hashes_never_verify(bad_hash):
    """A damaged or unknown hash fails the check instead of crashing."""
    assert not accounts.verify_password("password1", bad_hash)


# --- Creating accounts ------------------------------------------------------------

def test_new_user_defaults(conn):
    """Email is trimmed and lowercased, and new accounts are ordinary users."""
    # Create an account with extra spaces and capitals in the email.
    user = accounts.create_user(conn, "John", "Snow", "  John@Example.COM ", "password1")

    # The email was cleaned, the role is "user", and there's no sign-in yet.
    assert user.email == "john@example.com"
    assert user.role == "user"
    assert user.last_login_at is None


def test_names_are_saved_trimmed(conn):
    """Names are trimmed and repeated spaces collapsed."""
    # Create an account with untidy spacing in both names.
    user = accounts.create_user(conn, "  Mary  Ann ", " Smith ", "mary@example.com", "password1")

    # The names were tidied before saving.
    assert (user.first_name, user.last_name) == ("Mary Ann", "Smith")


# Run the test once for each bad name: empty first name, blank last name, too-long first name.
@pytest.mark.parametrize("first, last, message", [
    ("", "Snow", "First name is required"),
    ("John", "   ", "Last name is required"),
    ("A" * 51, "Snow", "50 characters or fewer"),
])
def test_missing_or_long_names_are_rejected(conn, first, last, message):
    """Empty or too-long names are rejected and nothing is saved."""
    # Creating the account raises the matching error.
    with pytest.raises(AccountError, match=message):
        accounts.create_user(conn, first, last, "john@example.com", "password1")

    # Nothing was saved.
    assert accounts.list_users(conn) == []


def test_duplicate_email_is_rejected_regardless_of_case(conn):
    """An email can only be used once, whatever its capitalization."""
    # First account succeeds.
    accounts.create_user(conn, "John", "Snow", "john@example.com", "password1")

    # Second account with the same email in capitals is rejected.
    with pytest.raises(AccountError, match="already exists"):
        accounts.create_user(conn, "Jane", "Doe", "JOHN@example.com", "password2")

    # Only the first account exists.
    assert len(accounts.list_users(conn)) == 1


# Run the test once for each badly formed email.
@pytest.mark.parametrize("email", ["", "john", "john@", "@example.com", "john@example", "jo hn@example.com"])
def test_invalid_emails_are_rejected(conn, email):
    """Badly formed emails are rejected."""
    with pytest.raises(AccountError, match="valid email"):
        accounts.create_user(conn, "John", "Snow", email, "password1")


# Run the test once for each weak password: too short, no number, no letter, too long (130 characters).
@pytest.mark.parametrize("password", ["short1", "allletters", "12345678", "a1" * 65])
def test_weak_passwords_are_rejected(conn, password):
    """Passwords that break the rules are rejected and nothing is saved."""
    # Creating the account raises the password-rules error.
    with pytest.raises(AccountError, match="rules"):
        accounts.create_user(conn, "John", "Snow", "john@example.com", password)

    # Nothing was saved.
    assert accounts.list_users(conn) == []


# --- Admin actions -----------------------------------------------------------------

def test_password_reset_replaces_the_hash(conn):
    """After a reset, the new password works and the old one doesn't."""
    # Create an account, then change its password.
    user = accounts.create_user(conn, "John", "Snow", "john@example.com", "password1")
    accounts.set_password(conn, user.user_id, "newpassword2")

    # The stored hash now matches the new password only.
    assert accounts.verify_password("newpassword2", stored_hash(conn, user.user_id))
    assert not accounts.verify_password("password1", stored_hash(conn, user.user_id))


def test_password_reset_enforces_rules_and_existing_user(conn):
    """A reset needs a valid password and an existing user."""
    user = accounts.create_user(conn, "John", "Snow", "john@example.com", "password1")

    # A weak new password is rejected.
    with pytest.raises(AccountError, match="rules"):
        accounts.set_password(conn, user.user_id, "weak")

    # A user ID that doesn't exist is rejected.
    with pytest.raises(AccountError, match="No account"):
        accounts.set_password(conn, 999, "newpassword2")


def test_deleting_a_user(conn):
    """Only the chosen user is deleted, and deleting them again is an error."""
    # Create two accounts and delete the first.
    user = accounts.create_user(conn, "John", "Snow", "john@example.com", "password1")
    accounts.create_user(conn, "Jane", "Doe", "jane@example.com", "password2")
    accounts.delete_user(conn, user.user_id)

    # Only the second account is left.
    assert [u.email for u in accounts.list_users(conn)] == ["jane@example.com"]

    # Deleting the same user again is reported as an error.
    with pytest.raises(AccountError, match="No account"):
        accounts.delete_user(conn, user.user_id)