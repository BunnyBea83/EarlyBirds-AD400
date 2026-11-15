"""Streamlit Skill Input component.

The selection lives in st.session_state, so it lasts for one browser session
and is not tied to a user account. Replace the session state with a profile
table when accounts exist.
"""

import sqlite3

import streamlit as st

from birdseye.skill_search import clean_selection, list_skills, search_skills

SELECTED_KEY = "selected_skill_ids"
SEARCH_KEY = "skill_search_text"
EMPTY_PROMPT = "Select at least one skill to see how you compare."


def render_skill_input(conn: sqlite3.Connection) -> list[int]:
    """Draw the skill picker and return the selected skill IDs."""
    all_skills = list_skills(conn)  # alphabetical
    by_id = {skill.skill_id: skill for skill in all_skills}
    position = {skill.skill_id: index for index, skill in enumerate(all_skills)}

    # Forget IDs that no longer exist (e.g. a skill was merged) before the
    # widget is created.
    st.session_state[SELECTED_KEY] = clean_selection(
        st.session_state.get(SELECTED_KEY, []), by_id
    )

    st.subheader("Your skills")
    query = st.text_input(
        "Search skills",
        key=SEARCH_KEY,
        placeholder="Try a synonym, e.g. MS Excel or Postgres",
    )
    matches = search_skills(conn, query)
    if query.strip() and not matches:
        st.caption(f"No skills match '{query.strip()}'.")

    # Always keep the current selection in the options: Streamlit drops
    # selected values that are missing from the options.
    option_ids = {skill.skill_id for skill in matches} | set(st.session_state[SELECTED_KEY])
    options = sorted(option_ids, key=position.__getitem__)
    selected = st.multiselect(
        "Selected skills",
        options=options,
        key=SELECTED_KEY,
        format_func=lambda skill_id: by_id[skill_id].name,
        placeholder="Choose skills",
    )

    if not selected:
        st.info(EMPTY_PROMPT)
    return selected