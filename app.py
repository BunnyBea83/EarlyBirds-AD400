"""Run Birdseye View with: streamlit run app.py."""

import os
import sqlite3
from pathlib import Path

import streamlit as st
from contextlib import closing

from birdseye.skill_input import render_skill_input
from birdseye.charts.heatmap import skill_heatmap
from birdseye.charts.top_skills import top_skills_chart
from birdseye.skill_summary import MissingSkillTables, load_summary, summarize
from birdseye.skill_ranking import combine_roles, load_top_skills




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
    st.caption(f"{unresolved:,} postings with unresolved roles are excluded from these charts.")
st.header("Top skills by role")
for role, row in roles.items():
    st.plotly_chart(top_skills_chart(role, row), key=f"top-{role}")
st.caption("A posting can mention several skills, so these percentages can add up to more than 100%.")

st.header("Most requested skills")
overall = combine_roles(roles) if demo else load_top_skills(database)
choice = st.selectbox("Show skills requested for", ["All postings", *roles])
chosen = overall if choice == "All postings" else roles[choice]
st.plotly_chart(top_skills_chart(choice, chosen), key="most-requested")
st.caption(
    f"Based on {chosen['total_postings']:,} postings. Each bar shows the percentage of "
    "job postings that mention the skill. A posting can mention several skills, so the "
    "percentages can add up to more than 100%."
)

st.header("Compare skill demand across roles")
with st.container(horizontal=True):
    st.plotly_chart(skill_heatmap(roles), width="content", key="skill-heatmap")



if database is None:
    st.caption("Skill selection uses the real database. Turn off the synthetic demo data to use it.")
else:
    try:
        with closing(sqlite3.connect(database)) as conn:
            selected_skill_ids = render_skill_input(conn)
    except sqlite3.Error as error:
        st.error("Could not load skills from the database. Check that it was built with the skill catalog.")
        st.code(str(error), language="text")
