"""Create Core Alpha MaterialManifest tables for outbound data policy."""

from metaos.core_alpha.persistence.migration import Migration


MIGRATION = Migration(
    version=5,
    name="material_manifest",
    up_statements=(
        """
        CREATE TABLE core_alpha_material_manifests (
            material_manifest_id TEXT PRIMARY KEY,
            invocation_type_code TEXT NOT NULL,
            invocation_type_registry_version TEXT NOT NULL,
            invocation_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            purpose_code TEXT NOT NULL,
            purpose_registry_version TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            policy_decision TEXT NOT NULL,
            decision_reason TEXT NOT NULL,
            materials_json TEXT NOT NULL,
            contains_profile_data INTEGER NOT NULL CHECK (contains_profile_data IN (0, 1)),
            created_at TEXT NOT NULL,
            research_case_id TEXT,
            research_run_id TEXT,
            research_attempt_id TEXT,
            capability_invocation_id TEXT,
            intake_or_import_context_ref TEXT,
            correlation_id TEXT NOT NULL,
            causation_id TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id),
            FOREIGN KEY (research_run_id)
                REFERENCES core_alpha_research_runs(research_run_id),
            FOREIGN KEY (research_attempt_id)
                REFERENCES core_alpha_research_attempts(research_attempt_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_material_manifests_run
        ON core_alpha_material_manifests (research_run_id, created_at)
        """,
        """
        CREATE INDEX idx_core_alpha_material_manifests_provider
        ON core_alpha_material_manifests (provider, purpose_code, created_at)
        """,
        """
        CREATE UNIQUE INDEX idx_core_alpha_material_manifests_invocation
        ON core_alpha_material_manifests (invocation_type_code, invocation_id)
        """,
    ),
    down_statements=(
        "DROP INDEX IF EXISTS idx_core_alpha_material_manifests_invocation",
        "DROP INDEX IF EXISTS idx_core_alpha_material_manifests_provider",
        "DROP INDEX IF EXISTS idx_core_alpha_material_manifests_run",
        "DROP TABLE IF EXISTS core_alpha_material_manifests",
    ),
)


__all__ = ["MIGRATION"]
