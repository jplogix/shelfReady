"""Persisted job worker — polls DB and can resume after restart."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.agent.runner import execute_job
from app.db.models import Job, JobStatus
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("shelfready.worker")


def claim_next_job() -> uuid.UUID | None:
    """Atomically claim one pending job. Skip locked rows so workers cannot share a job."""
    db = SessionLocal()
    try:
        running = db.scalar(select(Job).where(Job.status == JobStatus.running).limit(1))
        if running:
            return None
        job = db.scalar(
            select(Job)
            .where(Job.status == JobStatus.pending)
            .order_by(Job.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        return job.id
    finally:
        db.close()


def recover_stuck_running() -> None:
    """On worker start, re-queue running jobs so restart resumes work."""
    db = SessionLocal()
    try:
        stuck = db.scalars(select(Job).where(Job.status == JobStatus.running)).all()
        for job in stuck:
            logger.warning("Re-queueing interrupted job %s", job.id)
            job.status = JobStatus.pending
            if job.job_type == "process":
                job.job_type = "resume"
        db.commit()
    finally:
        db.close()


def main() -> None:
    from app.config import get_settings

    get_settings()  # fail fast on invalid production config
    logger.info("ShelfReady worker starting")
    recover_stuck_running()
    while True:
        job_id = claim_next_job()
        if not job_id:
            time.sleep(1.5)
            continue
        logger.info("Executing job %s", job_id)
        db = SessionLocal()
        try:
            execute_job(db, str(job_id))
            logger.info("Job %s finished", job_id)
        except Exception:
            logger.exception("Job %s failed", job_id)
        finally:
            db.close()


if __name__ == "__main__":
    main()
