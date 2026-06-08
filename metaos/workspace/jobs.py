"""Job repository backed by SQLite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from metaos.core.errors import JobNotFoundError
from metaos.core.schemas import Job, JobStatus, JobType, new_id
from metaos.workspace.database import connect, initialize_database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_job(row) -> Job:
    return Job(
        id=row["id"],
        type=JobType(row["type"]),
        status=JobStatus(row["status"]),
        progress=float(row["progress"]),
        message=row["message"],
        error=row["error"],
        payload=json.loads(row["payload_json"] or "{}"),
        result=json.loads(row["result_json"] or "{}"),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class JobRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_database(database_path)

    def create(self, job_type: JobType, payload: dict[str, Any] | None = None) -> Job:
        now = _now_iso()
        job = Job(
            id=new_id("job"),
            type=job_type,
            status=JobStatus.pending,
            payload=payload or {},
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, type, status, progress, message, error,
                    payload_json, result_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.type.value,
                    job.status.value,
                    job.progress,
                    job.message,
                    job.error,
                    json.dumps(job.payload, ensure_ascii=False),
                    json.dumps(job.result, ensure_ascii=False),
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                ),
            )
        return job

    def get(self, job_id: str) -> Job:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return _row_to_job(row)

    def list(self, limit: int = 50) -> list[Job]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_job(row) for row in rows]

    def update(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress: float | None = None,
        message: str | None = None,
        error: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> Job:
        current = self.get(job_id)
        next_status = status or current.status
        next_progress = current.progress if progress is None else progress
        next_message = current.message if message is None else message
        next_error = current.error if error is None else error
        next_result = current.result if result is None else result
        updated_at = _now_iso()
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, progress = ?, message = ?, error = ?,
                    result_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_status.value,
                    next_progress,
                    next_message,
                    next_error,
                    json.dumps(next_result, ensure_ascii=False),
                    updated_at,
                    job_id,
                ),
            )
        return self.get(job_id)


def main() -> None:
    repo = JobRepository()
    job = repo.create(JobType.ingest_document, {"example": True})
    print(job.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
