from __future__ import annotations

import unittest
from typing import Callable

from fastapi.testclient import TestClient

import metaos.app.api as api
from metaos.core.errors import ConfigurationError, JobNotFoundError
from metaos.core.schemas import Job, JobStatus, JobType


class JobRetryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_enqueue_retry_job: Callable = api.enqueue_retry_job
        self.client = TestClient(api.app)

    def tearDown(self) -> None:
        api.enqueue_retry_job = self.original_enqueue_retry_job

    def test_retry_job_returns_requeued_job(self) -> None:
        def fake_retry(job_id: str) -> Job:
            return Job(
                id=job_id,
                type=JobType.answer_question,
                status=JobStatus.pending,
                progress=0,
                message="Requeued: rag",
                result={"retry_history": [{"attempt": 1, "error": "timeout"}]},
            )

        api.enqueue_retry_job = fake_retry

        response = self.client.post("/jobs/job_alpha/retry")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], "job_alpha")
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["message"], "Requeued: rag")
        self.assertEqual(payload["result"]["retry_history"][0]["error"], "timeout")

    def test_retry_job_returns_404_for_missing_job(self) -> None:
        def fake_retry(job_id: str) -> Job:
            raise JobNotFoundError(f"Job not found: {job_id}")

        api.enqueue_retry_job = fake_retry

        response = self.client.post("/jobs/job_missing/retry")

        self.assertEqual(response.status_code, 404)
        self.assertIn("job_missing", response.json()["detail"])

    def test_retry_job_returns_400_for_invalid_retry_state_or_redis_failure(self) -> None:
        def invalid_retry(job_id: str) -> Job:
            raise ValueError("only failed jobs can be retried")

        api.enqueue_retry_job = invalid_retry
        invalid_response = self.client.post("/jobs/job_pending/retry")
        self.assertEqual(invalid_response.status_code, 400)
        self.assertIn("only failed", invalid_response.json()["detail"])

        def redis_failure(job_id: str) -> Job:
            raise ConfigurationError("Cannot connect to Redis")

        api.enqueue_retry_job = redis_failure
        redis_response = self.client.post("/jobs/job_failed/retry")
        self.assertEqual(redis_response.status_code, 400)
        self.assertIn("Redis", redis_response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
