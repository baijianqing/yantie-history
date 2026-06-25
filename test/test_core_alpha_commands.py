from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from metaos.core_alpha.commands import (
    ApplicationCommandHandler,
    CandidateResultCommandHandler,
    CommandOutcome,
    OutboxMessage,
    StaticFeatureFlagRegistry,
)
from metaos.core_alpha.contracts.common import CommandContext
from metaos.core_alpha.contracts.internal import SubmitCandidateResultCommandRequest
from metaos.core_alpha.persistence import (
    CoreAlphaDatabase,
    IdempotencyConflictError,
    UnitOfWork,
)
from test_core_alpha_run_evidence_repository import (
    NOW,
    attempt_response,
    case_response,
    code,
    execution_spec,
    outcome_response,
    plan_response,
    question_response,
    retrieval_response,
    run_response,
    scope_response,
    source_resolution,
)


def context(
    command_id: str = "cmd_1",
    *,
    idempotency_key: str = "idem_1",
    actor: str = "user",
) -> CommandContext:
    return CommandContext(
        command_id=command_id,
        actor_type=code(actor),
        actor_id="user_1",
        idempotency_key=idempotency_key,
        correlation_id="corr_1",
        causation_id="cause_1",
        trace_id="trace_1",
    )


def candidate_request(**updates: object) -> SubmitCandidateResultCommandRequest:
    payload: dict[str, object] = {
        "operation_type": code("draft_judgment"),
        "research_run_id": "run_1",
        "research_attempt_id": "attempt_1",
        "run_execution_spec_id": "spec_1",
        "input_versions": {
            "research_run_revision": 1,
            "knowledge_scope_version_id": "ksv_1",
            "research_plan_version_id": "rpv_1",
        },
        "lifecycle_generation": 1,
        "capability_implementation_version": "impl-v1",
        "output_schema_version": "candidate-schema-v1",
        "candidate_result": {"claim": "candidate"},
    }
    payload.update(updates)
    return SubmitCandidateResultCommandRequest.model_validate(payload)


class CoreAlphaCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def seed_run(self) -> None:
        with UnitOfWork(self.database) as uow:
            uow.case_scope.create_case(
                research_case=case_response(),
                root_question=question_response(),
            )
            uow.case_scope.add_source_resolutions(
                [source_resolution()],
                expected_case_revision=1,
                updated_at=NOW + timedelta(seconds=1),
            )
            uow.case_scope.create_knowledge_scope(
                scope_response(),
                expected_case_revision=2,
                updated_at=NOW + timedelta(seconds=2),
            )
            uow.case_scope.create_research_plan(
                plan_response(),
                expected_case_revision=3,
                updated_at=NOW + timedelta(seconds=3),
            )
            uow.run_evidence.create_research_run(
                research_run=run_response(),
                execution_spec=execution_spec(),
            )
            uow.run_evidence.add_attempt(attempt_response())
            uow.run_evidence.add_retrieval_run(retrieval_response())
            uow.lifecycle.ensure("research_run", "run_1", now=NOW)

    def test_application_command_replays_first_response_and_rejects_key_conflict(self) -> None:
        handler = ApplicationCommandHandler(self.database)
        calls = {"count": 0}

        def callback(uow: UnitOfWork) -> CommandOutcome:
            calls["count"] += 1
            return CommandOutcome(
                data={"value": calls["count"]},
                primary_aggregate_type="test_aggregate",
                primary_aggregate_id="agg_1",
                primary_aggregate_revision=1,
                event_type_code="test_command_completed",
            )

        first = handler.execute(
            scope="user_1:POST:/alpha/test",
            idempotency_key="idem_1",
            request_body={"x": 1},
            context=context(),
            callback=callback,
        )
        replay = handler.execute(
            scope="user_1:POST:/alpha/test",
            idempotency_key="idem_1",
            request_body={"x": 1},
            context=context("cmd_2"),
            callback=callback,
        )

        self.assertEqual(calls["count"], 1)
        self.assertFalse(first.idempotent_replay)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(first.response_body["data"], replay.response_body["data"])
        self.assertFalse(first.response_body["command"]["idempotent_replay"])
        self.assertTrue(replay.response_body["command"]["idempotent_replay"])

        with UnitOfWork(self.database, write=False) as uow:
            events = uow.events.list_for_aggregate("test_aggregate", "agg_1")
            self.assertEqual(len(events), 1)

        with self.assertRaises(IdempotencyConflictError):
            handler.execute(
                scope="user_1:POST:/alpha/test",
                idempotency_key="idem_1",
                request_body={"x": 2},
                context=context("cmd_3"),
                callback=callback,
            )

    def test_command_outbox_is_written_once_across_replay(self) -> None:
        handler = ApplicationCommandHandler(self.database)

        def callback(uow: UnitOfWork) -> CommandOutcome:
            return CommandOutcome(
                data={"queued": True},
                primary_aggregate_type="test_aggregate",
                primary_aggregate_id="agg_outbox",
                primary_aggregate_revision=1,
                event_type_code="outbox_test_completed",
                outbox_messages=(
                    OutboxMessage(
                        outbox_id="outbox_1",
                        topic="test.topic",
                        payload={"message": "hello"},
                        idempotency_key="outbox-idem-1",
                        available_at=NOW,
                    ),
                ),
            )

        for command_id in ("cmd_1", "cmd_2"):
            handler.execute(
                scope="user_1:POST:/alpha/outbox-test",
                idempotency_key="idem_outbox",
                request_body={"enqueue": True},
                context=context(command_id, idempotency_key="idem_outbox"),
                callback=callback,
            )

        with UnitOfWork(self.database) as uow:
            claimed = uow.outbox.claim_pending(
                worker_id="worker_1",
                now=NOW,
                lease_expires_at=NOW + timedelta(seconds=10),
            )
            self.assertEqual(len(claimed), 1)
            self.assertEqual(claimed[0].outbox_id, "outbox_1")

    def test_candidate_result_rejects_stale_versions_and_tombstones(self) -> None:
        self.seed_run()
        handler = CandidateResultCommandHandler(ApplicationCommandHandler(self.database))

        accepted = handler.submit(
            candidate_request(),
            context=context("cmd_candidate_1", idempotency_key="candidate-idem-1", actor="worker"),
        )
        self.assertEqual(
            accepted.response_body["data"]["submission_status"],
            "accepted_for_domain_processing",
        )
        self.assertIsNotNone(accepted.response_body["data"]["capability_candidate_result_id"])

        with UnitOfWork(self.database) as uow:
            uow.run_evidence.commit_outcome(
                outcome_response(),
                expected_run_revision=1,
                ended_at=NOW + timedelta(minutes=4),
            )

        stale = handler.submit(
            candidate_request(),
            context=context("cmd_candidate_2", idempotency_key="candidate-idem-2", actor="worker"),
        )
        self.assertEqual(
            stale.response_body["data"]["submission_status"],
            "rejected_version_mismatch",
        )
        self.assertIsNone(stale.response_body["data"]["capability_candidate_result_id"])

        with UnitOfWork(self.database) as uow:
            uow.lifecycle.advance_with_tombstone(
                tombstone_id="tombstone_1",
                entity_type="research_run",
                entity_id="run_1",
                expected_generation=1,
                reason="Deleted by user",
                idempotency_key="delete-run-1",
                deleted_at=NOW + timedelta(minutes=5),
            )

        tombstoned = handler.submit(
            candidate_request(input_versions={
                "research_run_revision": 2,
                "knowledge_scope_version_id": "ksv_1",
                "research_plan_version_id": "rpv_1",
            }),
            context=context("cmd_candidate_3", idempotency_key="candidate-idem-3", actor="worker"),
        )
        self.assertEqual(
            tombstoned.response_body["data"]["submission_status"],
            "rejected_tombstoned",
        )

        with UnitOfWork(self.database, write=False) as uow:
            run = uow.run_evidence.get_research_run("run_1")
            self.assertEqual(run.revision, 2)
            self.assertEqual(run.status, "completed")

    def test_feature_flags_default_off_and_changes_are_audited_without_domain_rewrite(self) -> None:
        self.seed_run()
        registry = StaticFeatureFlagRegistry.core_alpha_defaults()
        snapshot = registry.get("core_alpha.asynchronous_execution")
        self.assertFalse(snapshot.enabled)
        self.assertFalse(snapshot.overridden)

        with UnitOfWork(self.database) as uow:
            before = uow.run_evidence.get_research_run("run_1")
            changed = registry.set_override(
                uow=uow,
                context=context("cmd_flag_1"),
                flag_key="core_alpha.asynchronous_execution",
                enabled=True,
                reason="Manual development override.",
                occurred_at=NOW,
            )
            after = uow.run_evidence.get_research_run("run_1")
            self.assertTrue(changed.enabled)
            self.assertEqual(before.revision, after.revision)
            self.assertEqual(before.status, after.status)

        with UnitOfWork(self.database, write=False) as uow:
            events = uow.events.list_for_aggregate(
                "feature_flag",
                "core_alpha.asynchronous_execution",
            )
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].payload["enabled"], True)


if __name__ == "__main__":
    unittest.main()
