# Standard job roles

Run `python -m birdseye.roles data/processed/birdseye.db > roles.json` after
building the cleaned database. JSON rows include the job ID, original title,
normalized title, and assigned role. Stderr reports mapping totals and up to five
examples per unresolved outcome.

Review the initial taxonomy with the team before publishing comparisons.

| Role | Typical work |
| --- | --- |
| Data Analyst | Reports and interprets business data |
| Data Scientist | Uses statistics and models to answer data questions |
| Data Engineer | Builds data pipelines and storage |
| Software Engineer | Builds and maintains software |
| Marketing Manager | Plans campaigns and brand strategy |
| Project Manager | Coordinates project scope, schedules, and delivery |
| Registered Nurse | Provides and coordinates clinical care |

Add whole-title phrases to `ROLE_RULES` in `src/birdseye/roles.py` and update its
tests. Rules match whole words regardless of seniority prefixes or level suffixes.
Titles matching multiple roles go to Needs review. Blank or unmatched titles go
to Unknown.
