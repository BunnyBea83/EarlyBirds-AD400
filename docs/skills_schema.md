# Skills schema — TA4-38

Use `birdseye.skill_storage.initialize_storage(conn)` on a fresh SQLite
connection to the cleaned database. It seeds 40 canonical skills, optional
categories, and 59 normalized names/aliases from `skills_catalog.py`.

Running `download_data.py` and `clean_data.py` creates the cleaned `postings`
table. This PR provides schema initialization; cleaning alone does not create
the three skills tables. After cleaning, run this from the repository root:

```bash
python - <<'PY'
import sqlite3
from contextlib import closing
from pathlib import Path
from birdseye.skill_storage import initialize_storage

uri = Path("data/processed/birdseye.db").resolve().as_uri() + "?mode=rw"
with closing(sqlite3.connect(uri, uri=True)) as conn:
    initialize_storage(conn)
    for table in ("skills", "skill_aliases", "posting_skills"):
        print(table, conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
PY
```

On a fresh database, expect 40 skills, 59 aliases, and zero posting links.
The later batch extraction PR calls initialization and populates posting links.

- `skills`: unique integer ID, case-insensitive unique name, nullable category.
- `skill_aliases`: unique normalized alternate name linked to a skill ID.
- `posting_skills`: unique posting/skill pairs with enforced foreign keys.

Initialization preserves IDs and supports adding the category column to older
databases. The caller owns and closes the connection. SQL can retrieve, add, or
update catalog entries; use a reviewed application workflow when changing names
and aliases. Cleaning rebuilds clear derived links and restore the unique posting
index so the schema remains valid before extraction runs again.

Run `python -m pytest tests/test_skills_schema.py` for schema verification.

TA4-42 adds `save_posting_skills(conn, job_id, canonical_names)`. Initialize the
connection first. Saves replace only that posting's links atomically, deduplicate
input, reject unknown canonical names, and participate in an existing transaction.
An empty list clears matches. Each skill can still belong to many postings.
