from pathlib import Path

from streamlit.testing.v1 import AppTest

from birdseye.charts.top_skills import top_skills_chart
from birdseye.skill_summary import summarize
from birdseye.visualization_check import passes_check, top_three_answer_key


def test_answer_key_agrees_with_chart_and_accepts_cutoff_ties():
    row = summarize([
        {"role": "Marketing Manager", "skills": ["Campaigns", "Research", "Writing", "Budgeting"]},
        {"role": "Marketing Manager", "skills": ["Campaigns", "Research"]},
        {"role": "Marketing Manager", "skills": ["Campaigns"]},
    ], {})["roles"]["Marketing Manager"]
    key = top_three_answer_key(row)
    assert key == {"required": ["Campaigns", "Research"], "tied": ["Budgeting", "Writing"]}
    assert list(top_skills_chart("Marketing Manager", row).data[0].y) == [
        "Campaigns", "Research", "Budgeting", "Writing",
    ]
    assert passes_check(row, ["Campaigns", "Research", "Writing"], 60, guided=False)
    assert not passes_check(row, ["Campaigns", "Research", "Writing"], 61, guided=False)
    assert not passes_check(row, ["Campaigns", "Research", "Writing"], 45, guided=True)
    assert not passes_check(row, ["Budgeting", "Research", "Writing"], 45, guided=False)


def test_streamlit_dashboard_renders_the_synthetic_demo():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=15).run()
    assert not app.exception
    app.sidebar.checkbox[0].check().run()
    assert not app.exception
    assert len(app.get("plotly_chart")) == 9
    assert any("Marketing Manager" in title.value for title in app.subheader)
    assert any("No skills detected" in title.value for title in app.subheader)
