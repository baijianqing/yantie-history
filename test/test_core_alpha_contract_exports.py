from __future__ import annotations

import hashlib
import json
import unittest

from pydantic import BaseModel

import metaos.core_alpha.contracts as contracts
from metaos.core_alpha.contracts import decision, execution, internal, judgment, scope


COMMON_EXPORTS = [
    "AggregateReadParams",
    "AggregateRevisionReference",
    "CodeIdentifier",
    "CommandContext",
    "CommandMetadata",
    "CommandResponse",
    "Consistency",
    "ConsistencySource",
    "Error",
    "ErrorResponse",
    "HashValue",
    "IdempotencyKey",
    "ListResponse",
    "NonEmptyString",
    "NonNegativeInt",
    "OpaqueCursor",
    "OpenCodeValue",
    "PageInfo",
    "PaginationParams",
    "QueryResponse",
    "ResourceId",
    "ResourceReference",
    "Revision",
    "StrictContractModel",
    "UtcDateTime",
]

SCHEMA_SNAPSHOT_HASH = "262af0a81881b230a358527ce58b79b4d121d2fac6417579bcd92d479cacc5dd"


class CoreAlphaContractExportTests(unittest.TestCase):
    def test_public_exports_are_complete_unique_and_ordered(self) -> None:
        expected = [
            *COMMON_EXPORTS,
            *scope.__all__,
            *execution.__all__,
            *judgment.__all__,
            *decision.__all__,
            *internal.__all__,
        ]
        self.assertEqual(contracts.__all__, expected)
        self.assertEqual(len(expected), len(set(expected)))
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(hasattr(contracts, name))

    def test_contract_submodule_exports_do_not_overlap(self) -> None:
        owners: dict[str, str] = {}
        for module in (scope, execution, judgment, decision, internal):
            for name in module.__all__:
                with self.subTest(module=module.__name__, name=name):
                    self.assertNotIn(name, owners)
                    owners[name] = module.__name__

    def test_every_exported_model_has_a_closed_root_schema(self) -> None:
        for name, model in self.exported_models().items():
            with self.subTest(name=name):
                schema = model.model_json_schema()
                self.assertFalse(schema["additionalProperties"])

    def test_combined_json_schema_snapshot_is_stable(self) -> None:
        schemas = {
            name: model.model_json_schema()
            for name, model in sorted(self.exported_models().items())
        }
        encoded = json.dumps(
            schemas,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        self.assertEqual(digest, SCHEMA_SNAPSHOT_HASH)

    @staticmethod
    def exported_models() -> dict[str, type[BaseModel]]:
        models: dict[str, type[BaseModel]] = {}
        for name in contracts.__all__:
            value = getattr(contracts, name)
            if (
                isinstance(value, type)
                and issubclass(value, BaseModel)
                and value is not contracts.StrictContractModel
            ):
                models[name] = value
        return models


if __name__ == "__main__":
    unittest.main()
