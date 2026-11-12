"""Process cleaned postings in bounded chunks and persist extracted skills."""

import sqlite3
import logging
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from birdseye.skill_extraction import extract_skills
from birdseye.skill_management import load_skills
from birdseye.skill_storage import initialize_storage, save_posting_skills

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchResult:
    processed: int = 0
    matched_postings: int = 0
    skill_links: int = 0
    missing_descriptions: int = 0
    invalid_postings: int = 0


def process_postings(
    db_path: Path,
    *,
    batch_size: int = 1000,
    progress: Callable[[BatchResult], None] | None = None,
) -> BatchResult:
    """Replace matches for every posting, committing results together.

    Read descriptions in chunks rather than loading the dataset into memory.
    Missing descriptions are treated as empty text and counted. Progress is
    provisional until this function returns successfully. A failed run rolls
    back all match updates; catalog/schema initialization is separate.
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")
    # mode=rw prevents a typo or missing cleaned database from creating a file.
    uri = Path(db_path).resolve().as_uri() + "?mode=rw"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(postings)")}
        if not {"job_id", "description"}.issubset(columns):
            raise ValueError("Database requires postings with job_id and description; run clean_data.py first")
        initialize_storage(conn, allow_missing_job_ids=True)
        processed = matched = links = missing = invalid = 0
        with conn:
            # Begin explicitly so per-posting savepoints remain inside one
            # transaction, avoiding a disk commit for every job description.
            conn.execute("BEGIN IMMEDIATE")
            catalog = load_skills(conn)
            cursor = conn.execute("SELECT job_id, description FROM postings ORDER BY job_id")
            while rows := cursor.fetchmany(batch_size):
                for job_id, description in rows:
                    processed += 1
                    if not isinstance(job_id, int) or job_id <= 0:
                        invalid += 1
                        logger.warning("Skipping posting with invalid or missing job_id: %r", job_id)
                        continue
                    if description is None:
                        missing += 1
                        logger.warning("Posting %s has no description; clearing previous matches", job_id)
                        description = ""
                    elif not isinstance(description, str):
                        invalid += 1
                        logger.warning("Skipping posting %s with non-text description; clearing previous matches", job_id)
                        save_posting_skills(conn, job_id, [])
                        continue
                    skills = extract_skills(description, catalog=catalog)
                    save_posting_skills(conn, job_id, skills)
                    matched += bool(skills)
                    links += len(skills)
                if progress is not None:
                    progress(BatchResult(processed, matched, links, missing, invalid))
                logger.info("Processed %s postings; updates pending commit", processed)
        logger.info("Committed %s skill links; %s missing descriptions; %s invalid postings", links, missing, invalid)
        return BatchResult(processed, matched, links, missing, invalid)
