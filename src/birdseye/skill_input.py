"""Streamlit Skill Input component.

The user types in a dropdown that filters as they type (matching synonyms too),
picks a skill, and it moves into a separate list of added skills, each with a
button to remove it. The selection lives in st.session_state, so it lasts for
one browser session and is not tied to a user account. Replace the session
state with a profile table when accounts exist.
"""

import sqlite3

import streamlit as st

from birdseye.skill_search import clean_selection, list_skills, skill_label, skill_synonyms

SELECTED_KEY = "selected_skill_ids"
ADD_KEY = "add_skill_choice"
EMPTY_PROMPT = "Select at least one skill to see how you compare."


def _add_skill(labels: dict[str, int]) -> None:
    """Move the skill just picked into the selection and clear the dropdown."""
    label = st.session_state.get(ADD_KEY)
    if label in labels:
        current = st.session_state.get(SELECTED_KEY, [])
        st.session_state[SELECTED_KEY] = list(dict.fromkeys([*current, labels[label]]))
    st.session_state[ADD_KEY] = None


def _remove_skill(skill_id: int) -> None:
    st.session_state[SELECTED_KEY] = [
        chosen for chosen in st.session_state.get(SELECTED_KEY, []) if chosen != skill_id
    ]


def render_skill_input(conn: sqlite3.Connection) -> list[int]:
    """Draw the skill picker and return the selected skill IDs (alphabetical)."""
    all_skills = list_skills(conn)  # alphabetical
    by_id = {skill.skill_id: skill for skill in all_skills}
    position = {skill.skill_id: index for index, skill in enumerate(all_skills)}
    synonyms = skill_synonyms(conn)

    # Forget IDs that no longer exist (e.g. a skill was merged).
    state = clean_selection(st.session_state.get(SELECTED_KEY, []), by_id)
    st.session_state[SELECTED_KEY] = state
    already_added = set(state)

    # One option per skill not yet added, so a skill can't be added twice.
    labels = {
        skill_label(skill.name, synonyms.get(skill.skill_id, ())): skill.skill_id
        for skill in all_skills
        if skill.skill_id not in already_added
    }

    st.subheader("Your skills")
    st.selectbox(
        "Add a skill",
        options=list(labels),
        index=None,
        key=ADD_KEY,
        placeholder="Start typing, e.g. MS Excel or Postgres",
        on_change=_add_skill,
        args=(labels,),
    )

    selected = sorted(state, key=position.__getitem__)
    if not selected:
        st.info(EMPTY_PROMPT)
        return selected

    st.caption(f"{len(selected)} selected. Click a skill to remove it.")
    with st.container(horizontal=True):
        for skill_id in selected:
            st.button(
                by_id[skill_id].name,
                key=f"remove_skill_{skill_id}",
                icon=":material/close:",
                help=f"Remove {by_id[skill_id].name}",
                on_click=_remove_skill,
                args=(skill_id,),
            )
    return selected