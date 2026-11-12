"""Extract explicit catalog skill mentions without database side effects."""

import re
from functools import lru_cache

from birdseye.skills_catalog import SKILLS, Skill


def _term_pattern(term: str) -> str:
    # Escape punctuation literally while allowing spaces, tabs, or newlines
    # between the words of a multiword skill.
    return r"\s+".join(re.escape(word) for word in term.split())


# Compile once for reuse across thousands of descriptions. Unlike \b, these
# boundaries also work for terms ending in punctuation, such as C++ and C#.
# Include + and # in the boundary guard so C+++ and C#sharp do not match.
@lru_cache(maxsize=8)
def _matchers(catalog: tuple[Skill, ...]):
    return tuple(
        (
            skill.name,
            re.compile(
                r"(?<![\w+#])(?:"
                + "|".join(
                    _term_pattern(term)
                    for term in sorted((skill.name, *skill.aliases), key=len, reverse=True)
                )
                + r")(?![\w+#])",
                re.IGNORECASE,
            ),
        ),
        for skill in catalog
    )


def extract_skills(description: str, *, catalog: tuple[Skill, ...] = SKILLS) -> list[str]:
    """Return unique canonical skill names in catalog order.

    Matching is case-insensitive and recognizes explicit mentions, including
    aliases. It does not infer related skills or interpret negation. Empty or
    unmatched text returns an empty list; non-string input raises TypeError.
    """
    if not isinstance(description, str):
        raise TypeError("description must be a string")
    return [name for name, matcher in _matchers(catalog) if matcher.search(description)]
