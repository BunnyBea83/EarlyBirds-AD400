from birdseye.charts.top_skills import top_skills_chart


def test_top_skills_chart_shows_ranked_percentages_on_common_axis():
    result = top_skills_chart("Data Analyst", {"total_postings": 4, "top_skills": [
        {"skill": "SQL", "percentage": 75}, {"skill": "Python", "percentage": 25},
    ]})
    assert list(result.data[0].y) == ["SQL", "Python"]
    assert list(result.data[0].text) == ["75.0%", "25.0%"]
    assert result.layout.yaxis.autorange == "reversed"
    assert tuple(result.layout.xaxis.range) == (0, 100)
    assert "4 postings" in result.layout.title.text


def test_top_skills_chart_handles_role_without_skills():
    result = top_skills_chart("Marketing Manager", {"total_postings": 1, "top_skills": []})
    assert result.layout.annotations[0].text == "No skills detected"
