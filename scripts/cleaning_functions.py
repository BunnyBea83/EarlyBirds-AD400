"""Functions for cleaning the LinkedIn Job Postings (2023-2024) dataset.

scripts/clean_data.py imports these and calls them in order. Grouped by stage:

    Settings        paths, file names and the rules each step follows
    Helpers         small tools every step uses
    Load            read the raw CSVs and describe them
    Clean           remove duplicates and empty postings, handle missing values
    Standardize     consistent dates, pay, text, categories, locations and codes
    Join            add company and industry details to each posting
    Save            write the result to the SQLite database
    Report          build the cleaning report, data dictionary and limitations

Tests import them too (tests/test_cleaning_functions.py); pytest.ini adds
scripts/ to the import path so they can find this file.
"""

import sqlite3
from datetime import date
# pathlib's Path handles file paths the same way on Windows, macOS and Linux,
# so we never have to worry about "/" versus "\".
from pathlib import Path
import pandas as pd

# ==========================================================================
# Settings
# ==========================================================================

# __file__ is this file: <repo>/scripts/cleaning_functions.py.
# .resolve() makes it a full path; .parent.parent goes up two levels to the
# repo root. Working paths out this way means the code runs correctly no
# matter which folder you start it from.
REPO_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = REPO_ROOT / "data" / "raw"  # filled by scripts/download_data.py
DB_PATH = REPO_ROOT / "data" / "processed" / "birdseye.db"  # ignored by Git
REPORT_PATH = REPO_ROOT / "docs" / "data" / "cleaning_report.md"  # committed

# Name of the database table the postings are saved to.
TABLE_NAME = "postings"

# The raw files this script needs. Keys are short names used in code; values are
# paths inside data/raw/, matching the Kaggle download's folders. If Kaggle's
# layout ever differs, this dictionary is the only thing to change.
RAW_FILES = {
    "postings": "postings.csv",
    "companies": "companies/companies.csv",
    # Postings link to industries through this file (job_id, industry_id)...
    "job_industries": "jobs/job_industries.csv",
    # ...and this one turns industry_id into a readable name.
    "industries": "mappings/industries.csv",
}

# Columns the script can't work without. Checked right after loading, so a
# missing column gives a clear message instead of a confusing error later.
REQUIRED_COLUMNS = ["job_id", "title", "description"]

# ID columns in each file, converted to whole numbers right after loading.
ID_COLUMNS = {
    "postings": ["job_id", "company_id"],
    "companies": ["company_id"],
    "job_industries": ["job_id", "industry_id"],
    "industries": ["industry_id"],
}

# PRD data processing metric: keep at least 95% of records after cleaning.
KEEP_TARGET = 0.95

# What to do with missing values in each column.
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

# Company columns to add to each posting, and their new names.
# The "company_" prefix keeps them apart from the posting's own columns.
COMPANY_COLUMNS = {
    "company_size": "company_size",
    "city": "company_city",
    "state": "company_state",
    "country": "company_country",
}

# A plain-language description of each column, for the data dictionary.
# Any column missing from this list shows "Not yet described" in the report.
COLUMN_DESCRIPTIONS = {
    "job_id": "LinkedIn's ID for the posting; one row per job_id.",
    "company_name": "Company name as shown on the posting.",
    "title": "Job title, trimmed; all-caps or all-lowercase titles re-capitalized.",
    "description": "Full job description text, trimmed.",
    "max_salary": "Highest pay listed, in the posting's own pay period.",
    "med_salary": "Single pay figure listed, in the posting's own pay period.",
    "min_salary": "Lowest pay listed, in the posting's own pay period.",
    "pay_period": "Pay period of the salary columns (HOURLY, YEARLY, etc.).",
    "annual_min_salary": "min_salary converted to a yearly amount.",
    "annual_med_salary": "med_salary converted to a yearly amount.",
    "annual_max_salary": "max_salary converted to a yearly amount.",
    "normalized_salary": "The dataset's own yearly salary estimate.",
    "currency": "Currency of the salary figures.",
    "compensation_type": "Type of pay listed, such as base salary.",
    "location": "Job location as 'City, ST'; empty when it couldn't be read that way.",
    "location_raw": "Job location exactly as written in the original posting.",
    "zip_code": "5-digit ZIP code of the job location, stored as text to keep leading zeros.",
    "fips": "5-digit county FIPS code of the job location, stored as text to keep leading zeros.",
    "company_id": "ID linking the posting to its company.",
    "company_size": "Company size group from the companies file.",
    "company_city": "City of the company's listed address.",
    "company_state": "State of the company's listed address.",
    "company_country": "Country of the company's listed address.",
    "industry": "First industry listed for the posting.",
    "industries": "All industries listed for the posting, separated by '; '.",
    "views": "Number of times the posting was viewed.",
    "applies": "Number of applications submitted.",
    "listed_time": "Date the posting was listed (YYYY-MM-DD).",
    "original_listed_time": "Date the posting was first listed (YYYY-MM-DD).",
    "expiry": "Date the posting expires (YYYY-MM-DD).",
    "closed_time": "Date the posting closed (YYYY-MM-DD), if it did.",
    "remote_allowed": "1 if remote work is allowed, otherwise 0.",
    "formatted_work_type": "Work type, such as Full-Time or Contract.",
    "work_type": "Work type code, in the same spelling as formatted_work_type.",
    "formatted_experience_level": "Experience level, such as Entry Level; 'Not Specified' if missing.",
    "skills_desc": "Skills text added by the employer, when given.",
    "job_posting_url": "Link to the posting on LinkedIn.",
    "application_url": "Link to apply outside LinkedIn, when given.",
    "application_type": "How applications are submitted.",
    "posting_domain": "Website where applications are submitted outside LinkedIn.",
    "sponsored": "1 if the posting was promoted, otherwise 0.",
}


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
    The recorded counts become the step table in the report."""
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
# Step 4: Join
# ==========================================================================

def join_companies(postings, companies):
    """Add company details to each posting, matching on company_id."""
    if "company_id" not in postings.columns:
        return postings
    # Keep only the company columns we want, and rename them.
    details = companies[["company_id"] + present(companies, COMPANY_COLUMNS)].copy()
    details["company_id"] = to_int_id(details["company_id"])
    # One row per company, so no posting can match twice.
    details = details.dropna(subset=["company_id"]).drop_duplicates("company_id")
    details = details.rename(columns=COMPANY_COLUMNS)

    postings = postings.copy()
    postings["company_id"] = to_int_id(postings["company_id"])
    # how="left" keeps every posting, even ones with no matching company.
    # validate="many_to_one" means many postings can share a company but each
    # company appears once; pandas raises an error if that's ever not true,
    # which guarantees the join can't duplicate postings.
    return postings.merge(details, on="company_id", how="left", validate="many_to_one")


def join_industries(postings, job_industries, industries):
    """Add industry names to each posting, keeping one row per posting.

    A posting can belong to several industries. Joining them directly would
    repeat the posting once per industry, so instead "industry" holds the
    first one listed and "industries" lists all of them."""
    # Link each job_id to its industry names.
    links = job_industries[["job_id", "industry_id"]].copy()
    links["job_id"] = to_int_id(links["job_id"])
    links["industry_id"] = to_int_id(links["industry_id"])

    names = industries[["industry_id", "industry_name"]].copy()
    names["industry_id"] = to_int_id(names["industry_id"])
    names = names.drop_duplicates("industry_id")

    links = links.merge(names, on="industry_id", how="left").dropna(subset=["industry_name"])

    # Combine each job's industries into one row.
    # dict.fromkeys removes repeated names while keeping their original order.
    per_job = (
        links.groupby("job_id")["industry_name"]
        .agg(industry="first", industries=lambda names: "; ".join(dict.fromkeys(names)))
        .reset_index()
    )

    postings = postings.copy()
    postings["job_id"] = to_int_id(postings["job_id"])
    # validate="one_to_one": each posting matches at most one combined row.
    return postings.merge(per_job, on="job_id", how="left", validate="one_to_one")


def join_stats(postings, companies):
    """Share of postings with no matching company, and with no industry."""
    company_ids = to_int_id(companies["company_id"])
    # isin() checks each posting's company_id against the companies file;
    # empty IDs count as unmatched. mean() of True/False gives the share.
    no_company = (~postings["company_id"].isin(company_ids)).mean()
    no_industry = postings["industry"].isna().mean()
    return no_company, no_industry


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
        # A rebuild can change descriptions even when job IDs stay the same.
        # Clear derived matches before replacing postings; retain the catalog.
        has_skills = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='posting_skills'"
        ).fetchone()
        if has_skills:
            conn.execute("DELETE FROM posting_skills")
            conn.commit()
        # pandas writes the whole DataFrame as a table in one call.
        # if_exists="replace" drops the old table first; index=False skips
        # pandas' row numbers, which would otherwise become an extra column.
        postings.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)

        # An index on job_id makes lookups by job_id fast for later stories.
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_job_id ON {TABLE_NAME}(job_id)")
        if has_skills:
            # to_sql(replace) also drops the unique index that makes job_id
            # a valid parent key for posting_skills. Restore it immediately.
            conn.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS uq_postings_job_id ON {TABLE_NAME}(job_id)"
            )
        conn.commit()  # make the changes permanent

        # Read the count back with SQL, to confirm the data really landed.
        (row_count,) = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()
    finally:
        conn.close()

    return row_count


# ==========================================================================
# Documentation helpers
# ==========================================================================

def short_text(value, limit=40):
    """Shorten a value for the data dictionary's Example column."""
    text = " ".join(str(value).split())  # turn line breaks and runs of spaces into single spaces
    text = text.replace("|", "\\|")       # a raw | would break the Markdown table
    return text if len(text) <= limit else text[: limit - 1] + "…"


def data_dictionary(postings):
    """Describe every column in the cleaned table: type, meaning and an example."""
    lines = [
        "## Data dictionary",
        "",
        f"Columns in the `{TABLE_NAME}` table. Dates are stored as YYYY-MM-DD text.",
        "",
        "| Column | Type | Description | Example |",
        "|---|---|---|---|",
    ]
    for col in postings.columns:
        values = postings[col].dropna()
        example = short_text(values.iloc[0]) if len(values) else ""
        description = COLUMN_DESCRIPTIONS.get(col, "Not yet described")
        lines.append(f"| `{col}` | {postings[col].dtype} | {description} | {example} |")
    return lines


def limitations(postings):
    """List known limitations of the cleaned data, with figures from this run."""
    notes = []

    annual = present(postings, ["annual_min_salary", "annual_med_salary", "annual_max_salary"])
    if annual:
        # any(axis=1) is True for a row with at least one yearly salary.
        share = postings[annual].notna().any(axis=1).mean()
        notes.append(f"Only {share:.1%} of postings list a salary, so pay figures describe a subset of jobs.")

    if "currency" in postings.columns:
        currencies = sorted(postings["currency"].dropna().astype(str).unique())
        notes.append(
            f"Salaries stay in their original currency ({', '.join(currencies) or 'none listed'}); "
            "they weren't converted."
        )

    if "listed_time" in postings.columns:
        dates = postings["listed_time"].dropna()
        if len(dates):
            # YYYY-MM-DD text sorts in date order, so min and max work directly.
            notes.append(
                f"Postings were listed between {dates.min()} and {dates.max()}, "
                "so the data is a snapshot of that period, not a long-term trend."
            )

    if "location" in postings.columns:
        share = postings["location"].isna().mean()
        notes.append(
            f"{share:.1%} of locations couldn't be written as `City, ST` (for example "
            "\"United States\" or a metro area); the original text is kept in `location_raw`."
        )

    notes.append(
        "Job titles are only re-capitalized when written in all caps or all lowercase, "
        "so some inconsistency remains."
    )

    return ["## Known limitations", ""] + [f"- {note}" for note in notes]


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

    # Join results: how many postings found no match.
    no_company, no_industry = join_stats(postings, frames["companies"])
    lines += [
        "",
        "## Join results",
        "",
        f"- Postings with no matching company: {no_company:.1%}",
        f"- Postings with no industry: {no_industry:.1%}",
    ]

    lines += [""] + limitations(postings)
    lines += [""] + data_dictionary(postings)

    lines += [""] + profile(frames)
    return "\n".join(lines) + "\n"
