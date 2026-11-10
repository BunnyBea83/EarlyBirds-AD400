"""Clean the LinkedIn Job Postings (2023-2024) dataset and save it to SQLite (TA4-24).

Usage (from the repository root, with the virtual environment active):

    python scripts/clean_data.py

Steps, in order:

    Load the raw CSVs and profile them                     TA4-39
    Save the result to data/processed/birdseye.db (SQLite)
    Write a report to docs/data/cleaning_report.md

The report holds only counts, column names and short examples, no full
records, so it is safe to commit. The database is ignored by Git.
"""

import sqlite3
import sys
from datetime import date
# pathlib's Path handles file paths the same way on Windows, macOS and Linux,
# so we never have to worry about "/" versus "\".
from pathlib import Path
import pandas as pd

# ==========================================================================
# Settings
# ==========================================================================

# __file__ is this script: <repo>/scripts/clean_data.py.
# .resolve() makes it a full path; .parent.parent goes up two levels to the
# repo root. Working paths out this way means the script runs correctly
# no matter which folder you start it from.
REPO_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = REPO_ROOT / "data" / "raw"  # filled by scripts/download_data.py
DB_PATH = REPO_ROOT / "data" / "processed" / "birdseye.db"  # ignored by Git
REPORT_PATH = REPO_ROOT / "docs" / "data" / "cleaning_report.md"  # committed

# Name of the database table the postings are saved to.
TABLE_NAME = "postings"

# If Kaggle's layout ever differs, this dictionary is the only thing to change.
RAW_FILES = {
    "postings": "postings.csv",
    "companies": "companies/companies.csv",
    # Postings link to industries through this file (job_id, industry_id)
    "job_industries": "jobs/job_industries.csv",
    # This one turns industry_id into a readable name.
    "industries": "mappings/industries.csv",
}

# Columns the script can't work without. Checked right after loading, so a
# missing column gives a clear message instead of a confusing error later.
REQUIRED_COLUMNS = ["job_id", "title", "description"]


# ==========================================================================
# Helpers
# ==========================================================================

def present(df, columns):
    """Return the columns from the list that the DataFrame actually has.

    Lets each step skip a column quietly if the dataset doesn't include it,
    instead of crashing."""
    return [col for col in columns if col in df.columns]


def apply_step(postings, steps, label, func, *args):
    """Run one step on the postings and record the row counts before and after.

    *args passes any extra inputs on to the step, such as the companies table.
    The recorded counts become the step table in the report (TA4-45)."""
    before = len(postings)
    postings = func(postings, *args)
    steps.append((label, before, len(postings)))
    return postings


# ==========================================================================
# Step 1: Load
# ==========================================================================

def load_raw(raw_dir=RAW_DIR):
    """Read every raw CSV into a DataFrame.

    Returns a dict like {"postings": DataFrame, "companies": DataFrame, ...}.
    """
    # Check every file exists first, so one error lists ALL missing files
    # instead of failing on the first one and hiding the rest.
    missing = [path for path in RAW_FILES.values() if not (raw_dir / path).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing in {raw_dir}: {missing}. "
            "Run `python scripts/download_data.py` first."
        )

    # Build {name: DataFrame} for every file in one line (a dict comprehension).
    # low_memory=False reads each file in one pass, so pandas picks one
    # consistent type per column instead of guessing chunk by chunk.
    frames = {
        name: pd.read_csv(raw_dir / path, low_memory=False)
        for name, path in RAW_FILES.items()
    }

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in frames["postings"].columns]
    if missing_cols:
        raise KeyError(f"postings.csv is missing required column(s): {missing_cols}")

    return frames


def profile(frames):
    """Describe each raw file as Markdown: row and column counts, then each
    column's type and how many values are missing. Returns a list of lines."""
    lines = ["## Raw files", ""]

    # Summary table: one row per file. ---: right-aligns the number columns.
    lines += ["| File | Rows | Columns |", "|---|---:|---:|"]
    for name, df in frames.items():
        # len(df) is the row count; df.shape[1] is the column count.
        # {:,} adds thousands separators, e.g. 123,849.
        lines.append(f"| `{RAW_FILES[name]}` | {len(df):,} | {df.shape[1]} |")

    # Detail table for each file: every column with its type and missing count.
    for name, df in frames.items():
        lines += ["", f"### `{RAW_FILES[name]}`", "", "| Column | Type | Missing |", "|---|---|---:|"]
        # isna() marks each empty cell True; sum() counts them per column.
        missing = df.isna().sum()
        for col in df.columns:
            # dtype is pandas' type for the column: int64 (whole numbers),
            # float64 (decimals, or whole numbers with gaps), str (text), etc.
            lines.append(f"| `{col}` | {df[col].dtype} | {missing[col]:,} |")

    return lines


# ==========================================================================
# Step 5: Save to SQLite
# ==========================================================================

def save_to_sqlite(postings, db_path=DB_PATH):
    """Write the postings to a SQLite database table.

    The table is replaced on every run, so the database always matches the
    latest cleaning code. Returns the row count read back from the database.
    """
    # Create data/processed/ if it doesn't exist yet.
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # sqlite3 is built into Python. connect() opens the database file,
    # creating it if needed. try/finally guarantees the connection is closed
    # even if something fails partway through.
    conn = sqlite3.connect(db_path)
    try:
        # pandas writes the whole DataFrame as a table in one call.
        # if_exists="replace" drops the old table first; index=False skips
        # pandas' row numbers, which would otherwise become an extra column.
        postings.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)

        # An index on job_id makes lookups by job_id fast for later stories.
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_job_id ON {TABLE_NAME}(job_id)")
        conn.commit()  # make the changes permanent

        # Read the count back with SQL, to confirm the data really landed.
        (row_count,) = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()
    finally:
        conn.close()

    return row_count


# ==========================================================================
# Report
# ==========================================================================

def build_report(
    steps,
    frames,
    postings,
    saved,
):
    """Combine everything into one Markdown report."""
    lines = [
        "# Cleaning report",
        "",
        f"Generated by `scripts/clean_data.py` on {date.today():%Y-%m-%d}. "
        "Run the script again to update it.",
        "",
        "## Steps",
        "",
        "| # | Step | Before | After | Removed |",
        "|---:|---|---:|---:|---:|",
    ]
    # enumerate(..., start=1) numbers the steps 1, 2, 3...
    for number, (name, before, after) in enumerate(steps, start=1):
        lines.append(f"| {number} | {name} | {before:,} | {after:,} | {before - after:,} |")
    lines += ["", f"Saved {saved:,} rows to the `{TABLE_NAME}` table in `data/processed/birdseye.db`."]

    lines += [""] + profile(frames)
    return "\n".join(lines) + "\n"


# ==========================================================================
# Run everything in order
# ==========================================================================

def main() -> int:
    # Step 1: load. If anything is missing, explain it and stop.
    # Exit code 1 means "something went wrong".
    try:
        frames = load_raw()
    except (FileNotFoundError, KeyError) as err:
        print(err, file=sys.stderr)  # stderr is the standard place for errors
        return 1

    postings = frames["postings"]
    # Each entry is (step name, rows before, rows after), for the report.
    steps = [("Load raw postings (TA4-39)", len(postings), len(postings))]

    # Step 5: save, then build the report.
    saved = save_to_sqlite(postings)
    report = build_report(
        steps,
        frames,
        postings,
        saved,
    )

    # Save the report. utf-8 keeps special characters readable on Windows.
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    # Print a short summary; the full details are in the report file.
    for number, (name, before, after) in enumerate(steps, start=1):
        print(f"{number:>2}. {name}: {before:,} -> {after:,}")
    print(f"\nDatabase: {DB_PATH.relative_to(REPO_ROOT)} (table `{TABLE_NAME}`, {saved:,} rows)")
    print(f"Report:   {REPORT_PATH.relative_to(REPO_ROOT)}")
    return 0  # exit code 0 means success


# This block runs only when the file is run as a script
# (python scripts/clean_data.py), not when another file imports it.
# sys.exit passes main()'s return value to the terminal as the exit code.
if __name__ == "__main__":
    sys.exit(main())
