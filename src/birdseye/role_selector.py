"""Role dropdown shared by the dashboard sections (TA4-52, reused by TA4-54).

The list of roles comes from the role taxonomy (birdseye.roles.ROLE_RULES), so a
role added there appears in every dropdown without further changes.
"""

from collections.abc import Iterable

import streamlit as st

from birdseye.roles import NEEDS_REVIEW, UNKNOWN

ALL_POSTINGS = "All postings"


def role_options(
    role_names: Iterable[str], *, include_all: bool = False, all_label: str = ALL_POSTINGS
) -> list[str]:
    """Return the roles a person can choose, each once and in the order given.

    The catch-all labels "Unknown" and "Needs review" are not roles, so they are
    left out. With include_all, an "All postings" choice comes first.
    """
    options = [name for name in dict.fromkeys(role_names) if name not in (UNKNOWN, NEEDS_REVIEW)]
    return [all_label, *options] if include_all else options


def render_role_dropdown(
    role_names: Iterable[str],
    *,
    key: str,
    label: str = "Role",
    include_all: bool = False,
    all_label: str = ALL_POSTINGS,
    placeholder: str = "Choose a role",
) -> str | None:
    """Draw a single-choice role dropdown and return the chosen role.

    Choosing a different item replaces the previous choice. Without include_all
    nothing is chosen at first and the result is None; with it, "All postings"
    is chosen at first. Each dropdown on a page needs its own key.
    """
    options = role_options(role_names, include_all=include_all, all_label=all_label)
    return st.selectbox(
        label,
        options,
        index=0 if include_all else None,
        key=key,
        placeholder=placeholder,
    )