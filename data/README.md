# Data

Datasets are **not committed** to this repository. One command downloads the raw data from Kaggle, and another builds the cleaned database from it.

## Dataset

**LinkedIn Job Postings (2023–2024)** by Arsh Koneru and Zoey Yu Zou, on Kaggle: [`arshkon/linkedin-job-postings`](https://www.kaggle.com/datasets/arshkon/linkedin-job-postings). Licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## Folder layout

```
data/
├── README.md              (this file, tracked)
├── raw/                   downloaded Kaggle files (ignored by Git)
└── processed/
    └── birdseye.db        cleaned database (ignored by Git)
```

## 1. Download the raw data

From the repository root, with the virtual environment active:

```bash
python scripts/download_data.py
```

This puts the Kaggle files in `data/raw/`. Running it again does nothing if the files are already there; add `--force` to download a fresh copy.

The cleaning uses four of the downloaded files; the rest are kept for later features:

| File | Used for |
|---|---|
| `postings.csv` | The job postings themselves |
| `companies/companies.csv` | Company details added to each posting |
| `jobs/job_industries.csv` | Which industries each posting belongs to |
| `mappings/industries.csv` | Industry names |

### If the download asks you to log in

The dataset is public, so a login usually isn't needed. If Kaggle asks for one:

1. Sign in at kaggle.com (free account), open **Settings**, and create an API token.
2. Set it as an environment variable before running the script:
   - macOS / Linux: `export KAGGLE_API_TOKEN=<your token>`
   - Windows (PowerShell): `$env:KAGGLE_API_TOKEN="<your token>"`
3. Run `python scripts/download_data.py` again.

Never commit your token. It belongs only in your own terminal or local `.env` file.

## 2. Build the database

```bash
python scripts/clean_data.py
```

This cleans the raw files and saves the result to `data/processed/birdseye.db`. The database is rebuilt from scratch every run, so it always matches the latest cleaning code.

## What's in the database

One table, **`postings`**: one row per cleaned job posting, with company and industry details joined in. Duplicates and empty postings are removed, dates are `YYYY-MM-DD`, and salaries have yearly versions alongside the originals.

Every column, its type and meaning are listed in the **Data dictionary** section of [`docs/data/cleaning_report.md`](../docs/data/cleaning_report.md). The same report shows how many rows each cleaning step removed and how missing values were handled.

To browse it, use the VS Code SQLite extension's SQLITE EXPLORER or [DB Browser for SQLite](https://sqlitebrowser.org/) (both free; steps in the main [`README.md`](../README.md#looking-at-the-database)). Close it before running `clean_data.py` again, or Windows may lock the file.

## Rules

- `data/raw/`, `data/processed/`, and data file types (`.csv`, `.db`, `.zip` and similar) are listed in `.gitignore`.
- Run `git status` before committing and make sure no data files appear.
- Changes to the cleaning go in `scripts/cleaning_functions.py`; run `clean_data.py` afterwards and commit the updated `docs/data/cleaning_report.md` with your change.