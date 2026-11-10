# Data

Datasets are **not committed** to this repository. Instead, one command downloads them from Kaggle.

## Dataset

**LinkedIn Job Postings (2023–2024)** by Arsh Koneru and Zoey Yu Zou, on Kaggle: `arshkon/linkedin-job-postings`.

## Download it

From the repository root, with the virtual environment active:

```bash
python scripts/download_data.py
```

This puts the files in `data/raw/`. Running it again does nothing if the files are already there; add `--force` to download a fresh copy.

```
data/
├── README.md      (this file, tracked)
├── raw/           (downloaded Kaggle files, ignored by Git)
└── processed/     (cleaned outputs and the SQLite database, ignored by Git)
```

## If the download asks you to log in

The dataset is public, so a login usually isn't needed. If Kaggle asks for one:

1. Sign in at kaggle.com (free account), open **Settings**, and create an API token.
2. Set it as an environment variable before running the script:
   - macOS / Linux: `export KAGGLE_API_TOKEN=<your token>`
   - Windows (PowerShell): `$env:KAGGLE_API_TOKEN="<your token>"`
3. Run `python scripts/download_data.py` again.

Never commit your token. It belongs only in your own terminal or local `.env` file.

## Rules

- `data/raw/`, `data/processed/`, and data file types (`.csv`, `.db`, `.zip` and similar) are listed in `.gitignore`.
- Run `git status` before committing and make sure no data files appear.
- Cleaning steps are documented by TA4-24, not here.
