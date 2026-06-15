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
            self.assertEqual(fake_queue.calls[0]["timeout"], 2 * 60 * 60)

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

    def patched_queueing(self, repo: JobRepository, fake_queue: FakeQueue):
        return patch.multiple(
            queueing,
            JobRepository=lambda: repo,
            rq_queue=lambda queue_name: fake_queue,
        )


if __name__ == "__main__":
    unittest.main()
