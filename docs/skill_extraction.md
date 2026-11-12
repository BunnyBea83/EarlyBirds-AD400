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
