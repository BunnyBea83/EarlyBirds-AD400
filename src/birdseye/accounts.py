"""Local user accounts: the login database, password hashing and sign-up.

Accounts are kept in their own SQLite file (data/processed/accounts.db), separate
from the job data, so rebuilding birdseye.db never removes them.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Default accounts file, at the repository root's data/processed folder.
DEFAULT_ACCOUNTS_DB = Path(__file__).resolve().parents[2] / "data/processed/accounts.db"

# Password rules; PASSWORD_RULES is the text shown to users.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
PASSWORD_RULES = (
    f"At least {MIN_PASSWORD_LENGTH} characters, with at least one letter and one number."
)

# scrypt cost settings (OWASP recommendation). Saved inside each hash, so they can change later.
SCRYPT_N = 2**17
SCRYPT_R = 8
SCRYPT_P = 1
_SCRYPT_MAXMEM = 2**28  # these settings need about 128 MiB

MAX_NAME_LENGTH = 50

# Simple check for something@something.something with no spaces.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccountError(ValueError):
    """A sign-up or admin request that can't be completed. The message is safe to show users."""


@dataclass(frozen=True)
class User:
    """One user, without the password hash so it can't be shown by accident."""

    user_id: int
    email: str
    first_name: str
    last_name: str
    # "user" or "admin"
    role: str
    # UTC
    created_at: str
    # None until the user first signs in
    last_login_at: str | None

# ---------------------------------------------------------------
#     Database
# ---------------------------------------------------------------

def accounts_db_path() -> Path:
    """The accounts database: BIRDSEYE_ACCOUNTS_DB if set, otherwise data/processed/accounts.db."""
    configured = os.environ.get("BIRDSEYE_ACCOUNTS_DB")
    return Path(configured).expanduser().resolve() if configured else DEFAULT_ACCOUNTS_DB


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open the accounts database, creating its folder and tables if needed."""
    db_path = accounts_db_path() if db_path is None else db_path
    #  in-memory databases (used in tests) have no folder
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    initialize_accounts(conn)
    return conn


def initialize_accounts(conn: sqlite3.Connection) -> None:
    """Create the users table. Safe to run again on an existing database."""
    # needed for future tables that link to users
    conn.execute("PRAGMA foreign_keys = ON")
    # commits on success, undoes everything on an error
    with conn:
        # COLLATE NOCASE makes the email UNIQUE check ignore case.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
                created_at TEXT NOT NULL,
                last_login_at TEXT
            )
        """)

# ---------------------------------------------------------------
#    Validation and hashing
# ---------------------------------------------------------------

def normalize_email(email: str) -> str:
    """Trim and lowercase an email so Name@X.com and name@x.com are one account."""
    return email.strip().lower()


def validate_name(name: str, label: str) -> str:
    """Return the trimmed name, or raise AccountError if it's empty or too long. `label` is e.g. "First name"."""
    # trim and collapse repeated spaces
    name = " ".join(name.split())
    if not name:
        raise AccountError(f"{label} is required.")
    if len(name) > MAX_NAME_LENGTH:
        raise AccountError(f"{label} must be {MAX_NAME_LENGTH} characters or fewer.")
    return name


def validate_email(email: str) -> str:
    """Return the normalized email, or raise AccountError if it isn't a plausible address."""
    normalized = normalize_email(email)
    if len(normalized) > 254 or not _EMAIL_PATTERN.match(normalized):  # 254 is the longest valid email
        raise AccountError("Enter a valid email address, like name@example.com.")
    return normalized


def validate_password(password: str) -> None:
    """Raise AccountError if the password doesn't meet PASSWORD_RULES."""
    if (
        not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH
        or not any(ch.isalpha() for ch in password)
        or not any(ch.isdigit() for ch in password)
    ):
        raise AccountError(f"Password doesn't meet the rules. {PASSWORD_RULES}")


def hash_password(password: str) -> str:
    """Return a salted scrypt hash in the form scrypt$n$r$p$salt$hash.

    The random salt means two users with the same password get different hashes.
    """
    # Create 16 random bytes for the hash
    salt = secrets.token_bytes(16)
    # Hash the password using salt bytes
    digest = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    # Combine the hashed password into one string
    return "$".join(["scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P), _b64(salt), _b64(digest)])


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against a stored hash. A damaged hash fails instead of crashing."""
    try:
        # Split stored string into pieces
        scheme, n, r, p, salt, expected = stored_hash.split("$")
        # Make sure its a scrypt hash
        if scheme != "scrypt":
            return False
        # Hash the typed in password
        digest = _scrypt(password, _unb64(salt), int(n), int(r), int(p))
    # Handle broken hashes
    # Can occur from a hash stored in an incorrect format, a bad setting, or a bad salt
    except (ValueError, TypeError):
        return False
    # compare_digest takes the same time however close the guess is.
    return hmac.compare_digest(digest, _unb64(expected))


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    """Hash a password with scrypt using the given salt and cost settings; returns 32 bytes."""
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=_SCRYPT_MAXMEM, dklen=32)


def _b64(data: bytes) -> str:
    """Convert bytes (a salt or hash) to base64 text so they can be stored in the database."""
    return base64.b64encode(data).decode()


def _unb64(text: str) -> bytes:
    """Convert base64 text from the database back into bytes."""
    return base64.b64decode(text.encode())

# ---------------------------------------------------------------
#     Accounts
# ---------------------------------------------------------------
# Queries use ? placeholders, which prevents SQL injection.

# Columns that make up a User, in the same order as its fields.
_USER_COLUMNS = "user_id, email, first_name, last_name, role, created_at, last_login_at"

def create_user(
    conn: sqlite3.Connection, first_name: str, last_name: str, email: str, password: str, *, role: str = "user"
) -> User:
    """Create an account. Raises AccountError for a missing name, bad email, weak password or taken email."""
    first_name = validate_name(first_name, "First name")
    last_name = validate_name(last_name, "Last name")
    email = validate_email(email)
    validate_password(password)
    # Raise role error
    if role not in ("user", "admin"):
        raise AccountError("Role must be 'user' or 'admin'.")
    # Notify if account already exists
    if get_user_by_email(conn, email) is not None:
        raise AccountError("An account with that email already exists. Sign in instead.")
    try:
        with conn:
            # Run the SQL call
            cursor = conn.execute(
                # Add new user details into user table
                "INSERT INTO users(email, first_name, last_name, password_hash, role, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                # These values replace '?'
                (email, first_name, last_name, hash_password(password), role, _now()),
            )
    # Two sign-ups with the same email at once
    except sqlite3.IntegrityError as error:
        raise AccountError("An account with that email already exists. Sign in instead.") from error
    return get_user(conn, cursor.lastrowid)


def get_user(conn: sqlite3.Connection, user_id: int) -> User | None:
    """Look up a user by ID, or return None."""
    # Run the SQL call
    row = conn.execute(
        "SELECT " + _USER_COLUMNS + " FROM users WHERE user_id = ?",
        # This value replaces '?'
        (user_id,),
    ).fetchone()
    # Return found user or none
    return User(*row) if row else None


def get_user_by_email(conn: sqlite3.Connection, email: str) -> User | None:
    """Look up a user by email (any capitalization), or return None."""
    # Run the SQL call
    row = conn.execute(
        "SELECT " + _USER_COLUMNS + " FROM users WHERE email = ?",
        # This value replaces '?'
        (normalize_email(email),),
    ).fetchone()
    # Return found user or none
    return User(*row) if row else None


def list_users(conn: sqlite3.Connection) -> list[User]:
    """All users, oldest account first."""
    # Run the SQL call
    rows = conn.execute(
        "SELECT " + _USER_COLUMNS + " FROM users ORDER BY user_id"
    ).fetchall()
    return [User(*row) for row in rows]


def set_password(conn: sqlite3.Connection, user_id: int, new_password: str) -> None:
    """Replace a user's password, using the same rules as sign-up."""
    validate_password(new_password)
    with conn:
        # Run the SQL call
        updated = conn.execute(
            "UPDATE users SET password_hash = ? WHERE user_id = ?", (hash_password(new_password), user_id)
        # 0 means no such user
        ).rowcount
        if not updated:
            raise AccountError("No account with that user ID.")


def delete_user(conn: sqlite3.Connection, user_id: int) -> None:
    """Delete a user. Rows in tables linked with ON DELETE CASCADE go with them."""
    # Run the SQL call
    with conn:
        if not conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,)).rowcount:
            raise AccountError("No account with that user ID.")


def _now() -> str:
    """Current UTC time as fixed-width text, so timestamps sort correctly in SQL."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")