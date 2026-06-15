from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from metaos.core.schemas import JobStatus, JobType
from metaos.workspace.jobs import RETRY_HISTORY_KEY, JobRepository


class JobRepositoryRetryTests(unittest.TestCase):
    def test_retry_failed_job_resets_state_and_records_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = JobRepository(Path(temp_dir) / "metaos.sqlite3")
            job = repo.create(JobType.answer_question, {"question": "Alpha?"})
            failed = repo.update(
                job.id,
                status=JobStatus.failed,
                progress=1,
                message="Search failed",
                error="embedding timeout",
                result={"partial": True},
            )

            retried = repo.retry_failed(failed.id)

            self.assertEqual(retried.status, JobStatus.pending)
            self.assertEqual(retried.progress, 0)
            self.assertEqual(retried.message, "Retry queued")
            self.assertEqual(retried.error, "")
            self.assertEqual(retried.result["partial"], True)
            history = retried.result[RETRY_HISTORY_KEY]
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["attempt"], 1)
            self.assertEqual(history[0]["failed_at"], failed.updated_at.isoformat())
            self.assertEqual(history[0]["error"], "embedding timeout")
            self.assertEqual(history[0]["message"], "Search failed")
            self.assertTrue(history[0]["retried_at"])

    def test_retry_failed_job_appends_retry_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = JobRepository(Path(temp_dir) / "metaos.sqlite3")
            job = repo.create(JobType.index_knowledge, {"knowledge_item_id": "ki_1"})

            repo.update(job.id, status=JobStatus.failed, progress=1, message="First fail", error="one")
            first_retry = repo.retry_failed(job.id)
            repo.update(first_retry.id, status=JobStatus.failed, progress=1, message="Second fail", error="two")
            second_retry = repo.retry_failed(job.id, message="Retry queued again")

            history = second_retry.result[RETRY_HISTORY_KEY]
            self.assertEqual(second_retry.message, "Retry queued again")
            self.assertEqual([item["attempt"] for item in history], [1, 2])
            self.assertEqual([item["error"] for item in history], ["one", "two"])

    def test_retry_rejects_non_failed_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = JobRepository(Path(temp_dir) / "metaos.sqlite3")
            job = repo.create(JobType.ingest_document, {"source_id": "src_1"})

            with self.assertRaises(ValueError):
                repo.retry_failed(job.id)

            unchanged = repo.get(job.id)
            self.assertEqual(unchanged.status, JobStatus.pending)
            self.assertNotIn(RETRY_HISTORY_KEY, unchanged.result)


if __name__ == "__main__":
    unittest.main()
