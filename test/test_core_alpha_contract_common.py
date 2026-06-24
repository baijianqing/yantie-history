from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from pydantic import TypeAdapter, ValidationError

from metaos.core_alpha.contracts import (
    AggregateReadParams,
    AggregateRevisionReference,
    CommandContext,
    CommandMetadata,
    CommandResponse,
    Consistency,
    ConsistencySource,
    Error,
    ErrorResponse,
    HashValue,
    ListResponse,
    OpenCodeValue,
    PageInfo,
    PaginationParams,
    QueryResponse,
    ResourceReference,
    Revision,
)


UTC_NOW = datetime(2026, 6, 25, 1, 2, 3, tzinfo=timezone.utc)


def aggregate(
    aggregate_type: str = "research_case",
    aggregate_id: str = "case_1",
    revision: int = 1,
) -> AggregateRevisionReference:
    return AggregateRevisionReference(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        revision=revision,
    )


def authoritative_consistency() -> Consistency:
    return Consistency(
        source=ConsistencySource.authoritative_store,
        primary_aggregate=aggregate(),
        affected_aggregates=[],
        projection_checkpoint=None,
        is_stale=False,
        observed_at=UTC_NOW,
    )


class CoreAlphaCommonContractTests(unittest.TestCase):
    def test_closed_models_reject_extra_fields_and_blank_values(self) -> None:
        with self.assertRaises(ValidationError):
            OpenCodeValue(code="fact", registry_version="v1", extra="forbidden")
        with self.assertRaises(ValidationError):
            OpenCodeValue(code="   ", registry_version="v1")
        with self.assertRaises(ValidationError):
            ResourceReference(resource_type="JudgmentCard", resource_id="jcv_1")

        reference = ResourceReference(
            resource_type="judgment_card_version",
            resource_id=" jcv_1 ",
        )
        self.assertEqual(reference.resource_id, "jcv_1")

    def test_utc_datetime_rejects_naive_and_non_utc_offsets(self) -> None:
        valid = authoritative_consistency()
        self.assertEqual(valid.observed_at.utcoffset(), timedelta(0))
        self.assertIn('"observed_at":"2026-06-25T01:02:03Z"', valid.model_dump_json())

        base = {
            "source": "authoritative_store",
            "primary_aggregate": aggregate(),
            "affected_aggregates": [],
            "projection_checkpoint": None,
            "is_stale": False,
        }
        with self.assertRaises(ValidationError):
            Consistency(**base, observed_at=datetime(2026, 6, 25, 1, 2, 3))
        with self.assertRaises(ValidationError):
            Consistency(
                **base,
                observed_at=datetime(
                    2026,
                    6,
                    25,
                    9,
                    2,
                    3,
                    tzinfo=timezone(timedelta(hours=8)),
                ),
            )

    def test_hash_cursor_revision_and_pagination_boundaries(self) -> None:
        hash_adapter = TypeAdapter(HashValue)
        self.assertEqual(hash_adapter.validate_python("sha256:00af"), "sha256:00af")
        for invalid_hash in ("SHA256:00af", "sha256:00AF", "sha256", "sha256:"):
            with self.subTest(invalid_hash=invalid_hash), self.assertRaises(ValidationError):
                hash_adapter.validate_python(invalid_hash)

        revision_adapter = TypeAdapter(Revision)
        self.assertEqual(revision_adapter.validate_python(1), 1)
        for invalid_revision in (0, -1, True, "1"):
            with self.subTest(invalid_revision=invalid_revision), self.assertRaises(ValidationError):
                revision_adapter.validate_python(invalid_revision)

        self.assertEqual(PaginationParams().limit, 50)
        self.assertEqual(PaginationParams(limit=200, consistency_wait_ms=5000).limit, 200)
        with self.assertRaises(ValidationError):
            PaginationParams(limit=201)
        with self.assertRaises(ValidationError):
            PaginationParams(cursor="   ")
        with self.assertRaises(ValidationError):
            AggregateReadParams(minimum_revision=0)

    def test_consistency_enforces_source_and_unique_aggregate_revisions(self) -> None:
        valid = authoritative_consistency()
        self.assertFalse(valid.is_stale)

        with self.assertRaises(ValidationError):
            Consistency(
                source="authoritative_store",
                primary_aggregate=aggregate(),
                affected_aggregates=[],
                projection_checkpoint="cursor_1",
                is_stale=False,
                observed_at=UTC_NOW,
            )
        with self.assertRaises(ValidationError):
            Consistency(
                source="authoritative_store",
                primary_aggregate=aggregate(),
                affected_aggregates=[],
                projection_checkpoint=None,
                is_stale=True,
                observed_at=UTC_NOW,
            )
        with self.assertRaises(ValidationError):
            Consistency(
                source="projection",
                primary_aggregate=None,
                affected_aggregates=[],
                projection_checkpoint=None,
                is_stale=False,
                observed_at=UTC_NOW,
            )
        with self.assertRaises(ValidationError):
            Consistency(
                source="authoritative_store",
                primary_aggregate=aggregate(),
                affected_aggregates=[aggregate()],
                projection_checkpoint=None,
                is_stale=False,
                observed_at=UTC_NOW,
            )

        multi_aggregate = Consistency(
            source="authoritative_store",
            primary_aggregate=aggregate(),
            affected_aggregates=[aggregate("judgment_card", "jc_1", 3)],
            projection_checkpoint=None,
            is_stale=False,
            observed_at=UTC_NOW,
        )
        self.assertEqual(multi_aggregate.affected_aggregates[0].revision, 3)

    def test_command_context_and_envelope_preserve_idempotency_metadata(self) -> None:
        actor_type = OpenCodeValue(code="user", registry_version="core-alpha-v1")
        context = CommandContext(
            command_id="cmd_1",
            actor_type=actor_type,
            actor_id="user_1",
            idempotency_key="idem_1",
            correlation_id="corr_1",
            causation_id="cause_1",
            trace_id="trace_1",
        )
        self.assertEqual(context.actor_type.code, "user")

        invalid_context = context.model_dump()
        invalid_context["idempotency_key"] = "   "
        with self.assertRaises(ValidationError):
            CommandContext.model_validate(invalid_context)
        invalid_context = context.model_dump()
        invalid_context["untrusted_actor"] = "forbidden"
        with self.assertRaises(ValidationError):
            CommandContext.model_validate(invalid_context)

        response = CommandResponse[OpenCodeValue](
            data=actor_type,
            command=CommandMetadata(
                command_id="cmd_1",
                trace_id="trace_1",
                idempotency_key="idem_1",
                idempotent_replay=True,
            ),
            consistency=authoritative_consistency(),
        )
        self.assertTrue(response.command.idempotent_replay)
        self.assertEqual(response.consistency.primary_aggregate.revision, 1)

        with self.assertRaises(ValidationError):
            CommandResponse[OpenCodeValue](
                data=actor_type,
                command=response.command,
                consistency=Consistency(
                    source="projection",
                    primary_aggregate=aggregate(),
                    affected_aggregates=[],
                    projection_checkpoint="cursor_1",
                    is_stale=False,
                    observed_at=UTC_NOW,
                ),
            )
        with self.assertRaises(ValidationError):
            CommandResponse[OpenCodeValue](
                data=actor_type,
                command=response.command,
                consistency=Consistency(
                    source="authoritative_store",
                    primary_aggregate=None,
                    affected_aggregates=[],
                    projection_checkpoint=None,
                    is_stale=False,
                    observed_at=UTC_NOW,
                ),
            )

    def test_query_list_and_error_envelopes_have_fixed_shapes(self) -> None:
        query = QueryResponse[OpenCodeValue | None](
            data=None,
            consistency=Consistency(
                source="authoritative_store",
                primary_aggregate=aggregate(),
                affected_aggregates=[],
                projection_checkpoint=None,
                is_stale=False,
                observed_at=UTC_NOW,
            ),
        )
        self.assertIsNone(query.data)

        list_response = ListResponse[OpenCodeValue](
            data=[OpenCodeValue(code="fact", registry_version="v1")],
            page=PageInfo(next_cursor=None),
            consistency=Consistency(
                source="projection",
                primary_aggregate=None,
                affected_aggregates=[],
                projection_checkpoint="cursor_1",
                is_stale=False,
                observed_at=UTC_NOW,
            ),
        )
        self.assertEqual(list_response.data[0].code, "fact")

        with self.assertRaises(ValidationError):
            ListResponse[OpenCodeValue](
                data=[],
                page=PageInfo(next_cursor=None),
                consistency=authoritative_consistency(),
            )

        error = ErrorResponse(
            error=Error(
                code="concurrency_conflict",
                message="Revision does not match",
                details={"expected_revision": 7, "actual_revision": 8},
                trace_id="trace_1",
                retryable=False,
            )
        )
        self.assertEqual(error.error.code, "concurrency_conflict")

    def test_exported_models_generate_closed_json_schema(self) -> None:
        open_code_schema = OpenCodeValue.model_json_schema()
        command_schema = CommandResponse[OpenCodeValue].model_json_schema()

        self.assertFalse(open_code_schema["additionalProperties"])
        self.assertFalse(command_schema["additionalProperties"])
        self.assertIn("Consistency", command_schema["$defs"])
        self.assertIn("OpenCodeValue", command_schema["$defs"])


if __name__ == "__main__":
    unittest.main()
