"""Worker restart recovery: running jobs are re-queued as resume."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready"
)
os.environ.setdefault("AGENT_MODE", "replay")

from app.db.models import Batch, BatchStatus, Job, JobStatus, Workspace
from app.db.session import SessionLocal
from app.worker import recover_stuck_running
from sqlalchemy import select


def test_recover_stuck_running_requeues():
    db = SessionLocal()
    try:
        ws = db.scalar(select(Workspace).limit(1))
        assert ws
        batch = Batch(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            name="recovery-test",
            status=BatchStatus.processing,
            counts={},
        )
        db.add(batch)
        job = Job(
            id=uuid.uuid4(),
            batch_id=batch.id,
            job_type="process",
            status=JobStatus.running,
            agent_mode="replay",
            checkpoint={"processed_ids": []},
        )
        db.add(job)
        db.commit()
        jid = job.id
    finally:
        db.close()

    recover_stuck_running()

    db = SessionLocal()
    try:
        job = db.get(Job, jid)
        assert job
        assert job.status == JobStatus.pending
        assert job.job_type == "resume"
        # cleanup so other tests are not blocked by one-job-at-a-time lock
        job.status = JobStatus.completed
        db.commit()
    finally:
        db.close()
