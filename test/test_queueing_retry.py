from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from metaos.core.schemas import JobStatus, JobType
from metaos.tasks import queueing
from metaos.workspace.jobs import RETRY_HISTORY_KEY, JobRepository


class FakeQueue:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[dict] = []

    def enqueue_call(self, **kwargs) -> None:
        self.calls.append(kwargs)


class FakeRegistry:
    def __init__(self, job_ids: list[str] | None = None) -> None:
        self.job_ids = job_ids or []
        self.cleanup_called = False

    def cleanup(self) -> None:
        self.cleanup_called = True

    def get_job_ids(self) -> list[str]:
        return list(self.job_ids)


class FakeRQQueue(FakeQueue):
    def __init__(self, name: str, failed_job_ids: list[str]) -> None:
        super().__init__(name)
        self.connection = object()
        self.started_job_registry = FakeRegistry()
        self.failed_job_registry = FakeRegistry(failed_job_ids)


class FakeRQJob:
    exc_info = "Moved to FailedJobRegistry, due to AbandonedJobError"
    worker_name = "gpu-worker"
    origin = "ocr"
    started_at = None
    ended_at = None

    @classmethod
    def fetch(cls, job_id: str, *, connection):
        return cls()

    def get_status(self, refresh: bool = False) -> str:
        return "failed"


class QueueingRetryTests(unittest.TestCase):
    def test_enqueue_retry_job_requeues_failed_job_with_same_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = JobRepository(Path(temp_dir) / "metaos.sqlite3")
            job = repo.create(JobType.answer_question, {"question": "Alpha?", "top_k": 3})
            repo.update(job.id, status=JobStatus.failed, progress=1, message="RAG failed", error="timeout")
            fake_queue = FakeQueue("rag")

            with self.patched_queueing(repo, fake_queue):
                retried = queueing.enqueue_retry_job(job.id)

            self.assertEqual(retried.id, job.id)
            self.assertEqual(retried.status, JobStatus.pending)
            self.assertEqual(retried.progress, 0)
            self.assertEqual(retried.message, "Requeued: rag")
            self.assertEqual(retried.error, "")
            self.assertEqual(retried.result[RETRY_HISTORY_KEY][0]["error"], "timeout")
            self.assertEqual(len(fake_queue.calls), 1)
            call = fake_queue.calls[0]
            self.assertEqual(call["func"], queueing.TASK_RAG_ANSWER)
            self.assertEqual(call["args"], (job.id,))
            self.assertEqual(call["job_id"], job.id)
            self.assertIn("retry:answer_question", call["description"])

    def test_retry_dispatch_uses_ocr_pdf_pages_when_plan_path_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = JobRepository(Path(temp_dir) / "metaos.sqlite3")
            job = repo.create(
                JobType.ocr_document,
                {"source_id": "src_1", "asset_id": "asset_1", "plan_path": "plan.json"},
            )
            repo.update(job.id, status=JobStatus.failed, progress=1, error="ocr failed")
            fake_queue = FakeQueue("ocr")

            with self.patched_queueing(repo, fake_queue):
                retried = queueing.enqueue_retry_job(job.id)

            self.assertEqual(retried.message, "Requeued: ocr")
            self.assertEqual(fake_queue.calls[0]["func"], queueing.TASK_OCR_PDF_PAGES)
            self.assertEqual(fake_queue.calls[0]["timeout"], queueing.configured_ocr_timeout())

    def test_retry_rejects_pending_job_without_enqueueing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = JobRepository(Path(temp_dir) / "metaos.sqlite3")
            job = repo.create(JobType.ingest_document, {"source_id": "src_1"})
            fake_queue = FakeQueue("ingest")

            with self.patched_queueing(repo, fake_queue):
                with self.assertRaises(ValueError):
                    queueing.enqueue_retry_job(job.id)

            self.assertEqual(fake_queue.calls, [])
            self.assertEqual(repo.get(job.id).status, JobStatus.pending)

    def test_retry_rejects_unsupported_job_type_without_resetting_failed_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = JobRepository(Path(temp_dir) / "metaos.sqlite3")
            job = repo.create(JobType.summarize_knowledge, {"knowledge_item_id": "ki_1"})
            repo.update(job.id, status=JobStatus.failed, progress=1, error="unsupported")
            fake_queue = FakeQueue("rag")

            with self.patched_queueing(repo, fake_queue):
                with self.assertRaises(ValueError):
                    queueing.enqueue_retry_job(job.id)

            unchanged = repo.get(job.id)
            self.assertEqual(fake_queue.calls, [])
            self.assertEqual(unchanged.status, JobStatus.failed)
            self.assertNotIn(RETRY_HISTORY_KEY, unchanged.result)

    def test_sync_rq_failed_job_marks_running_sqlite_job_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = JobRepository(Path(temp_dir) / "metaos.sqlite3")
            job = repo.create(JobType.ocr_document, {"source_id": "src_1", "asset_id": "asset_1"})
            repo.update(job.id, status=JobStatus.running, progress=0.1, message="加载 OCR 引擎")
            fake_queue = FakeRQQueue("ocr", [job.id])

            with patch.multiple(
                queueing,
                rq_queue=lambda queue_name: fake_queue,
                RQJob=FakeRQJob,
            ):
                updated = queueing.sync_rq_failures_to_job_repository(
                    [queueing.QueueName.ocr],
                    repo=repo,
                )

            synced = repo.get(job.id)
            self.assertEqual(len(updated), 1)
            self.assertEqual(synced.status, JobStatus.failed)
            self.assertEqual(synced.progress, 1)
            self.assertIn("AbandonedJobError", synced.error)
            self.assertEqual(synced.result["rq_failure"]["worker_name"], "gpu-worker")
            self.assertTrue(fake_queue.started_job_registry.cleanup_called)

    def patched_queueing(self, repo: JobRepository, fake_queue: FakeQueue):
        return patch.multiple(
            queueing,
            JobRepository=lambda: repo,
            rq_queue=lambda queue_name: fake_queue,
        )


if __name__ == "__main__":
    unittest.main()
