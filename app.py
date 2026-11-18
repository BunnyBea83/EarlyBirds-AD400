"""Run Birdseye View with: streamlit run app.py."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

import streamlit as st

from birdseye.charts.heatmap import skill_heatmap
from birdseye.charts.top_skills import top_skills_chart
from birdseye.role_profiles import MAX_PROFILE_SKILLS, MissingRoleProfiles, load_role_profile, profile_skills
from birdseye.role_selector import ALL_POSTINGS, render_role_dropdown
from birdseye.skill_input import render_skill_input
from birdseye.skill_gap_view import render_skill_gap
from birdseye.skill_ranking import combine_roles, load_top_skills
from birdseye.skill_search import list_skills
from birdseye.skill_summary import MissingSkillTables, load_summary, summarize


def demo_summary():
    postings = [
        {"role": "Data Analyst", "skills": ["SQL", "Python", "Data visualization"]},
        {"role": "Data Analyst", "skills": ["SQL", "Python"]},
        {"role": "Data Analyst", "skills": []},
        {"role": "Marketing Manager", "skills": ["Project management", "Writing", "Market research"]},
        {"role": "Marketing Manager", "skills": ["Project management", "Writing"]},
        {"role": "Registered Nurse", "skills": []},
    ]
    return summarize(postings, {
        "SQL": "Software", "Python": "Software", "Data visualization": "Analysis",
        "Project management": "Management", "Writing": "Communication",
        "Market research": "Analysis",
    })


st.set_page_config(page_title="Birdseye View", layout="wide")
st.title("Birdseye View")
demo = st.sidebar.checkbox("Use synthetic demo data")
database = None  # only set to a real path when not in demo mode
if demo:
    st.info("Synthetic example for testing. These figures do not describe the job market.")
    summary = demo_summary()
else:
    default_database = Path(__file__).resolve().parent / "data/processed/birdseye.db"
    database = Path(os.environ.get("BIRDSEYE_DB") or default_database).expanduser().resolve()
    if not database.is_file():
        st.error(f"Database file not found at {database}. Build it with scripts/clean_data.py "
                 "or set BIRDSEYE_DB to an existing database.")
        st.stop()
    try:
        summary = load_summary(database)
    except MissingSkillTables as error:
        st.error(f"{error} See the README for the extraction command.")
        st.stop()
    except sqlite3.Error as error:
        st.error(f"Could not load the database at {database}. "
                 "Check that the selected file is a cleaned Birdseye database.")
        st.code(str(error), language="text")
        st.stop()

roles = summary["roles"]
unresolved = sum(summary["unresolved_roles"].values())
if unresolved:
    st.caption(f"{unresolved:,} postings with unresolved roles are excluded from the by-role "
               "charts. The \"All postings\" chart includes them.")

# --- TA4-66: Top skills by role ---
st.header("Top skills by role")
for role, row in roles.items():
    st.plotly_chart(top_skills_chart(role, row), key=f"top-{role}")
st.caption("A posting can mention several skills, so these percentages can add up to more than 100%.")

# --- TA4-54: Most requested skills (top 15), all postings or one role ---
st.header("Most requested skills")
overall = combine_roles(roles) if demo else load_top_skills(database)
choice = render_role_dropdown(
    roles, key="top-skills-role", label="Show skills requested for", include_all=True
)
chosen = overall if choice == ALL_POSTINGS else roles[choice]
st.plotly_chart(top_skills_chart(choice, chosen), key="most-requested")
st.caption(
    f"Based on {chosen['total_postings']:,} postings. Each bar shows the percentage of "
    "job postings that mention the skill. A posting can mention several skills, so the "
    "percentages can add up to more than 100%."
)

# --- TA4-52: Role dropdown (shares its list and behavior with TA4-54) ---
# --- TA4-51: The selected role's stored skill profile (up to 20 skills) ---
st.header("Role skill profile")
target_role = render_role_dropdown(roles, key="target-role")  # None until a role is picked
profile = None  # the selected role's profile; stays None until a role is picked and its profile loads
if target_role is None:
    st.info(f"Choose a role to see its top {MAX_PROFILE_SKILLS} skills.")
else:
    if demo:
        profile = profile_skills(roles[target_role]["skills"])  # the demo has no database table
    else:
        try:
            profile = load_role_profile(database, target_role)
        except MissingRoleProfiles as error:
            st.warning(str(error))
    if profile is not None:
        st.plotly_chart(
            top_skills_chart(target_role, {
                "total_postings": roles[target_role]["total_postings"], "top_skills": profile,
            }),
            key="role-profile",
        )

# --- TA4-41: Skill input (the person's own skills) ---
selected_skill_names = set()  # skill names the person picked; empty until they pick some
if database is None:
    st.caption("Skill selection uses the real database. Turn off the synthetic demo data to use it.")
else:
    try:
        with closing(sqlite3.connect(database)) as conn:
            selected_skill_ids = render_skill_input(conn)
            names_by_id = {skill.skill_id: skill.name for skill in list_skills(conn)}
        selected_skill_names = {names_by_id[skill_id] for skill_id in selected_skill_ids}
    except sqlite3.Error as error:
        st.error("Could not load skills from the database. Check that it was built with the skill catalog.")
        st.code(str(error), language="text")

# --- TA4-48 / TA4-50: Which of the role's top skills you have and are missing, and your match ---
if demo:
    st.header("How well do my skills match a role?")
    st.caption("Skill matching uses the real database. Turn off the synthetic demo data to use it.")
else:
    render_skill_gap(target_role, profile, selected_skill_names)

# --- TA4-67: Compare skill demand across roles in a heatmap ---
st.header("Compare skill demand across roles")
with st.container(horizontal=True):
    st.plotly_chart(skill_heatmap(roles), width="content", key="skill-heatmap")