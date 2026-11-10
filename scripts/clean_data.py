"""Clean the LinkedIn Job Postings (2023-2024) dataset and save it to SQLite.

Usage (from the repository root, with the virtual environment active):

    python scripts/clean_data.py

This file only says WHAT happens and in what order. HOW each step works is in
scripts/cleaning_functions.py.

Writes:
    data/processed/birdseye.db        the cleaned postings (ignored by Git)
    docs/data/cleaning_report.md      step counts, missing values, data
                                      dictionary and limitations (committed)
"""

import sys

# The cleaning functions and settings, from scripts/cleaning_functions.py.
# Python looks in the running script's own folder first, so this file,
# sitting next to clean_data.py, is found without any setup.
from cleaning_functions import (
    load_raw,
    apply_step,
    remove_duplicate_ids,
    remove_missing_text,
    remove_repeated_postings,
    fill_missing_values,
    convert_dates,
    annualize_salaries,
    tidy_text,
    standardize_categories,
    standardize_locations,
    format_codes,
    join_companies,
    join_industries,
    save_to_sqlite,
    build_report,
    DB_PATH,
    REPORT_PATH,
    REPO_ROOT,
    TABLE_NAME,
)


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

    # Step 4: join. Each join keeps the row count the same.
    postings = apply_step(postings, steps, "Join company details", join_companies, frames["companies"])
    postings = apply_step(
        postings, steps, "Join industries",
        join_industries, frames["job_industries"], frames["industries"],
    )

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
