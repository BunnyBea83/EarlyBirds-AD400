"""Compare a person's skills with a role's skill profile (TA4-50).

The profile is the role's stored top skills (up to 20) with the share of postings
that ask for each one (see birdseye.role_profiles). The match is a plain count:
how many of those top skills the person has.
"""

from collections.abc import Iterable


def match_skills(profile: Iterable[dict], have_skills: Iterable[str]) -> dict:
    """Split a role profile into skills the person has and skills they are missing.

    profile holds {"skill", "percentage"} items, as returned by
    role_profiles.load_role_profile. Returns:
      matched  how many profile skills the person has
      total    how many skills the profile has
      have     profile skills the person has, most requested first
      missing  profile skills the person lacks, most requested first
    Names are compared ignoring case. Skills the person has that are not in the
    profile are ignored. Picking "MS Excel" in the skill picker already gives the
    standard skill name ("Microsoft Excel"), so synonyms match too.
    """
    owned = {name.casefold() for name in have_skills}
    ranked = sorted(profile, key=lambda row: (-row["percentage"], row["skill"].casefold(), row["skill"]))
    have = [row for row in ranked if row["skill"].casefold() in owned]
    missing = [row for row in ranked if row["skill"].casefold() not in owned]
    return {"matched": len(have), "total": len(ranked), "have": have, "missing": missing}


def match_label(result: dict) -> str:
    """The match as plain text, e.g. "7 out of 20"."""
    return f"{result['matched']} out of {result['total']}"