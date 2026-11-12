# Skills schema — TA4-38

Use `birdseye.skill_storage.initialize_storage(conn)` on a fresh SQLite
connection to the cleaned database. It seeds 40 canonical skills, optional
categories, and 59 normalized names/aliases from `skills_catalog.py`.

- `skills`: unique integer ID, case-insensitive unique name, nullable category.
- `skill_aliases`: unique normalized alternate name linked to a skill ID.
- `posting_skills`: unique posting/skill pairs with enforced foreign keys.

Initialization preserves IDs and supports adding the category column to older
databases. The caller owns and closes the connection. SQL can retrieve, add, or
update catalog entries; use a reviewed application workflow when changing names
and aliases. Cleaning rebuilds clear derived links and restore the unique posting
index so the schema remains valid before extraction runs again.

Run `python -m pytest tests/test_skills_schema.py` for schema verification.
