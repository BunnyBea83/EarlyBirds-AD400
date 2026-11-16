"""Streamlit pieces for the role comparison (TA4-59).

Kept apart from role_comparison.py so the grouping logic needs no Streamlit.
"""

from collections.abc import Iterable, Mapping

import streamlit as st

from birdseye.role_comparison import TOP_SKILLS, compare_roles, comparison_rows, role_choices

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
    """Pick two roles and show their top skills side by side.

    Changing either dropdown reruns the comparison. TA4-63 adds the written summary.
    """
    role_a, role_b = render_role_pickers(roles)
    if role_a is None or role_b is None:
        st.info("Choose two roles to compare their skills.")
        return
    result = compare_roles(role_a, role_b, roles)
    st.markdown(
        f"**{role_a}:** {result['total_a']:,} postings \u00b7 "
        f"**{role_b}:** {result['total_b']:,} postings"
    )
    rows = comparison_rows(result)
    if not rows:
        st.info("No skills were found in the postings for these roles, so there is nothing to compare yet.")
        return
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config={
            role: st.column_config.NumberColumn(
                format="%.1f%%", help=f"Percent of {role} postings that mention the skill"
            )
            for role in (role_a, role_b)
        },
    )
    st.caption(
        f"Each number is the percentage of that role's own postings that mention the skill. "
        f"Skills are grouped by whether they are among the top {TOP_SKILLS} for both roles or "
        "just one. A skill listed as unique to one role can still appear in the other role's "
        "postings, just less often. Within each group, skills are listed from most to least in demand."
    )