"""Repository for immutable Core Alpha MaterialManifest records."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from metaos.core_alpha.contracts.egress import MaterialManifestResponse
from metaos.core_alpha.persistence.repositories import (
    RecordNotFoundError,
    RepositoryBase,
    _canonical_json,
    _utc_iso,
)


def _load_json(value: str | None, default: Any) -> Any:
    return json.loads(value) if value is not None else default


class MaterialManifestRepository(RepositoryBase):
    table_name = "core_alpha_material_manifests"
    id_column = "material_manifest_id"

    def add(self, manifest: MaterialManifestResponse) -> None:
        self.connection.execute(
            """
            INSERT INTO core_alpha_material_manifests (
                material_manifest_id, invocation_type_code,
                invocation_type_registry_version, invocation_id, provider,
                purpose_code, purpose_registry_version, policy_version,
                policy_decision, decision_reason, materials_json,
                contains_profile_data, created_at, research_case_id,
                research_run_id, research_attempt_id, capability_invocation_id,
                intake_or_import_context_ref, correlation_id, causation_id,
                trace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._values(manifest),
        )

    def get(self, material_manifest_id: str) -> MaterialManifestResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_material_manifests
            WHERE material_manifest_id = ?
            """,
            (material_manifest_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"material manifest not found: {material_manifest_id}")
        return self._manifest(row)

    def get_by_invocation(
        self,
        *,
        invocation_type_code: str,
        invocation_id: str,
    ) -> MaterialManifestResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_material_manifests
            WHERE invocation_type_code = ? AND invocation_id = ?
            """,
            (invocation_type_code, invocation_id),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"material manifest not found for invocation: {invocation_type_code}/{invocation_id}"
            )
        return self._manifest(row)

    def list_for_research_run(self, research_run_id: str) -> list[MaterialManifestResponse]:
        rows = self.connection.execute(
            """
            SELECT * FROM core_alpha_material_manifests
            WHERE research_run_id = ?
            ORDER BY created_at, material_manifest_id
            """,
            (research_run_id,),
        ).fetchall()
        return [self._manifest(row) for row in rows]

    @staticmethod
    def _values(manifest: MaterialManifestResponse) -> tuple[Any, ...]:
        return (
            manifest.material_manifest_id,
            manifest.invocation_type.code,
            manifest.invocation_type.registry_version,
            manifest.invocation_id,
            manifest.provider,
            manifest.purpose.code,
            manifest.purpose.registry_version,
            manifest.policy_version,
            manifest.policy_decision,
            manifest.decision_reason,
            _canonical_json([material.model_dump(mode="json") for material in manifest.materials]),
            1 if manifest.contains_profile_data else 0,
            _utc_iso(manifest.created_at),
            manifest.research_case_id,
            manifest.research_run_id,
            manifest.research_attempt_id,
            manifest.capability_invocation_id,
            manifest.intake_or_import_context_ref,
            manifest.correlation_id,
            manifest.causation_id,
            manifest.trace_id,
        )

    @staticmethod
    def _manifest(row: sqlite3.Row) -> MaterialManifestResponse:
        return MaterialManifestResponse.model_validate(
            {
                "material_manifest_id": row["material_manifest_id"],
                "invocation_type": {
                    "code": row["invocation_type_code"],
                    "registry_version": row["invocation_type_registry_version"],
                },
                "invocation_id": row["invocation_id"],
                "provider": row["provider"],
                "purpose": {
                    "code": row["purpose_code"],
                    "registry_version": row["purpose_registry_version"],
                },
                "policy_version": row["policy_version"],
                "policy_decision": row["policy_decision"],
                "decision_reason": row["decision_reason"],
                "materials": _load_json(row["materials_json"], []),
                "contains_profile_data": bool(row["contains_profile_data"]),
                "created_at": datetime.fromisoformat(row["created_at"]),
                "research_case_id": row["research_case_id"],
                "research_run_id": row["research_run_id"],
                "research_attempt_id": row["research_attempt_id"],
                "capability_invocation_id": row["capability_invocation_id"],
                "intake_or_import_context_ref": row["intake_or_import_context_ref"],
                "correlation_id": row["correlation_id"],
                "causation_id": row["causation_id"],
                "trace_id": row["trace_id"],
            }
        )


__all__ = ["MaterialManifestRepository"]
