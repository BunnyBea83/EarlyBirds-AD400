"""Compare the top skills of two roles (TA4-59; grouping is subtask TA4-61).

Works on the per-role results from skill_summary (summary["roles"]), which hold
every skill's posting count and each role's total postings. No Streamlit and no
database access, so it can be tested directly.
"""

from collections.abc import Mapping

TOP_SKILLS = 20


def _share(count: int, total: int) -> float:
    """Percentage of `total` postings, or 0 when there are no postings."""
    return 100 * count / total if total else 0.0


def compare_roles(
    role_a: str, role_b: str, roles: Mapping[str, dict], size: int = TOP_SKILLS
) -> dict:
    """Sort two roles' top `size` skills into shared, unique to A and unique to B.

    A skill is shared if it is in both roles' top `size`, and unique to a role if
    it is in only that role's top `size`. Every row carries both roles' numbers:
      count_a, count_b       postings that mention the skill, in each role
      share_a, share_b       percent of each role's own postings (0 if never mentioned)
      combined_share         percent of both roles' postings pooled together
    A unique skill shows the other role's real share, even if that role has the
    skill outside its top `size`. Shared skills are sorted by combined_share, unique
    skills by their share in their own role; ties are alphabetical.
    """
    if role_a == role_b:
        raise ValueError("Choose two different roles to compare")
    for role in (role_a, role_b):
        if role not in roles:
            raise ValueError(f"Unknown role: {role}")
    entry_a, entry_b = roles[role_a], roles[role_b]
    total_a, total_b = entry_a["total_postings"], entry_b["total_postings"]
    counts_a = {row["skill"]: row["posting_count"] for row in entry_a["skills"]}
    counts_b = {row["skill"]: row["posting_count"] for row in entry_b["skills"]}

    def top(counts):
        ranked = sorted(counts, key=lambda skill: (-counts[skill], skill.casefold(), skill))
        return set(ranked[:size])

    top_a, top_b = top(counts_a), top(counts_b)

    def row(skill):
        count_a, count_b = counts_a.get(skill, 0), counts_b.get(skill, 0)
        return {
            "skill": skill,
            "count_a": count_a, "count_b": count_b,
            "share_a": _share(count_a, total_a), "share_b": _share(count_b, total_b),
            "combined_share": _share(count_a + count_b, total_a + total_b),
        }

    def ordered(skills, key):
        return sorted((row(skill) for skill in skills),
                      key=lambda item: (-item[key], item["skill"].casefold(), item["skill"]))

    return {
        "role_a": role_a, "role_b": role_b,
        "total_a": total_a, "total_b": total_b,
        "shared": ordered(top_a & top_b, "combined_share"),
        "only_a": ordered(top_a - top_b, "share_a"),
        "only_b": ordered(top_b - top_a, "share_b"),
    }