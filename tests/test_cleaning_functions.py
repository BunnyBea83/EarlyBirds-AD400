"""Tests for the cleaning rules in scripts/cleaning_functions.py.

Each test builds a tiny table by hand, runs one function on it, and checks the
result, so they run in a second without the real dataset.
Run with: python -m pytest  (pytest.ini adds scripts/ to the import path)
"""

import pandas as pd

from cleaning_functions import (
    annualize_salaries,
    fix_capitalization,
    format_codes,
    join_industries,
    remove_duplicate_ids,
    remove_missing_text,
    remove_repeated_postings,
    standardize_categories,
    to_city_state,
    to_int_id,
)


# ---------------------------------------------------------------- Clean

def test_remove_duplicate_ids_keeps_first_copy():
    postings = pd.DataFrame({"job_id": [1, 1, 2], "title": ["First", "Copy", "Other"]})
    result = remove_duplicate_ids(postings)
    assert list(result["job_id"]) == [1, 2]
    assert list(result["title"]) == ["First", "Other"]


def test_remove_missing_text_drops_empty_and_space_only():
    postings = pd.DataFrame({
        "job_id": [1, 2, 3, 4],
        "title": ["Analyst", None, "Engineer", "Developer"],
        "description": ["Use SQL", "Use SQL", "   ", "Build apps"],
    })
    # 2 has no title; 3's description is only spaces.
    assert list(remove_missing_text(postings)["job_id"]) == [1, 4]


def test_remove_repeated_postings_ignores_case_and_spacing():
    postings = pd.DataFrame({
        "job_id": [1, 2, 3],
        "company_name": ["Acme", "acme", "Globex"],
        "title": ["Data Analyst", "data  analyst", "Data Analyst"],
        "description": ["Use SQL\nand Python", "use sql and python", "Use SQL and Python"],
    })
    # 2 repeats 1 apart from case and spacing; 3 is another company, so it stays.
    assert list(remove_repeated_postings(postings)["job_id"]) == [1, 3]


# ---------------------------------------------------------- Standardize

def test_to_city_state():
    assert to_city_state("Seattle, WA") == "Seattle, WA"
    assert to_city_state("Austin, Texas") == "Austin, TX"        # full state name
    assert to_city_state("Portland, or") == "Portland, OR"       # lowercase code
    assert to_city_state("New York, NY, United States") == "New York, NY"
    assert to_city_state("United States") is None                # no city
    assert to_city_state("Greater Seattle Area") is None         # metro area
    assert to_city_state("Toronto, Ontario") is None             # not a US state


def test_fix_capitalization_leaves_acronyms_alone():
    assert fix_capitalization("DATA ANALYST") == "Data Analyst"
    assert fix_capitalization("data analyst") == "Data Analyst"
    assert fix_capitalization("SQL Developer") == "SQL Developer"


def test_annualize_salaries():
    postings = pd.DataFrame({
        "min_salary": [40.0, 5000.0, 90000.0, 100.0],
        "pay_period": ["HOURLY", "monthly", "YEARLY", None],
    })
    result = annualize_salaries(postings)
    # 40 x 2,080 hours; 5,000 x 12 months; yearly unchanged; no pay period -> empty.
    assert list(result["annual_min_salary"][:3]) == [83200.0, 60000.0, 90000.0]
    assert pd.isna(result["annual_min_salary"].iloc[3])
    # The original column is kept for checking.
    assert list(result["min_salary"][:3]) == [40.0, 5000.0, 90000.0]


def test_standardize_categories_one_spelling():
    postings = pd.DataFrame({"work_type": ["FULL_TIME", "Full-time", " full-time "]})
    assert list(standardize_categories(postings)["work_type"]) == ["Full-Time"] * 3


def test_format_codes_keeps_leading_zeros():
    postings = pd.DataFrame({"zip_code": [2134.0, 98101.0, None]})
    result = format_codes(postings)
    assert list(result["zip_code"][:2]) == ["02134", "98101"]
    assert pd.isna(result["zip_code"].iloc[2])


def test_to_int_id_turns_decimals_into_whole_numbers():
    result = to_int_id(pd.Series([10.0, None, 20.0]))
    assert str(result.dtype) == "Int64"
    assert list(result.dropna()) == [10, 20]


# ----------------------------------------------------------------- Join

def test_join_industries_keeps_one_row_per_posting():
    postings = pd.DataFrame({"job_id": [1, 2, 3]})
    job_industries = pd.DataFrame({"job_id": [1, 1, 2], "industry_id": [4, 6, 6]})
    industries = pd.DataFrame({"industry_id": [4, 6], "industry_name": ["Software", "Finance"]})

    result = join_industries(postings, job_industries, industries)

    # Posting 1 is in two industries but still one row; 3 has none.
    assert len(result) == 3
    first = result.iloc[0]
    assert first["industry"] == "Software"
    assert first["industries"] == "Software; Finance"
    assert pd.isna(result.iloc[2]["industry"])
