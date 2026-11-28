"""Create the local accounts database and, optionally, add the shared test users.

    python scripts/setup_accounts.py           create data/processed/accounts.db
    python scripts/setup_accounts.py --seed    also add the test users below

The app creates the tables itself on first run, so this is mainly for --seed.
These passwords are for local testing only. Never use a real password here.
"""

import argparse
import sys
from contextlib import closing
from pathlib import Path

from birdseye import accounts

# Shared test logins, also listed in the README.
TEST_USERS = [
    # (first name, last name, email, password, role)
    ("Test", "User", "test@birdseye.dev", "birdseye123", "user"),
    ("Second", "Tester", "test2@birdseye.dev", "birdseye123", "user"),
    ("Admin", "User", "admin@birdseye.dev", "birdseye123", "admin"),
]


def main() -> int:
    """Create the accounts database, and add the test users if --seed is given."""
    # Read the command-line options (--help shows the first line of this file's docstring).
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # No --db means the same file the app uses.
    parser.add_argument("--db", type=Path, default=None,
                        help="accounts database (default: BIRDSEYE_ACCOUNTS_DB or data/processed/accounts.db)")
    parser.add_argument("--seed", action="store_true", help="add the shared test users")
    args = parser.parse_args()

    # Open the database, creating the file and users table if they're missing.
    with closing(accounts.connect(args.db)) as conn:
        print(f"Accounts database ready at {args.db or accounts.accounts_db_path()}")

        # Add each test user, unless it already exists.
        if args.seed:
            for first_name, last_name, email, password, role in TEST_USERS:
                # Skip existing users, so running --seed twice is safe.
                if accounts.get_user_by_email(conn, email):
                    print(f"  {email} already exists, skipped")
                else:
                    accounts.create_user(conn, first_name, last_name, email, password, role=role)
                    print(f"  added {email} ({role})")
            print(f"Test password for all test users: {TEST_USERS[0][3]}")
    # 0 means success
    return 0


# Run main() only when the file is run as a script, not when it's imported (e.g. by the tests).
if __name__ == "__main__":
    sys.exit(main())