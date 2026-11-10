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

Canonical repository: [`REPO URL`](https://github.com/BunnyBea83/EarlyBirds-AD400/tree/main)

## Prerequisites

- **Python 3.11** (supported runtime; see `.python-version`). Check with `python --version`.
- **Git**

All tools used in this project are free.

## Setup

1. Clone the repository and move into it:

   ```bash
   git clone https://github.com/BunnyBea83/EarlyBirds-AD400.git
   cd <REPO FOLDER>
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   ```

   - macOS / Linux: `source .venv/bin/activate`
   - Windows (PowerShell): `.venv\Scripts\Activate.ps1`
   - Windows (Command Prompt): `.venv\Scripts\activate.bat`

   Your prompt should now start with `(.venv)`.

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Download the dataset (one time, a few minutes):

   ```bash
   python scripts/download_data.py
   ```

   The files go into `data/raw/`. If Kaggle asks you to log in, see [`data/README.md`](data/README.md).

## Run the project check

From the repository root, with the virtual environment active:

```bash
pytest
```

A successful run ends with `2 passed`. This is a smoke check that confirms your environment is set up correctly; it does not test features yet.

## Project structure

```
├── src/birdseye/     Application source code
├── tests/            Automated tests (run with pytest)
├── docs/             Project documentation and images
├── scripts/          Command-line scripts (e.g. download_data.py)
├── data/             Local data (see data/README.md; never committed)
├── requirements.txt  Pinned Python dependencies
├── .python-version   Supported Python version
├── CHANGELOG.md      Record of changes per sprint
└── CONTRIBUTING.md   How to contribute
```

## Data

The dataset is not stored in this repository. `python scripts/download_data.py` downloads it from Kaggle into `data/raw/`. See [`data/README.md`](data/README.md) for details.

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
