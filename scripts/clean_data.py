"""Clean the LinkedIn Job Postings (2023-2024) dataset and save it to SQLite (TA4-24).

Usage (from the repository root, with the virtual environment active):

    python scripts/clean_data.py

Steps, in order:

    Load the raw CSVs and profile them                   
    Clean: duplicates, empty postings, missing values 
    Standardize: dates, annual pay, text, locations
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
# Data Cleaning Formatting
# ==========================================================================

# ID columns in each file, converted to whole numbers right after loading.
ID_COLUMNS = {
    "postings": ["job_id", "company_id"],
    "companies": ["company_id"],
    "job_industries": ["job_id", "industry_id"],
    "industries": ["industry_id"],
}

# PRD data processing metric: keep at least 95% of records after cleaning.
KEEP_TARGET = 0.95

# what to do with missing values in each column.
# Each entry is: column -> (value to fill in, or None to leave empty, reason).
# The reasons are copied into the report, so every choice is documented.
SALARY_REASON = "Not every posting lists pay; filling it in would invent salaries."
MISSING_VALUE_POLICY = {
    "remote_allowed": (0, "Empty means the posting didn't mark remote work as allowed, so 0 (no)."),
    "formatted_experience_level": ("Not specified", "Kept as its own group so these postings still appear in charts."),
    "skills_desc": (None, "Optional field that most postings leave blank."),
    "min_salary": (None, SALARY_REASON),
    "med_salary": (None, SALARY_REASON),
    "max_salary": (None, SALARY_REASON),
    "pay_period": (None, SALARY_REASON),
    "currency": (None, SALARY_REASON),
    "compensation_type": (None, SALARY_REASON),
    "normalized_salary": (None, SALARY_REASON),
    "company_id": (None, "Postings without a company are counted in the join results."),
    "company_name": (None, "Postings without a company are counted in the join results."),
    "views": (None, "Unknown isn't the same as zero views."),
    "applies": (None, "Unknown isn't the same as zero applications."),
    "closed_time": (None, "Most postings were still open when the data was collected."),
    "expiry": (None, "No expiry date was recorded."),
    "application_url": (None, "Only present when applying happens outside LinkedIn."),
    "posting_domain": (None, "Only present when applying happens outside LinkedIn."),
    "zip_code": (None, "Location detail isn't always given."),
    "fips": (None, "Location detail isn't always given."),
}
# Used for any column not listed above.
DEFAULT_POLICY = (None, "No rule set yet, so left empty.")

# Raw timestamps stored as Unix milliseconds, converted to dates.
DATE_COLUMNS = ["listed_time", "original_listed_time", "expiry", "closed_time"]

# How many of each pay period make up a year.
# HOURLY assumes full time: 40 hours x 52 weeks = 2,080 hours.
PAY_PERIOD_FACTORS = {"HOURLY": 2080, "WEEKLY": 52, "BIWEEKLY": 26, "MONTHLY": 12, "YEARLY": 1}
SALARY_COLUMNS = ["min_salary", "med_salary", "max_salary"]

# Category columns whose values should use one spelling each.
CATEGORY_COLUMNS = ["formatted_work_type", "work_type", "formatted_experience_level"]

# Location codes stored as fixed-width text, so leading zeros survive
# (Boston's ZIP is 02134, not 2134). Column -> number of digits.
CODE_COLUMNS = {"zip_code": 5, "fips": 5}

# US states (plus DC), for writing every location as "City, ST".
# Keys are lowercase so "washington", "Washington" and "WASHINGTON" all match.
STATE_ABBREVIATIONS = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
# The set of valid two-letter codes, for checking values like "WA".
VALID_STATES = set(STATE_ABBREVIATIONS.values())


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
    The recorded counts become the step table in the report"""
    before = len(postings)
    postings = func(postings, *args)
    steps.append((label, before, len(postings)))
    return postings


def to_int_id(series):
    """Convert an ID column to whole numbers that allow gaps.

    pandas reads a number column with any empty cells as decimals (10.0),
    because its plain whole-number type can't hold "empty". "Int64" (capital I)
    is pandas' whole-number type that can, so 10.0 becomes 10 and empty stays
    empty. In the database these become INTEGER values (or NULL)."""
    return pd.to_numeric(series, errors="coerce").astype("Int64")


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

    # Make every ID a whole number (10, not 10.0), in every file that has it.
    for name, columns in ID_COLUMNS.items():
        for col in present(frames[name], columns):
            frames[name][col] = to_int_id(frames[name][col])

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
# Step 2: Clean
# ==========================================================================

def remove_duplicate_ids(postings):
    """Keep one row per job_id. keep="first" keeps the first copy and drops the rest."""

    return postings.drop_duplicates(subset="job_id", keep="first")


def remove_missing_text(postings):
    """Remove postings with no title or no description, including ones that
    contain only spaces."""

    # Start with "keep every row", then rule rows out column by column.
    keep = pd.Series(True, index=postings.index)
    for col in ["title", "description"]:
        # astype("string") treats every value as text; strip() removes spaces
        # from both ends; fillna("") turns empty cells into "" so one check
        # catches both empty cells and space-only text.
        text = postings[col].astype("string").str.strip().fillna("")
        keep &= text != ""  # &= means "keep AND this condition"
    return postings[keep]


def remove_repeated_postings(postings):
    """Remove the same job posted more than once under different job_ids:
    same company, title and description."""

    cols = present(postings, ["company_name", "title", "description", "location"])
    # Compare tidied copies so small differences don't hide a repeat:
    # \s+ turns any run of spaces or line breaks into one space, then strip()
    # trims the ends and lower() ignores capitalization. So "Data Analyst "
    # and "data  analyst" count as the same. The original text isn't changed.
    key = postings[cols].apply(
        lambda col: col.astype("string").str.replace(r"\s+", " ", regex=True).str.strip().str.lower()
    )
    # duplicated() marks every repeat after the first; ~ flips it to "keep".
    return postings[~key.duplicated(keep="first")]


def fill_missing_values(postings):
    """Fill empty cells where MISSING_VALUE_POLICY says to; leave the rest empty."""

    postings = postings.copy()  # work on a copy so the input isn't changed
    for col, (value, _reason) in MISSING_VALUE_POLICY.items():
        if value is not None and col in postings.columns:
            postings[col] = postings[col].fillna(value)
    return postings

# ==========================================================================
# Step 3: Standardize
# ==========================================================================

def convert_dates(postings):
    """Convert Unix-millisecond timestamps to dates written as YYYY-MM-DD."""

    postings = postings.copy()
    for col in present(postings, DATE_COLUMNS):
        # The raw values count milliseconds since 1 January 1970.
        # errors="coerce" turns anything unreadable into an empty value.
        dates = pd.to_datetime(postings[col], unit="ms", errors="coerce")
        # Store as "YYYY-MM-DD" text: the standard format SQLite understands
        # for dates (it has no separate date type), and it sorts correctly.
        postings[col] = dates.dt.strftime("%Y-%m-%d")
    return postings


def annualize_salaries(postings):
    """Add yearly versions of the salary columns, using pay_period.

    The originals are kept so the conversion can be checked. A posting whose
    pay_period is missing or unknown gets empty yearly values."""

    if "pay_period" not in postings.columns:
        return postings
    postings = postings.copy()
    # Look up each posting's multiplier, e.g. HOURLY -> 2080.
    # map() returns empty for any pay_period not in the dictionary.
    period = postings["pay_period"].astype("string").str.strip().str.upper()
    factor = period.map(PAY_PERIOD_FACTORS).astype("float")
    for col in present(postings, SALARY_COLUMNS):
        # to_numeric makes sure the column is numbers before multiplying.
        postings[f"annual_{col}"] = pd.to_numeric(postings[col], errors="coerce") * factor
    return postings


def fix_capitalization(title):
    """Title-case a job title only if it's ALL CAPS or all lowercase.

    "DATA ANALYST" -> "Data Analyst". Mixed-case titles are left alone, so
    acronyms like "SQL" in "SQL Developer" don't become "Sql"."""

    if title.isupper() or title.islower():
        return title.title()
    return title


def tidy_text(postings):
    """Trim titles and descriptions, and make title capitalization consistent."""

    postings = postings.copy()
    # \s+ matches any run of spaces, tabs or line breaks; replacing it with one
    # space turns "Data   Analyst" into "Data Analyst".
    titles = postings["title"].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    # na_action="ignore" skips empty values instead of passing them to the function.
    postings["title"] = titles.map(fix_capitalization, na_action="ignore")
    # Descriptions are only trimmed: their line breaks and capitalization are
    # kept, since later text analysis lowercases them itself.
    postings["description"] = postings["description"].astype("string").str.strip()
    return postings


def standardize_categories(postings):
    """Give each category one spelling, e.g. FULL_TIME and Full-time -> Full-Time."""

    postings = postings.copy()
    for col in present(postings, CATEGORY_COLUMNS):
        postings[col] = (
            postings[col]
            .astype("string")
            .str.strip()
            .str.replace("_", "-")  # FULL_TIME -> FULL-TIME
            .str.lower()            # FULL-TIME -> full-time
            .str.title()            # full-time -> Full-Time
        )
    return postings


def to_city_state(location):
    """Rewrite one location as "City, ST", or return None if that isn't possible.

    "Seattle, WA" and "Seattle, Washington" both become "Seattle, WA".
    Values like "United States" or "Greater Seattle Area" have no city and
    state, so they return None."""

    # Split on commas and trim each piece: "Seattle , WA" -> ["Seattle", "WA"].
    parts = [part.strip() for part in str(location).split(",")]
    if len(parts) < 2 or not parts[0]:
        return None
    city, state = parts[0], parts[1]

    if state.upper() in VALID_STATES:            # already a code, e.g. "wa"
        state = state.upper()
    elif state.lower() in STATE_ABBREVIATIONS:   # a full name, e.g. "Washington"
        state = STATE_ABBREVIATIONS[state.lower()]
    else:                                        # not a US state
        return None
    return f"{city}, {state}"


def format_codes(postings):
    """Store ZIP and FIPS codes as fixed-width text, e.g. 2134.0 -> "02134"."""

    postings = postings.copy()
    for col in present(postings, CODE_COLUMNS):
        postings[col] = (
            to_int_id(postings[col])      # 2134.0 -> 2134 (empty stays empty)
            .astype("string")             # 2134 -> "2134"
            .str.zfill(CODE_COLUMNS[col])  # "2134" -> "02134": pad with zeros on the left
        )
    return postings


def standardize_locations(postings):
    """Write every location as "City, ST", keeping the original in location_raw."""

    if "location" not in postings.columns:
        return postings
    postings = postings.copy()
    postings["location_raw"] = postings["location"]
    postings["location"] = postings["location"].map(to_city_state, na_action="ignore")
    return postings


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
    missing_before_fill,
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

    # Check the 95% target against the raw row count (the first step's count).
    raw_count = steps[0][1]
    kept = len(postings) / raw_count if raw_count else 0
    status = "met" if kept >= KEEP_TARGET else "NOT met"
    lines.append(
        f"Kept {len(postings):,} of {raw_count:,} raw postings ({kept:.1%}). "
        f"Target of at least {KEEP_TARGET:.0%}: {status}."
    )

    # Missing values: what was empty after cleaning, and what was done about it.
    lines += [
        "",
        "## Missing values",
        "",
        "Every column with empty values after cleaning, and how they were handled.",
        "",
        "| Column | Missing | Choice | Reason |",
        "|---|---:|---|---|",
    ]
    for col, count in missing_before_fill.items():
        if count == 0:
            continue
        value, reason = MISSING_VALUE_POLICY.get(col, DEFAULT_POLICY)
        choice = "Left empty" if value is None else f"Filled with `{value}`"
        lines.append(f"| `{col}` | {count:,} | {choice} | {reason} |")

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
    steps = [("Load raw postings", len(postings), len(postings))]

    # Step 2: clean. Empty postings are removed before looking for
    # repeats, so blank postings aren't counted as repeats of each other.
    postings = apply_step(postings, steps, "Remove duplicate job_ids", remove_duplicate_ids)
    postings = apply_step(postings, steps, "Remove postings with no title or description", remove_missing_text)
    postings = apply_step(postings, steps, "Remove repeated postings", remove_repeated_postings)
    # Count empty values now, before filling, so the report shows the real gaps.
    missing_before_fill = postings.isna().sum()
    postings = apply_step(postings, steps, "Fill or keep missing values", fill_missing_values)

# Step 3: standardize. None of these remove rows.
    postings = apply_step(postings, steps, "Convert timestamps to dates", convert_dates)
    postings = apply_step(postings, steps, "Add yearly salaries", annualize_salaries)
    postings = apply_step(postings, steps, "Trim text, fix title capitalization", tidy_text)
    postings = apply_step(postings, steps, "One spelling per work type and level", standardize_categories)
    postings = apply_step(postings, steps, "Locations as City, ST", standardize_locations)
    postings = apply_step(postings, steps, "ZIP and FIPS codes as 5-digit text", format_codes)

    # Step 5: save, then build the report.
    saved = save_to_sqlite(postings)
    report = build_report(
        steps,
        frames,
        postings,
        saved,
        missing_before_fill,
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
