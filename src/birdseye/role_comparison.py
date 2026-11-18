"""Compare the top skills of two roles (TA4-59; grouping is subtask TA4-61).

Works on the per-role results from skill_summary (summary["roles"]), which hold
every skill's posting count and each role's total postings. No Streamlit and no
database access, so it can be tested directly.
"""

import math
from collections.abc import Iterable, Mapping

TOP_SKILLS = 20


def role_choices(role_names: Iterable[str], exclude: str | None = None) -> list[str]:
    """Roles a person can pick in one comparison dropdown, alphabetically.

    Each role appears once, ignoring letter case when sorting. The role chosen in the
    other dropdown is left out, so the same role can't be picked twice.
    """
    return sorted({name for name in role_names if name != exclude},
                  key=lambda name: (name.casefold(), name))


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


def comparison_rows(result: Mapping) -> list[dict]:
    """Flatten compare_roles() output into table rows for the side-by-side view (TA4-62).

    Each row has a "Group" ("Shared", "Unique to <role A>" or "Unique to <role B>"), the
    "Skill", and one column per role, named after the role, holding that skill's share
    (percent) of the role's own postings. Shared skills come first, then role A's unique
    skills, then role B's, each already sorted from most to least in demand.
    """
    role_a, role_b = result["role_a"], result["role_b"]
    groups = (
        ("Shared", result["shared"]),
        (f"Unique to {role_a}", result["only_a"]),
        (f"Unique to {role_b}", result["only_b"]),
    )
    return [
        {"Group": label, "Skill": row["skill"], role_a: row["share_a"], role_b: row["share_b"]}
        for label, rows in groups
        for row in rows
    ]


# --- Plain-language summary paragraph (TA4-63) ---

# The overlap wording depends on what share of the longer list the roles have in common, so it
# stays accurate for roles that have fewer than TOP_SKILLS skills.
MANY_SHARED = 0.4  # at or above this share, the roles "overlap quite a bit"
SOME_SHARED = 0.2  # below this share, they "share few of their most requested skills"


def _percent(share: float) -> str:
    """A share as a whole-number percentage, with "less than 1%" for tiny nonzero values."""
    if 0 < share < 0.5:
        return "less than 1%"
    return f"{math.floor(share + 0.5)}%"


def _top(size: int) -> str:
    """"the top 12" for a list of 12 skills; no number for a single skill."""
    return f"the top {size}" if size > 1 else "the top skills"


def _unique_sentence(role: str, other: str, rows: list[dict], key: str, also: bool, other_size: int) -> str:
    """One sentence about the skills that stand out for `role` but not for `other`."""
    if not rows:
        return f"Every one of the top skills found for {role} is also among {_top(other_size)} for {other}."
    named = f"{rows[0]['skill']} ({_percent(rows[0][key])} of {role} postings)"
    if len(rows) > 1:
        named += f" and {rows[1]['skill']} ({_percent(rows[1][key])})"
    lead = "also stand out" if also else "stand out"
    verb = "are" if len(rows) > 1 else "is"
    return f"{role} postings {lead} for {named}, which {verb} not among {_top(other_size)} for {other}."


def _overlap_clause(role_a: str, role_b: str, count: int, size_a: int, size_b: int) -> str:
    """"N of the M skills ..." using each role's real list length, not a fixed 20."""
    verb = "is" if count == 1 else "are"
    if size_a == size_b:
        return f"{count} of the {size_a} skills most often requested for each role {verb} the same"
    small, large, size_small, size_large = (role_a, role_b, size_a, size_b) if size_a < size_b \
        else (role_b, role_a, size_b, size_a)
    if count == size_small:
        lead = "the one skill" if count == 1 else f"all {count} of the skills"
        verb = "is" if count == 1 else "are"
        return f"{lead} most often requested for {small} {verb} also among the top {size_large} for {large}"
    return (f"{count} of the {size_small} skills most often requested for {small} {verb} also among "
            f"the top {size_large} for {large}")


def _takeaway(role_a: str, role_b: str, shared: list[dict], only_a: list[dict], only_b: list[dict]) -> str:
    """The closing sentence: what the roles share, plus a soft pointer to the best unique skill.

    It suggests looking into the most requested skill that is not among the other role's top skills, for
    the role the reader wants. It does not assume which role that is, and it does not predict
    how hard a move between the roles would be.
    """
    parts = []
    if shared:
        parts.append("the shared skills are the ones postings for both roles ask for")
    if only_a and only_b:
        parts.append(
            f"it may be worth looking into learning the most requested skill found in only one role's "
            f"top skills for the role you want: {only_a[0]['skill']} for {role_a} or "
            f"{only_b[0]['skill']} for {role_b}"
        )
    elif only_a or only_b:
        role, other, row = (role_a, role_b, only_a[0]) if only_a else (role_b, role_a, only_b[0])
        parts.append(
            f"if you are interested in {role}, it may be worth looking into learning {row['skill']}, "
            f"its most requested skill that is not among {other}'s top skills"
        )
    return "If you are comparing these roles, " + ", and ".join(parts) + "."


def describe_comparison(result: Mapping) -> str:
    """Write a short plain-language paragraph about what compare_roles() found (TA4-63).

    It follows a sentence template: how much the top skills overlap, up to two shared
    skills, up to two skills that stand out for each role (each with its share of that
    role's postings, as whole-number percentages), and a closing sentence that restates
    the overlap and suggests looking into the most requested unique skill. It only reports
    what the top-skill lists show: it does not predict how hard a move between the roles would
    be or how much a reader would need to learn. It does not assume which role the reader is
    coming from. When there are fewer than two skills to name, it names what exists. A role
    with no skills found gets one explanatory sentence instead.
    """
    role_a, role_b = result["role_a"], result["role_b"]
    shared, only_a, only_b = result["shared"], result["only_a"], result["only_b"]
    missing = [role for role, rows in ((role_a, shared + only_a), (role_b, shared + only_b)) if not rows]
    if len(missing) == 2:
        return f"We didn't find any skills in the {role_a} or {role_b} postings yet, so a comparison isn't possible."
    if missing:
        other = role_b if missing[0] == role_a else role_a
        return f"We didn't find any skills in the {missing[0]} postings yet, so a comparison with {other} isn't possible."

    count = len(shared)
    size_a, size_b = count + len(only_a), count + len(only_b)  # the lists' real lengths
    named = f"{shared[0]['skill']} (mentioned in {_percent(shared[0]['share_a'])} of {role_a} postings " \
            f"and {_percent(shared[0]['share_b'])} of {role_b} postings)" if shared else ""
    if count == 1:
        shared_sentence = f"Both roles ask for {named}."
    elif count > 1:
        second = f"{shared[1]['skill']} ({_percent(shared[1]['share_a'])} and {_percent(shared[1]['share_b'])})"
        shared_sentence = f"Both roles frequently ask for {named} and {second}."

    if not only_a and not only_b:
        return " ".join([
            f"{role_a} and {role_b} job postings ask for the same most requested skills.",
            shared_sentence,
            _takeaway(role_a, role_b, shared, [], []),
        ])

    sentences = []
    if count == 0:
        sentences.append("These two roles have no skills in common among the most requested for each.")
    else:
        clause = _overlap_clause(role_a, role_b, count, size_a, size_b)
        fraction = count / max(size_a, size_b)
        if fraction >= SOME_SHARED:
            overlap = "overlap quite a bit" if fraction >= MANY_SHARED else "have some skills in common"
            sentences.append(f"{role_a} and {role_b} job postings {overlap}: {clause}.")
        else:
            sentences.append(f"{role_a} and {role_b} job postings share few of their most requested skills: "
                             f"only {clause}.")
        sentences.append(shared_sentence)

    sentences.append(_unique_sentence(role_a, role_b, only_a, "share_a", count >= 2, size_b))
    sentences.append(_unique_sentence(role_b, role_a, only_b, "share_b", False, size_a))
    sentences.append(_takeaway(role_a, role_b, shared, only_a, only_b))
    return " ".join(sentences)