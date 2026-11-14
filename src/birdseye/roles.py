"""Map cleaned job titles to a small, editable comparison taxonomy."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sqlite3
import sys

# Whole phrases describe the work performed. Review this taxonomy with the team
# before using it to publish results.
ROLE_RULES = {
    "Data Analyst": ("data analyst", "business intelligence analyst", "bi analyst"),
    "Data Scientist": ("data scientist",),
    "Data Engineer": ("data engineer", "analytics engineer"),
    "Software Engineer": ("software engineer", "software developer"),
    "Marketing Manager": ("marketing manager", "brand manager"),
    "Project Manager": ("project manager", "project lead"),
    "Registered Nurse": ("registered nurse", "rn"),
}
UNKNOWN = "Unknown"
NEEDS_REVIEW = "Needs review"
TITLE_WORDS = {
    "sr": "senior", "jr": "junior", "mgr": "manager", "eng": "engineer",
    "dev": "developer",
}


def normalize_title(title):
    words = re.findall(r"[^\W_]+", (title or "").casefold())
    return " ".join(TITLE_WORDS.get(word, word) for word in words)


def map_roles(postings, rules=ROLE_RULES):
    """Return structured mappings and a summary with up to five examples per issue."""
    phrases = [(role, f" {normalize_title(alias)} ")
               for role, aliases in rules.items() for alias in aliases]
    counts = Counter(dict.fromkeys(("mapped", "unmapped", "ambiguous"), 0))
    examples = defaultdict(list)
    mappings = []
    for posting in postings:
        title = posting["title"]
        normalized = normalize_title(title)
        padded = f" {normalized} "
        matches = {role for role, phrase in phrases if phrase in padded}
        if len(matches) == 1:
            role, outcome = next(iter(matches)), "mapped"
        elif matches:
            role, outcome = NEEDS_REVIEW, "ambiguous"
        else:
            role, outcome = UNKNOWN, "unmapped"
        counts[outcome] += 1
        if outcome != "mapped" and len(examples[outcome]) < 5:
            examples[outcome].append(title)
        mappings.append({"job_id": posting["job_id"], "title": title,
                         "normalized_title": normalized, "role": role})
    return mappings, {"counts": dict(counts), "examples": dict(examples)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="Cleaned Birdseye SQLite database")
    args = parser.parse_args()
    with sqlite3.connect(f"{args.database.resolve().as_uri()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        mappings, report = map_roles(conn.execute("SELECT job_id, title FROM postings ORDER BY job_id"))
    print(json.dumps(report), file=sys.stderr)
    print(json.dumps(mappings))


if __name__ == "__main__":
    main()
