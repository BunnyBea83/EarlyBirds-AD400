"""The "How well do my skills match a role?" section (TA4-48, TA4-50).

It reuses the role chosen in the role dropdown, the stored role profile (the same top
skills the profile chart shows) and the skills picked in the skill picker.
"""

from collections.abc import Iterable

import streamlit as st

from birdseye.skill_match import match_label, match_skills

HEADER = "How well do my skills match a role?"


def render_skill_gap(role: str | None, profile: list[dict] | None, have_skills: Iterable[str]) -> None:
    """Show the match and the skills the person has and is missing for `role`.

    role is None until a role is chosen; profile is None when the role's stored profile
    could not be loaded (the profile section already explains why).
    """
    have_skills = set(have_skills)
    st.header(HEADER)
    if role is None:
        st.info('Choose a role under "Role skill profile" to compare your skills with it.')
        return
    if not have_skills:
        st.info('Add your skills under "Your skills" to see how well they match this role.')
        return
    if profile is None:
        return
    if not profile:
        st.info("No skills meet the minimum posting share for this role.")
        return

    result = match_skills(profile, have_skills)
    st.metric(f"Your match with {role}", match_label(result))
    st.caption(f"This counts how many of the top {result['total']} skills in {role} postings you have.")

    have_column, missing_column = st.columns(2)
    for column, label, rows in ((have_column, "You have", result["have"]),
                                (missing_column, "Missing", result["missing"])):
        column.subheader(f"{label} ({len(rows)})")
        if rows:
            column.dataframe(
                [{"Skill": row["skill"], f"Share of {role} postings": f"{row['percentage']:.0f}%"}
                 for row in rows],
                hide_index=True,
            )
    st.caption("Skills are listed from most to least requested for this role.")