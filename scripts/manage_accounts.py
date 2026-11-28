"""Admin tasks for local accounts, from the command line.

    python scripts/manage_accounts.py list
    python scripts/manage_accounts.py reset-password test@birdseye.dev
    python scripts/manage_accounts.py delete test@birdseye.dev

Add --db PATH before the command to use another accounts database.
"""

import argparse
import getpass
import sys
from contextlib import closing
from pathlib import Path

from birdseye import accounts
from birdseye.accounts import AccountError


def main() -> int:
    """Read the command, find the user if needed, and run the matching admin task."""
    # Read the command-line options (--help shows the first line of this file's docstring).
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # No --db means the same file the app uses.
    parser.add_argument("--db", type=Path, default=None,
                        help="accounts database (default: BIRDSEYE_ACCOUNTS_DB or data/processed/accounts.db)")

    # One sub-command per task, each with its own arguments.
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list all users")
    reset = commands.add_parser("reset-password", help="set a new password for a user")
    reset.add_argument("email")
    delete = commands.add_parser("delete", help="delete a user and their data")
    delete.add_argument("email")
    delete.add_argument("--yes", action="store_true", help="skip the confirmation question")
    args = parser.parse_args()

    # Open the accounts database and run the chosen command.
    with closing(accounts.connect(args.db)) as conn:
        try:
            if args.command == "list":
                return list_users(conn)

            # reset-password and delete both start by finding the user by email.
            user = accounts.get_user_by_email(conn, args.email)
            if user is None:
                raise AccountError(f"No account for {args.email}.")

            if args.command == "reset-password":
                return reset_password(conn, user)
            return delete_user(conn, user, confirmed=args.yes)
        except AccountError as error:
            # Show a short message instead of a traceback; exit code 1 means it failed.
            print(f"Error: {error}", file=sys.stderr)
            return 1


def list_users(conn) -> int:
    """Print every user as a table. Password hashes are never shown."""
    users = accounts.list_users(conn)

    # Say how to add test users if there aren't any yet.
    if not users:
        print("No accounts yet. Add test users with: python scripts/setup_accounts.py --seed")
        return 0

    # Print a header row, then one row per user, padded to fixed-width columns.
    print(f"{'ID':>4}  {'Name':<24} {'Email':<32} {'Role':<6} {'Created':<21} Last sign-in")
    for user in users:
        name = f"{user.first_name} {user.last_name}"
        print(f"{user.user_id:>4}  {name:<24} {user.email:<32} {user.role:<6} {user.created_at:<21} "
              f"{user.last_login_at or 'never'}")
    return 0


def reset_password(conn, user) -> int:
    """Ask for a new password twice and save it."""
    print(accounts.PASSWORD_RULES)

    # Ask for the password twice; getpass hides what's typed.
    new_password = getpass.getpass(f"New password for {user.email}: ")
    if new_password != getpass.getpass("Type it again: "):
        raise AccountError("Passwords don't match. Nothing was changed.")

    # Save it (set_password also checks the password rules).
    accounts.set_password(conn, user.user_id, new_password)
    print(f"Password changed for {user.email}.")
    return 0


def delete_user(conn, user, *, confirmed: bool) -> int:
    """Delete a user after asking to confirm, unless --yes was given."""
    # Ask first; anything other than y or yes (including just Enter) cancels.
    if not confirmed:
        answer = input(f"Delete {user.email} and all their data? This can't be undone. [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Nothing was deleted.")
            return 0

    # Delete the user (and anything linked to them).
    accounts.delete_user(conn, user.user_id)
    print(f"Deleted {user.email}.")
    return 0


# Run main() only when the file is run as a script, not when it's imported (e.g. by the tests).
if __name__ == "__main__":
    sys.exit(main())