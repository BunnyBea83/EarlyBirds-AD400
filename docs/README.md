# Docs

Project documentation that belongs with the code lives here. Planning documents (PRD, sprint reviews, requirements, the Data Evaluation page) live in Confluence.

## What's here

| Path | What it is |
|---|---|
| `data/cleaning_report.md` | The latest cleaning results: row counts for every step, how missing values were handled, join results, known limitations, a data dictionary and a profile of the raw files. **Generated** by `python scripts/clean_data.py`. |
| `images/` | The Birdseye logo and other images used in the READMEs. |

## Generated files

`data/cleaning_report.md` is rewritten every time `scripts/clean_data.py` runs, so **don't edit it by hand**: changes would be lost on the next run. To change what it says:

- Column descriptions in the data dictionary: edit `COLUMN_DESCRIPTIONS` in `scripts/cleaning_functions.py`.
- How a missing value is handled, and the reason shown: edit `MISSING_VALUE_POLICY` in the same file.
- Anything else: change the cleaning code, then run `python scripts/clean_data.py` again.

Commit the updated report in the same PR as the code change, so the two always match.

## Adding documentation

Add notes here when they explain how the code works and should change along with it, such as a design decision or how a pipeline step works. Notes about planning or the client go in Confluence instead.
