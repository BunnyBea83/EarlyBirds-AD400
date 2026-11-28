"""The optional create-account form in the sidebar. Skipped if Streamlit's test runner is unavailable."""

import pytest

from birdseye import accounts
from contextlib import closing


def _sidebar_app():
    """A tiny app with just the sidebar form and some stand-in dashboard content."""
    import streamlit as st

    from birdseye.auth_view import render_account_sidebar

    render_account_sidebar()
    st.write("Dashboard content")


@pytest.fixture
def accounts_db(tmp_path, monkeypatch):
    """Point the app at a temporary accounts file and use fast hashing."""
    # Pick a temporary file
    db_path = tmp_path / "accounts.db"
    # Point application at temp file
    monkeypatch.setenv("BIRDSEYE_ACCOUNTS_DB", str(db_path))
    # Hash the password quickly
    monkeypatch.setattr(accounts, "SCRYPT_N", 2**10)
    # Hands path to any test calling this function
    return db_path


@pytest.fixture
def app(accounts_db):
    """Run the tiny app with Streamlit's test runner (no browser needed)."""
    # skip these tests if the runner isn't installed
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    return AppTest.from_function(_sidebar_app).run()


def _create(app, email, password, confirm=None, first="John", last="Snow"):
    """Fill in the form and click Create account."""
    app.text_input(key="sidebar-sign-up-first").input(first)
    app.text_input(key="sidebar-sign-up-last").input(last)
    app.text_input(key="sidebar-sign-up-email").input(email)
    app.text_input(key="sidebar-sign-up-password").input(password)
    app.text_input(key="sidebar-sign-up-confirm").input(password if confirm is None else confirm)
    # Click the form's button, then rerun the app to see the result.
    return [b for b in app.button if b.label == "Create account"][0].click().run()


def _emails(db_path):
    """Emails saved in the accounts file."""
    with closing(accounts.connect(db_path)) as conn:
        return [u.email for u in accounts.list_users(conn)]


def test_account_creation_is_optional(app):
    """The form starts collapsed and the dashboard shows without an account."""
    # Check page loaded without crashing
    assert not app.exception
    # Confirm creation form is in one closed section
    assert [e.label for e in app.sidebar.expander] == ["Create an account (optional)"]
    # Verify dashboard shows without login
    assert any(m.value == "Dashboard content" for m in app.markdown)


def test_create_account_saves_user_and_clears_form(app, accounts_db):
    """A valid form saves the account, shows a message and empties the fields."""
    # Fill in submission form
    app = _create(app, " John@Example.com ", "password2")
    # Check nothing crashed
    assert not app.exception
    # Check the user sees the right message
    assert [s.value for s in app.success] == ["Account created for John Snow (john@example.com)."]
    # Check if the account was saved
    assert _emails(accounts_db) == ["john@example.com"]
    # The form is emptied after a successful sign-up.
    assert app.text_input(key="sidebar-sign-up-email").value == ""
    assert app.text_input(key="sidebar-sign-up-first").value == ""


def test_mismatched_passwords_create_nothing(app, accounts_db):
    """Different passwords in the two boxes show an error and save nothing."""
    # Fill in the form with a different password
    app = _create(app, "john@example.com", "password2", confirm="password3")
    # Check the page shows an error box
    assert [e.value for e in app.error] == ["Passwords don't match."]
    # Check nothing was saved
    assert _emails(accounts_db) == []


def test_weak_password_shows_the_rules(app, accounts_db):
    """A weak password shows the password rules and saves nothing."""
    # Submit the form with with no number and short password
    app = _create(app, "john@example.com", "short")
    # Check password rules are displayed
    assert "rules" in app.error[0].value
    # Check nothing was saved
    assert _emails(accounts_db) == []


def test_duplicate_email_is_rejected(app, accounts_db):
    """Signing up twice with the same email is rejected."""
    # Create successful sign in
    app = _create(app, "john@example.com", "password2")
    # Same email, different capitalization
    app = _create(app, "JOHN@example.com", "password3")
    # Check for already exists error
    assert "already exists" in app.error[0].value
    # Check only the first account was saved
    assert _emails(accounts_db) == ["john@example.com"]


def test_missing_name_creates_nothing(app, accounts_db):
    """A missing first name shows an error and saves nothing."""
    # Create form with no name
    app = _create(app, "john@example.com", "password2", first="")
    # Check no name display error
    assert [e.value for e in app.error] == ["First name is required."]
    # Check nothing was saved
    assert _emails(accounts_db) == []