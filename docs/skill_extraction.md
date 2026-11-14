# Skill extraction — TA4-40

```python
from birdseye.skill_extraction import extract_skills

extract_skills("Python and Postgres")  # ["Python", "PostgreSQL"]
```

The service matches explicit catalog names and aliases case-insensitively,
allows whitespace variations, and returns canonical names in catalog order.
Empty text produces an empty list; non-string input raises TypeError. Distinct
skills such as Java and JavaScript remain separate. Negation, proficiency, and
required/preferred classification are outside the matching contract.

Run `python -m pytest tests/test_skill_extraction.py` after installing the project.

## Backend processing — TA4-37

Build the cleaned SQLite database using `python scripts/clean_data.py`, then run:

```bash
python scripts/extract_skills.py --batch-size 1000
```

The default database is `data/processed/birdseye.db`, relative to the repository.
Use `--db PATH` for another existing cleaned database. Input must have a postings
table with `job_id` and `description` columns and unique non-null IDs among valid
records. An invalid schema or duplicate IDs is a source-level failure, reported
without pretending the batch succeeded. A missing file is not created.

The service reads descriptions in bounded chunks, validates each record, and
loads the stored catalog once per run, including reviewed additions and aliases.
Missing or invalid IDs are skipped with warnings. NULL descriptions clear previous
matches and increment the missing-description count. Non-text descriptions clear
previous matches, increment invalid-posting counts, and do not stop valid records.
Empty or unmatched text produces no links. Logs omit description contents.

Progress messages and INFO/WARNING logs report outcomes; the final summary reports
processed rows, matched postings, skill links, missing descriptions, and invalid
postings when present. CLI logs go to stderr. Library callers can configure
`logging` for a file or other destination.

All match writes commit together; a database error rolls them back, although
catalog initialization remains. Progress is provisional until success. Processing
holds a SQLite write lock; close editing tools and avoid concurrent cleaning.
Reruns replace matches without duplicates. Cleaning rebuilds clear derived links,
so run extraction again afterward.

Python callers can use `birdseye.skill_batch.process_postings`, which returns
`BatchResult` counts and accepts a progress callback. Tests use temporary databases:
`python -m pytest tests/test_skill_batch.py`.

## Functional verification — TA4-46

`python -m pytest tests/test_skill_workflow.py` runs temporary raw CSVs through
the actual cleaning orchestrator and invokes extraction as a separate process.
It verifies exact stored skill results, deduplication, no-match postings, foreign
keys, rebuilds, changed descriptions, catalog additions and consolidation, and
record warnings without aborting the batch. No production data or local cleaning
report is modified. Run the full suite using `python -m pytest`.
