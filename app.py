"""Run Birdseye View with: streamlit run app.py."""

import os
import sqlite3

import streamlit as st

from birdseye.charts.top_skills import top_skills_chart
from birdseye.skill_summary import load_summary, summarize


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
if demo:
    st.info("Synthetic example for testing. These figures do not describe the job market.")
    summary = demo_summary()
else:
    try:
        summary = load_summary(os.environ.get("BIRDSEYE_DB", "data/processed/birdseye.db"))
    except sqlite3.Error:
        st.error("Build the cleaned database and run skill extraction, or select synthetic demo data.")
        st.stop()

roles = summary["roles"]
unresolved = sum(summary["unresolved_roles"].values())
if unresolved:
    st.caption(f"{unresolved:,} postings with unresolved roles are excluded from these charts.")
st.header("Top skills by role")
for role, row in roles.items():
    st.plotly_chart(top_skills_chart(role, row), key=f"top-{role}")
st.caption("A posting can mention several skills, so these percentages can add up to more than 100%.")
