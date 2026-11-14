from birdseye.charts.word_cloud import skill_word_cloud
from birdseye.skill_summary import summarize


def test_cloud_preserves_multiword_labels_and_uses_posting_frequency():
    rows = [
        {"role": "Marketing Manager", "skills": ["Project management", "Project management", "Writing"]},
        {"role": "Marketing Manager", "skills": ["Project management"]},
    ]
    summary = summarize(rows, {})["roles"]
    cloud = skill_word_cloud(summary["Marketing Manager"])
    assert cloud.words_ == {"Project management": 1, "Writing": 0.5}
    assert skill_word_cloud(summary["Data Analyst"]) is None
