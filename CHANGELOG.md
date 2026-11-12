# Changelog

All notable changes to Birdseye are recorded in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/). Each sprint ends with a release.

<!--
HOW TO ADD AN ENTRY (every PR that changes behavior, data or setup)

1. Add one line under the right heading in [Unreleased] below.
2. Start with the Jira key, then say what changed for the reader, not how you coded it.
   Good: - TA4-54: Top skills summary can be filtered by role.
   Avoid: - Refactored filter function in summary.py.
3. Add the PR number at the end, like (#12).
4. Only use the headings you need; leave the others empty.

Headings:
  Added       new features or charts
  Changed     changes to existing behavior
  Fixed       bug fixes
  Removed     features taken out
  Data        dataset, cleaning or skill extraction changes
  Infrastructure  repo, tooling, environment or CI changes

Skip the changelog for typo fixes, formatting or comment-only PRs.
-->

## [Unreleased]

### Added
- TA4-66: Show the top requested skills by role as horizontal bars. (#11)
- TA4-65: Report ranked skills and category totals by role. (#10)
- TA4-64: Map job titles to standard roles for skill comparisons. (#9)
- TA4-45: Cleaning report with step-by-step row counts, missing-value choices, known limitations and a data dictionary (`docs/data/cleaning_report.md`). (#2)

### Changed

### Fixed

### Removed

### Data
- TA4-39: Raw postings, company and industry files load into a SQLite database (`data/processed/birdseye.db`) with `python scripts/clean_data.py`. (#2)
- TA4-47: Duplicate job IDs, postings with no title or description, and repeated postings (same company, title, description and location) are removed. (#2)
- TA4-43: Dates are YYYY-MM-DD, salaries have yearly versions, work types and experience levels use one spelling, locations read "City, ST", and ZIP and FIPS codes keep leading zeros. (#2)
- TA4-49: Each posting includes its company details and industries, with no postings duplicated. (#2)

### Infrastructure
- TA4-74: Repository set up with README, contribution guide, changelog, pinned dependencies and a smoke test. (#1)
- TA4-74: One-command dataset download with `python scripts/download_data.py`. (#1)
- TA4-74: The `birdseye` package can be imported anywhere after `pip install -r requirements.txt`. (#1)
- TA4-24: Tests for the cleaning rules; README and data README explain building and viewing the database. (#2)

<!--
AT SPRINT END (PM)

1. Copy the [Unreleased] section below this comment.
2. Rename it to: ## [0.X.0] - Sprint name - YYYY-MM-DD
3. Delete any empty headings in the copied section.
4. Leave a fresh, empty [Unreleased] section at the top.
-->

<!--
EXAMPLE OF A FINISHED RELEASE (delete once you have a real one)

## [0.1.0] - Soar 1 - 2026-11-19

### Added
- TA4-54: Top 15 skills summary, filterable by role. (#8)
- TA4-15: Bar chart of the top 15 skills for two roles. (#10)

### Data
- TA4-24: Cleaned LinkedIn 2023-2024 dataset; duplicates and empty postings removed. (#4)

### Infrastructure
- TA4-74: Repository, README and contribution guide set up. (#1)
-->
