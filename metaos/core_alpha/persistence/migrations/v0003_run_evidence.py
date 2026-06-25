"""Create Core Alpha ResearchRun, evidence, and execution record tables."""

from metaos.core_alpha.persistence.migration import Migration


MIGRATION = Migration(
    version=3,
    name="run_evidence",
    up_statements=(
        """
        CREATE TABLE core_alpha_research_runs (
            research_run_id TEXT PRIMARY KEY,
            research_case_id TEXT NOT NULL,
            research_question_id TEXT NOT NULL,
            knowledge_scope_version_id TEXT NOT NULL,
            research_plan_version_id TEXT NOT NULL,
            run_execution_spec_id TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            created_at TEXT NOT NULL,
            started_at TEXT,
            ended_at TEXT,
            superseded_by_run_id TEXT,
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id),
            FOREIGN KEY (research_question_id)
                REFERENCES core_alpha_research_questions(research_question_id),
            FOREIGN KEY (knowledge_scope_version_id)
                REFERENCES core_alpha_knowledge_scope_versions(knowledge_scope_version_id),
            FOREIGN KEY (research_plan_version_id)
                REFERENCES core_alpha_research_plan_versions(research_plan_version_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_research_runs_case
        ON core_alpha_research_runs (research_case_id, created_at)
        """,
        """
        CREATE TABLE core_alpha_run_execution_specs (
            run_execution_spec_id TEXT PRIMARY KEY,
            research_run_id TEXT NOT NULL UNIQUE,
            knowledge_scope_version_id TEXT NOT NULL,
            source_resolution_ids_json TEXT NOT NULL,
            research_plan_version_id TEXT NOT NULL,
            source_version_ids_json TEXT NOT NULL,
            index_generation_ids_json TEXT NOT NULL,
            retrieval_strategy_version TEXT NOT NULL,
            context_strategy_version TEXT NOT NULL,
            embedding_contract_json TEXT NOT NULL,
            reranker_contract_json TEXT NOT NULL,
            capability_contracts_json TEXT NOT NULL,
            allowed_implementations_json TEXT NOT NULL,
            fallback_policy_json TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            output_schema_version TEXT NOT NULL,
            audit_policy_version TEXT NOT NULL,
            decision_fitness_policy_version TEXT NOT NULL,
            egress_policy_version TEXT NOT NULL,
            system_safety_limits_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            budget_snapshot_id TEXT,
            FOREIGN KEY (research_run_id)
                REFERENCES core_alpha_research_runs(research_run_id),
            FOREIGN KEY (knowledge_scope_version_id)
                REFERENCES core_alpha_knowledge_scope_versions(knowledge_scope_version_id),
            FOREIGN KEY (research_plan_version_id)
                REFERENCES core_alpha_research_plan_versions(research_plan_version_id)
        )
        """,
        """
        CREATE TABLE core_alpha_research_attempts (
            research_attempt_id TEXT PRIMARY KEY,
            research_run_id TEXT NOT NULL,
            attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
            attempt_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            previous_attempt_id TEXT,
            started_at TEXT,
            ended_at TEXT,
            failure_category_code TEXT,
            failure_category_registry_version TEXT,
            failure_reason TEXT,
            UNIQUE (research_run_id, attempt_number),
            FOREIGN KEY (research_run_id)
                REFERENCES core_alpha_research_runs(research_run_id),
            FOREIGN KEY (previous_attempt_id)
                REFERENCES core_alpha_research_attempts(research_attempt_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_attempts_run
        ON core_alpha_research_attempts (research_run_id, attempt_number)
        """,
        """
        CREATE TABLE core_alpha_retrieval_runs (
            retrieval_run_id TEXT PRIMARY KEY,
            research_attempt_id TEXT NOT NULL,
            knowledge_scope_source_binding_id TEXT NOT NULL,
            retrieval_channel_code TEXT NOT NULL,
            retrieval_channel_registry_version TEXT NOT NULL,
            query_ref TEXT NOT NULL,
            status TEXT NOT NULL,
            retrieval_outcome TEXT,
            created_at TEXT NOT NULL,
            index_generation_id TEXT,
            started_at TEXT,
            ended_at TEXT,
            failure_reason TEXT,
            FOREIGN KEY (research_attempt_id)
                REFERENCES core_alpha_research_attempts(research_attempt_id),
            FOREIGN KEY (knowledge_scope_source_binding_id)
                REFERENCES core_alpha_knowledge_scope_bindings(knowledge_scope_source_binding_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_retrieval_runs_attempt
        ON core_alpha_retrieval_runs (research_attempt_id, created_at)
        """,
        """
        CREATE TABLE core_alpha_research_run_outcomes (
            research_run_outcome_id TEXT PRIMARY KEY,
            research_run_id TEXT NOT NULL UNIQUE,
            outcome_type TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            reason_registry_version TEXT NOT NULL,
            reason_summary TEXT NOT NULL,
            created_at TEXT NOT NULL,
            judgment_card_version_id TEXT,
            FOREIGN KEY (research_run_id)
                REFERENCES core_alpha_research_runs(research_run_id)
        )
        """,
        """
        CREATE TABLE core_alpha_execution_checkpoints (
            execution_checkpoint_id TEXT PRIMARY KEY,
            research_run_id TEXT NOT NULL,
            checkpoint_type TEXT NOT NULL,
            input_revision INTEGER NOT NULL CHECK (input_revision >= 1),
            completed_at TEXT NOT NULL,
            result_ref_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            research_attempt_id TEXT,
            FOREIGN KEY (research_run_id)
                REFERENCES core_alpha_research_runs(research_run_id),
            FOREIGN KEY (research_attempt_id)
                REFERENCES core_alpha_research_attempts(research_attempt_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_checkpoints_run
        ON core_alpha_execution_checkpoints (research_run_id, completed_at)
        """,
        """
        CREATE TABLE core_alpha_evidence_units (
            evidence_unit_id TEXT PRIMARY KEY,
            knowledge_item_id TEXT NOT NULL,
            knowledge_item_version_id TEXT NOT NULL,
            location_json TEXT NOT NULL,
            excerpt TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            origin_type_code TEXT NOT NULL,
            origin_type_registry_version TEXT NOT NULL,
            validity_status TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            chunk_id TEXT,
            origin_retrieval_run_id TEXT,
            UNIQUE (knowledge_item_version_id, location_json, content_hash),
            FOREIGN KEY (origin_retrieval_run_id)
                REFERENCES core_alpha_retrieval_runs(retrieval_run_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_evidence_units_source
        ON core_alpha_evidence_units (knowledge_item_version_id, content_hash)
        """,
        """
        CREATE TABLE core_alpha_research_evidence_uses (
            research_evidence_use_id TEXT PRIMARY KEY,
            research_run_id TEXT NOT NULL,
            research_attempt_id TEXT NOT NULL,
            evidence_unit_id TEXT NOT NULL,
            evidence_revision INTEGER NOT NULL CHECK (evidence_revision >= 1),
            knowledge_scope_version_id TEXT NOT NULL,
            use_type TEXT NOT NULL,
            validity_checked_at TEXT NOT NULL,
            validity_result TEXT NOT NULL,
            created_at TEXT NOT NULL,
            retrieval_run_id TEXT,
            FOREIGN KEY (research_run_id)
                REFERENCES core_alpha_research_runs(research_run_id),
            FOREIGN KEY (research_attempt_id)
                REFERENCES core_alpha_research_attempts(research_attempt_id),
            FOREIGN KEY (evidence_unit_id)
                REFERENCES core_alpha_evidence_units(evidence_unit_id),
            FOREIGN KEY (knowledge_scope_version_id)
                REFERENCES core_alpha_knowledge_scope_versions(knowledge_scope_version_id),
            FOREIGN KEY (retrieval_run_id)
                REFERENCES core_alpha_retrieval_runs(retrieval_run_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_evidence_uses_run
        ON core_alpha_research_evidence_uses (research_run_id, created_at)
        """,
        """
        CREATE INDEX idx_core_alpha_evidence_uses_evidence
        ON core_alpha_research_evidence_uses (evidence_unit_id, created_at)
        """,
    ),
    down_statements=(
        "DROP INDEX IF EXISTS idx_core_alpha_evidence_uses_evidence",
        "DROP INDEX IF EXISTS idx_core_alpha_evidence_uses_run",
        "DROP TABLE IF EXISTS core_alpha_research_evidence_uses",
        "DROP INDEX IF EXISTS idx_core_alpha_evidence_units_source",
        "DROP TABLE IF EXISTS core_alpha_evidence_units",
        "DROP INDEX IF EXISTS idx_core_alpha_checkpoints_run",
        "DROP TABLE IF EXISTS core_alpha_execution_checkpoints",
        "DROP TABLE IF EXISTS core_alpha_research_run_outcomes",
        "DROP INDEX IF EXISTS idx_core_alpha_retrieval_runs_attempt",
        "DROP TABLE IF EXISTS core_alpha_retrieval_runs",
        "DROP INDEX IF EXISTS idx_core_alpha_attempts_run",
        "DROP TABLE IF EXISTS core_alpha_research_attempts",
        "DROP TABLE IF EXISTS core_alpha_run_execution_specs",
        "DROP INDEX IF EXISTS idx_core_alpha_research_runs_case",
        "DROP TABLE IF EXISTS core_alpha_research_runs",
    ),
)


__all__ = ["MIGRATION"]
