from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from metaos.core_alpha.case_management import (
    ResearchCaseCommandHandler,
    ResearchCaseQueryHandler,
)
from metaos.core_alpha.commands import ApplicationCommandHandler
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.contracts.scope import (
    AddResearchQuestionRequest,
    CreateResearchCaseRequest,
    DeriveResearchCaseRequest,
    QuestionRole,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    UnitOfWork,
)


NOW = datetime(2026, 6, 25, 8, 0, tzinfo=timezone.utc)


def context(command_id: str = "cmd_1", *, idempotency_key: str = "idem_1") -> CommandContext:
    return CommandContext(
        command_id=command_id,
        actor_type=OpenCodeValue(code="user", registry_version="core-alpha-v1"),
        actor_id="user_1",
        idempotency_key=idempotency_key,
        correlation_id="corr_1",
        causation_id="cause_1",
        trace_id="trace_1",
    )


class FixedClock:
    def __init__(self) -> None:
        self.offset = 0

    def __call__(self) -> datetime:
        value = NOW + timedelta(minutes=self.offset)
        self.offset += 1
        return value


class ResearchCaseCommandHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()
        self.clock = FixedClock()
        self.commands = ResearchCaseCommandHandler(
            ApplicationCommandHandler(self.database),
            clock=self.clock,
        )
        self.queries = ResearchCaseQueryHandler(self.database)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def create_case(self, *, idempotency_key: str = "idem_create") -> dict:
        response = self.commands.create_case(
            CreateResearchCaseRequest(
                title="Hidden intention",
                question_text="How should hidden intention be evaluated?",
                question_role=QuestionRole.root,
            ),
            context=context(f"cmd_create_{idempotency_key}", idempotency_key=idempotency_key),
        )
        self.assertEqual(response.status_code, 201)
        return dict(response.response_body["data"])

    def test_create_case_is_idempotent_and_records_root_question(self) -> None:
        first = self.commands.create_case(
            CreateResearchCaseRequest(
                title="Hidden intention",
                question_text="How should hidden intention be evaluated?",
                question_role=QuestionRole.root,
            ),
            context=context("cmd_create_1", idempotency_key="idem_create"),
        )
        replay = self.commands.create_case(
            CreateResearchCaseRequest(
                title="Hidden intention",
                question_text="How should hidden intention be evaluated?",
                question_role=QuestionRole.root,
            ),
            context=context("cmd_create_2", idempotency_key="idem_create"),
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 201)
        self.assertFalse(first.response_body["command"]["idempotent_replay"])
        self.assertTrue(replay.response_body["command"]["idempotent_replay"])
        self.assertEqual(first.response_body["data"], replay.response_body["data"])

        case_id = first.response_body["data"]["research_case"]["research_case_id"]
        questions = self.queries.list_questions(case_id)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0].question_role, QuestionRole.root)
        self.assertEqual(questions[0].created_by, "user_1")

        with UnitOfWork(self.database, write=False) as uow:
            events = uow.events.list_for_aggregate("research_case", case_id)
            self.assertEqual(len(events), 1)
            lifecycle = uow.lifecycle.get("research_case", case_id)
            self.assertEqual(lifecycle.generation, 1)

    def test_add_question_advances_revision_and_rejects_stale_parent_or_archived_case(self) -> None:
        data = self.create_case()
        case_id = data["research_case"]["research_case_id"]
        root_question_id = data["research_question"]["research_question_id"]

        response = self.commands.add_question(
            case_id,
            AddResearchQuestionRequest(
                expected_revision=1,
                question_text="What is the strongest counterexample?",
                question_role=QuestionRole.follow_up,
            ),
            context=context("cmd_add_1", idempotency_key="idem_add_1"),
        )
        self.assertEqual(response.status_code, 200)
        updated = response.response_body["data"]["research_case"]
        question = response.response_body["data"]["research_question"]
        self.assertEqual(updated["revision"], 2)
        self.assertEqual(updated["current_question_id"], question["research_question_id"])
        self.assertEqual(question["parent_question_id"], root_question_id)

        with self.assertRaises(ConcurrencyConflictError):
            self.commands.add_question(
                case_id,
                AddResearchQuestionRequest(
                    expected_revision=1,
                    question_text="Stale write",
                    question_role=QuestionRole.follow_up,
                ),
                context=context("cmd_add_stale", idempotency_key="idem_add_stale"),
            )

        self.commands.archive_case(
            case_id,
            expected_revision=2,
            context=context("cmd_archive", idempotency_key="idem_archive"),
        )
        with self.assertRaises(ValueError):
            self.commands.add_question(
                case_id,
                AddResearchQuestionRequest(
                    expected_revision=3,
                    question_text="Archived write",
                    question_role=QuestionRole.follow_up,
                ),
                context=context("cmd_add_archived", idempotency_key="idem_add_archived"),
            )

    def test_archive_and_reopen_are_revision_guarded(self) -> None:
        data = self.create_case()
        case_id = data["research_case"]["research_case_id"]

        archived = self.commands.archive_case(
            case_id,
            expected_revision=1,
            context=context("cmd_archive", idempotency_key="idem_archive"),
        )
        archived_case = archived.response_body["data"]["research_case"]
        self.assertEqual(archived_case["revision"], 2)
        self.assertEqual(archived_case["lifecycle_status"], "archived")
        self.assertEqual(archived_case["attention_status"], "closed")
        self.assertIsNotNone(archived_case["archived_at"])

        reopened = self.commands.reopen_case(
            case_id,
            expected_revision=2,
            context=context("cmd_reopen", idempotency_key="idem_reopen"),
        )
        reopened_case = reopened.response_body["data"]["research_case"]
        self.assertEqual(reopened_case["revision"], 3)
        self.assertEqual(reopened_case["lifecycle_status"], "open")
        self.assertEqual(reopened_case["attention_status"], "active")
        self.assertIsNone(reopened_case["archived_at"])

        with self.assertRaises(ConcurrencyConflictError):
            self.commands.archive_case(
                case_id,
                expected_revision=2,
                context=context("cmd_archive_stale", idempotency_key="idem_archive_stale"),
            )

    def test_derive_case_forks_without_moving_source_history(self) -> None:
        source_data = self.create_case()
        source_case_id = source_data["research_case"]["research_case_id"]
        source_question_id = source_data["research_question"]["research_question_id"]

        derived = self.commands.derive_case(
            source_case_id,
            DeriveResearchCaseRequest(
                expected_revision=1,
                source_question_id=source_question_id,
                title="Derived counterexample study",
                question_text="Which counterexamples deserve a separate study?",
            ),
            context=context("cmd_derive", idempotency_key="idem_derive"),
        )
        self.assertEqual(derived.status_code, 201)
        derived_case = derived.response_body["data"]["research_case"]
        derived_question = derived.response_body["data"]["research_question"]
        self.assertEqual(derived_case["parent_research_case_id"], source_case_id)
        self.assertEqual(derived_question["question_role"], "derived")
        self.assertEqual(derived_question["parent_question_id"], source_question_id)

        source_case = self.queries.get_case(source_case_id)
        self.assertEqual(source_case.revision, 1)
        self.assertEqual(
            [question.research_question_id for question in self.queries.list_questions(source_case_id)],
            [source_question_id],
        )

        with self.assertRaises(ConcurrencyConflictError):
            self.commands.derive_case(
                source_case_id,
                DeriveResearchCaseRequest(
                    expected_revision=2,
                    source_question_id=source_question_id,
                    title="Stale derived study",
                    question_text="This should not fork.",
                ),
                context=context("cmd_derive_stale", idempotency_key="idem_derive_stale"),
            )

    def test_derive_rejects_source_question_from_another_case(self) -> None:
        first = self.create_case(idempotency_key="idem_create_first")
        second = self.create_case(idempotency_key="idem_create_second")

        with self.assertRaises(ValueError):
            self.commands.derive_case(
                first["research_case"]["research_case_id"],
                DeriveResearchCaseRequest(
                    expected_revision=1,
                    source_question_id=second["research_question"]["research_question_id"],
                    title="Bad derived study",
                    question_text="This source question belongs elsewhere.",
                ),
                context=context("cmd_bad_derive", idempotency_key="idem_bad_derive"),
            )


if __name__ == "__main__":
    unittest.main()
