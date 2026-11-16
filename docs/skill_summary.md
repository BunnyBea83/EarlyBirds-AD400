# Skill demand by role

After cleaning the postings and running TA4-25 skill extraction, use
`python -m birdseye.skill_summary data/processed/birdseye.db`. The reader uses
the extraction schema's `skills` and `posting_skills` tables and joins canonical
skills to cleaned postings by job ID. Edit categories in the upstream skill
catalog. Missing categories become Uncategorized.

Each result groups postings by role and includes the posting total, all ranked
skills, the first 15 skills, and category totals. Posting share counts distinct
postings with the skill or any skill in the category. The denominator includes
postings with no extracted skills. Category composition counts each distinct
skill–posting match in the category and divides by all matches in the role.
The first measure can sum to more than 100%. The second sums to 100% before
rounding. Unknown and ambiguous role counts are reported separately.

Use `python -m pytest tests/test_skill_summary.py` to verify the contract with
a synthetic in-memory database.
