<p align="center">
  <img src="docs/images/birdseye-logo.png" alt="Birdseye logo: a bird perched at the top of a rising line chart in front of a striped rising sun" width="360">
</p>

<h1 align="center">Birdseye</h1>

<p align="center"><em>A bird's-eye view of the job market.</em></p>

Birdseye helps job seekers catch hiring trends early. Using public job posting data and Python-based text analysis, it shows which skills employers ask for most and presents the findings in clear visuals for non-technical users. Birdseye is built by the Early Birds team for CareerPath Solutions.

## MVP features

- **Lookout:** analyzes job descriptions to find the skills employers ask for most.
- **Flight Paths:** compares two roles side by side to show which skills they share and which are unique to each.
- **Birdseye View:** presents the findings in clear charts designed for non-technical users.

## Repository

Canonical repository: [BunnyBea83/EarlyBirds-AD400](https://github.com/BunnyBea83/EarlyBirds-AD400)

## Prerequisites

- **Python 3.11** (supported runtime; see `.python-version`)
- **Git**

All tools used in this project are free.

## Setup

1. Clone the repository and move into it:

   ```bash
   git clone https://github.com/BunnyBea83/EarlyBirds-AD400.git
   cd EarlyBirds-AD400
   ```

2. Create a virtual environment **with Python 3.11**. Name the version explicitly, since plain `python` may point to a different version (for example Anaconda's):

   - Windows: `py -3.11 -m venv .venv`
   - macOS / Linux: `python3.11 -m venv .venv`

   If you use Anaconda and your prompt shows `(base)`, run `conda deactivate` first.

3. Activate it. Do this every time you open a new terminal:

   - Windows (PowerShell): `.venv\Scripts\Activate.ps1`
   - Windows (Command Prompt): `.venv\Scripts\activate.bat`
   - macOS / Linux: `source .venv/bin/activate`

   Your prompt should now start with `(.venv)`, and `python --version` should say 3.11.

4. Install dependencies **from the repository root** (the folder with this README). This also installs the project's own `birdseye` package:

   ```bash
   pip install -r requirements.txt
   ```

   Check that it worked: `python -c "import birdseye; print(birdseye.__version__)"` should print `0.1.0`.

5. Download the dataset (one time, a few minutes):

   ```bash
   python scripts/download_data.py
   ```

   The files go into `data/raw/`. If Kaggle asks you to log in, see [`data/README.md`](data/README.md).

## Build the database

Clean the raw data and save it to a SQLite database:

```bash
python scripts/clean_data.py
```

It prints each cleaning step with its row counts, and creates:

- **`data/processed/birdseye.db`**: the cleaned postings in a table named `postings`. Not committed; everyone builds their own copy with this command.
- **`docs/data/cleaning_report.md`**: row counts for every step, how missing values were handled, join results, known limitations, a data dictionary and a profile of the raw files. Committed, so the team can see the latest results.

### Looking at the database

**Two free options:**

1) In VS Code, with the SQLite extension (alexcvzz):
* press Ctrl+Shift+P and run SQLite: Open Database
* pick data/processed/birdseye.db. The SQLITE EXPLORER panel appears at the bottom of the Explorer sidebar, listing the postings table and its columns.
* To query it, run SQLite: New Query
   * type a query
   * then right-click → Run Query (or Ctrl+Shift+Q).
   * Select only the columns you need; the full description column makes results slow and hard to read.
2) [DB Browser for SQLite](https://sqlitebrowser.org/dl/):
* open birdseye.db to scroll the table like a spreadsheet,
* or run SQL in its Execute SQL tab. Better for browsing all the rows.

**A quick check that the cleaning worked (both numbers should match):**
sql
```SELECT COUNT(*), COUNT(DISTINCT job_id) FROM postings;```

Close the database in either tool before running clean_data.py again, or Windows may lock the file.

The cleaning steps are in scripts/clean_data.py; how each one works is in scripts/cleaning_functions.py.

## Run the tests

From the repository root, with the virtual environment active:

```bash
python -m pytest
```

A successful run ends with `12 passed`: two smoke checks for the environment and ten tests for the cleaning rules. Running it as `python -m pytest`, rather than plain `pytest`, guarantees it uses the environment's Python.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python --version` shows something other than 3.11 | The environment isn't active, or was made with another version. Activate it (step 3); if it's still wrong, delete `.venv` and recreate it with step 2. |
| `ModuleNotFoundError: No module named 'pandas'` (or another package) | Packages aren't installed in the active environment. Run step 4. |
| `ModuleNotFoundError: No module named 'birdseye'` | Run step 4 from the repository root. `src/birdseye/__init__.py` is imported, not run directly. |
| `ModuleNotFoundError: No module named 'cleaning_functions'` in tests | `pytest.ini` must say `pythonpath = scripts`. |
| Warnings mentioning `anaconda3` when running tests | Anaconda's Python is being used instead of the environment's. Run `conda deactivate`, activate the environment, and use `python -m pytest`. |
| PowerShell says running scripts is disabled | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again. |
| "Permission denied" deleting `.venv` | Something still uses it. Run `deactivate`, close VS Code and other terminals, then try again. |
| `database is locked` when running `clean_data.py` | Close DB Browser (or any other program with `birdseye.db` open) and run it again. |

## Project structure

```
├── src/birdseye/                Application package
├── scripts/
│   ├── download_data.py         Download the dataset from Kaggle
│   ├── clean_data.py            Run the cleaning steps in order
│   └── cleaning_functions.py    How each cleaning step works
├── tests/                       Automated tests (run with python -m pytest)
├── docs/
│   ├── data/cleaning_report.md  Latest cleaning results (generated)
│   └── images/                  Logo and other images
├── data/                        Local data (see data/README.md; never committed)
│   ├── raw/                     Downloaded Kaggle files
│   └── processed/birdseye.db    Cleaned database (generated)
├── requirements.txt             Pinned Python dependencies (also installs src/birdseye)
├── pyproject.toml               Makes src/birdseye importable as `import birdseye`
├── pytest.ini                   Test settings
├── .python-version              Supported Python version
├── CHANGELOG.md                 Record of changes per sprint
└── CONTRIBUTING.md              How to contribute
```

## Data

The dataset is not stored in this repository. `python scripts/download_data.py` downloads it from Kaggle into `data/raw/`, and `python scripts/clean_data.py` builds the database from it. See [`data/README.md`](data/README.md) for details.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for branch naming, Jira references, and the pull request process.

## Stack

- **Language:** Python 3.11
- **Database:** SQLite (built into Python)
- **Data download:** kagglehub
- **Data handling:** pandas
- **Dashboard:** Streamlit
- **Charts:** Plotly
- **Tests:** pytest

Exact versions are pinned in `requirements.txt`.