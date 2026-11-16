"""Streamlit pieces for the role comparison (TA4-59).

Kept apart from role_comparison.py so the grouping logic needs no Streamlit.
"""

from collections.abc import Iterable, Mapping

import streamlit as st

from birdseye.role_comparison import compare_roles, role_choices

KEY_A = "compare-role-a"
KEY_B = "compare-role-b"


def render_role_pickers(
    role_names: Iterable[str], *, key_a: str = KEY_A, key_b: str = KEY_B
) -> tuple[str | None, str | None]:
    """Draw two role dropdowns side by side and return (first role, second role).

    Both list every role alphabetically. A role chosen in one is removed from the
    other, so the same role can't be compared with itself. To swap the two roles,
    change one dropdown first. Nothing is chosen at first, so either can be None.
    """
    names = list(role_names)
    column_a, column_b = st.columns(2)
    with column_a:
        # The other dropdown's latest choice is already in session state on each rerun.
        choice_a = st.selectbox(
            "First role", role_choices(names, exclude=st.session_state.get(key_b)),
            index=None, key=key_a, placeholder="Choose a role",
        )
    with column_b:
        choice_b = st.selectbox(
            "Second role", role_choices(names, exclude=choice_a),
            index=None, key=key_b, placeholder="Choose a role",
        )
    return choice_a, choice_b


def render_role_comparison(roles: Mapping[str, dict]) -> None:
    """Pick two roles and show how their top skills compare.

    Changing either dropdown reruns the comparison. For now the result is a one-line
    count; TA4-62 replaces it with the side-by-side table and TA4-63 adds the paragraph.
    """
    role_a, role_b = render_role_pickers(roles)
    if role_a is None or role_b is None:
        st.info("Choose two roles to compare their skills.")
        return
    result = compare_roles(role_a, role_b, roles)
    st.caption(
        f"Shared skills: {len(result['shared'])}. Only in {role_a}: {len(result['only_a'])}. "
        f"Only in {role_b}: {len(result['only_b'])}."
    )