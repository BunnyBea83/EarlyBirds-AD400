"""Score a facilitator's usability check against the dashboard rankings."""

from math import isfinite


def top_three_answer_key(summary):
    """Return required skills and interchangeable skills at the cutoff."""
    skills = summary["skills"]
    if len(skills) < 3:
        raise ValueError("Choose a role with at least three observed skills.")
    cutoff = skills[2]["posting_count"]
    return {
        "required": [row["skill"] for row in skills if row["posting_count"] > cutoff],
        "tied": [row["skill"] for row in skills if row["posting_count"] == cutoff],
    }


def passes_check(summary, answers, elapsed_seconds, *, guided):
    key = top_three_answer_key(summary)
    submitted = {answer.strip().casefold() for answer in answers}
    required = {skill.casefold() for skill in key["required"]}
    tied = {skill.casefold() for skill in key["tied"]}
    return (
        not guided
        and isfinite(elapsed_seconds)
        and 0 <= elapsed_seconds <= 60
        and len(answers) == len(submitted) == 3
        and required <= submitted <= required | tied
    )
