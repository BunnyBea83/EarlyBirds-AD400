"""Download the LinkedIn Job Postings (2023-2024) dataset from Kaggle into data/raw/.

Usage (from the repository root, with the virtual environment active):

    python scripts/download_data.py           # download if data/raw/ is empty
    python scripts/download_data.py --force   # download again and overwrite

The dataset is public, so a Kaggle login is usually not needed. If Kaggle asks
for one, see "If the download asks you to log in" in data/README.md.
"""

import argparse
import sys
from pathlib import Path

import kagglehub

DATASET = "arshkon/linkedin-job-postings"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--force",
        action="store_true",
        help="download again even if data/raw/ already has files",
    )
    args = parser.parse_args()

    if RAW_DIR.exists() and any(RAW_DIR.iterdir()) and not args.force:
        print(f"Data already present in {RAW_DIR}. Use --force to download again.")
        return 0

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {DATASET} into {RAW_DIR} ...")
    try:
        kagglehub.dataset_download(
            DATASET, output_dir=str(RAW_DIR), force_download=args.force
        )
    except Exception as err:  # network errors, login required, etc.
        print(f"Download failed: {err}", file=sys.stderr)
        print("See data/README.md for help.", file=sys.stderr)
        return 1

    files = sorted(p for p in RAW_DIR.rglob("*") if p.is_file())
    total_mb = sum(p.stat().st_size for p in files) / 1_000_000
    print(f"Done: {len(files)} files, {total_mb:.0f} MB")
    for p in files:
        print(f"  {p.relative_to(RAW_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
