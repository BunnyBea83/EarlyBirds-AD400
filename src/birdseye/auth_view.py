"""Streamlit form for creating an account from the dashboard sidebar.

Accounts are optional: the skills dashboard works the same for everyone.
The account logic itself is in accounts.py.
"""

from contextlib import closing

import streamlit as st

from birdseye import accounts
from birdseye.accounts import AccountError

# Session state key for a message to show after the page reruns.
NOTICE_KEY = "account_notice"


def render_account_sidebar() -> None:
    """Show the optional create-account form in the sidebar."""
    with st.sidebar:
        # Show a success message saved before the last rerun, then remove it so it appears once.
        notice = st.session_state.pop(NOTICE_KEY, None)
        if notice:
            st.success(notice)

        # The form sits in an expander that starts closed, so it's easy to ignore.
        with st.expander("Create an account (optional)"):
            render_sign_up_form(key="sidebar")

        # Separate the account section from the dashboard options below it.
        st.divider()


def render_sign_up_form(*, key: str) -> None:
    """Create-account form. `key` keeps widget names unique if the form appears more than once."""

    fields = [f"{key}-sign-up-{name}" for name in ("first", "last", "email", "password", "confirm")]

    # After a successful sign-up, empty the fields before they're drawn (they can't be changed after).
    if st.session_state.pop(f"{key}-sign-up-done", False):
        for field in fields:
            st.session_state[field] = ""
    # Draw the form. Fields are sent together when the button is clicked, and
    # clear_on_submit=False keeps what the user typed if there's an error.
    with st.form(f"{key}-sign-up", clear_on_submit=False):
        first_name = st.text_input("First name", key=f"{key}-sign-up-first")
        last_name = st.text_input("Last name", key=f"{key}-sign-up-last")
        email = st.text_input("Email", key=f"{key}-sign-up-email")
        # Typing is hidden
        password = st.text_input("Password", type="password", key=f"{key}-sign-up-password")
        confirm = st.text_input("Confirm password", type="password", key=f"{key}-sign-up-confirm")
        # Show the password rules under the fields
        st.caption(accounts.PASSWORD_RULES)
        submitted = st.form_submit_button("Create account")

    # Nothing else to do until the button is clicked.
    if not submitted:
        return

    # Check the two password boxes match (only the form has a confirm box, so it's checked here).
    if password != confirm:
        st.error("Passwords don't match.")
        return

    # Save the account. create_user checks the names, email and password rules.
    try:
        with closing(accounts.connect()) as conn:  # closes the connection even on an error
            user = accounts.create_user(conn, first_name, last_name, email, password)
    except AccountError as error:
        # Missing name, bad email, weak password or email already taken: show the reason.
        st.error(str(error))
        return

    # Save the success message to show after the rerun (anything shown now would disappear).
    st.session_state[NOTICE_KEY] = f"Account created for {user.first_name} {user.last_name} ({user.email})."

    # Mark the form to be emptied on the next redraw (see the top of this function).
    st.session_state[f"{key}-sign-up-done"] = True
    
    # Redraw the page from the top so the message shows and the form is empty.
    st.rerun()