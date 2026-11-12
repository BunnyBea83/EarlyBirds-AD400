# Reviewed equivalent skills — TA4-44

Use an initialized SQLite connection with `birdseye.skill_management`:

```python
from birdseye.skill_management import add_skill, update_skill, load_skills, consolidate_skills
from birdseye.skill_extraction import extract_skills

skill_id = add_skill(conn, "Technical Writing", aliases=("Documentation Writing",), category="Professional")
update_skill(conn, skill_id, name="Technical Writing", category="Communication")
results = extract_skills("documentation writing", catalog=load_skills(conn))
```

`add_skill` normalizes case and whitespace when resolving existing canonical
names or aliases. Reviewed new vocabulary is added when no equivalent exists.
Conflicting alias ownership raises an error; related skills such as Java and
JavaScript are kept separate. Unknown words in job descriptions are not
automatically invented as skills. Users can propose a term through `add_skill`.

For records reviewed as equivalent, call
`consolidate_skills(conn, source_id, target_id, confirmed=True)`. All source
posting links and aliases move to the target without duplicates. The target ID
and category survive; the source row is removed. Omit confirmation and no merge
occurs. No uncertain fuzzy similarity automatically changes the catalog.

Renaming preserves the ID, old name as an alias, and posting associations.
Initialization will not resurrect renamed or merged starter entries. Changes
are atomic and participate in a caller-owned transaction when one is active.
The caller owns and closes the connection. Reload the catalog after changes.

`extract_skills` without a catalog still uses the starter vocabulary. Database
workflows must pass `catalog=load_skills(conn)` to reflect stored changes.

Run `python -m pytest tests/test_skill_management.py` to verify these behaviors.
