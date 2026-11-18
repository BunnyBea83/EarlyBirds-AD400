import pytest

from birdseye.charts.category_mix import category_mix_chart
from birdseye.skill_summary import summarize


def test_category_mix_uses_skill_matches_and_stable_colors_across_roles():
    roles = ("Data Analyst", "Marketing Manager", "Registered Nurse")
    summary = summarize([
        {"role": roles[0], "skills": ["Python", "Python", "SQL", "Writing"]},
        {"role": roles[0], "skills": []},
        {"role": roles[1], "skills": ["Writing"]},
    ], {"Python": "Software", "SQL": "Software", "Writing": "Communication"}, roles)
    chart = category_mix_chart(summary["roles"])
    traces = {trace.name: trace for trace in chart.data}
    assert list(traces["Communication"].x) == pytest.approx([100 / 3, 100, 0])
    assert list(traces["Software"].x) == pytest.approx([200 / 3, 0, 0])
    assert traces["Software"].marker.color != traces["Communication"].marker.color
    assert chart.layout.barmode == "stack"
    assert chart.layout.annotations[0].y == roles[2]
