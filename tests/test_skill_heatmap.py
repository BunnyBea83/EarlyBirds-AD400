from birdseye.charts.heatmap import skill_heatmap
from birdseye.skill_summary import summarize


def test_heatmap_ranks_all_skills_and_distinguishes_zero_and_no_postings():
    roles = ("Data Analyst", "Marketing Manager", "Software Engineer")
    skills = [f"Skill {i:02}" for i in range(21)]
    summary = summarize([
        {"role": roles[0], "skills": skills + [skills[-1]]},
        {"role": roles[0], "skills": []},
        {"role": roles[1], "skills": [skills[-1]]},
    ], {}, roles)["roles"]
    chart = skill_heatmap(summary)
    trace = chart.data[0]
    assert len(trace.y) == 20
    assert list(trace.y[:3]) == ["Skill 20", "Skill 00", "Skill 01"]
    assert list(trace.z[1]) == [50, 0, None]
    assert [a.text for a in chart.layout.annotations[3:6]] == ["50.0%", "0.0%", "N/A"]
    assert (trace.zmin, trace.zmax) == (0, 100)
