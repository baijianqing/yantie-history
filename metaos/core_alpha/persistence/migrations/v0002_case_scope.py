"""Create Core Alpha ResearchCase, SourceResolution, Scope, and Plan tables."""

from metaos.core_alpha.persistence.migration import Migration


MIGRATION = Migration(
    version=2,
    name="case_scope_plan",
    up_statements=(
        """
        CREATE TABLE core_alpha_research_cases (
            research_case_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            root_question_id TEXT NOT NULL,
            current_question_id TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL,
            attention_status TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            current_knowledge_scope_version_id TEXT,
            current_judgment_card_version_id TEXT,
            current_research_disposition_id TEXT,
            parent_research_case_id TEXT,
            archived_at TEXT
        )
        """,
        """
        CREATE INDEX idx_core_alpha_cases_updated
        ON core_alpha_research_cases (updated_at)
        """,
        """
        CREATE TABLE core_alpha_research_questions (
            research_question_id TEXT PRIMARY KEY,
            research_case_id TEXT NOT NULL,
            question_text TEXT NOT NULL,
            question_role TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            parent_question_id TEXT,
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_questions_case
        ON core_alpha_research_questions (research_case_id, created_at)
        """,
        """
        CREATE TABLE core_alpha_source_resolutions (
            source_resolution_id TEXT PRIMARY KEY,
            research_question_id TEXT NOT NULL,
            resolution_stage TEXT NOT NULL,
            raw_anchor TEXT NOT NULL,
            requested_access_policy TEXT NOT NULL,
            resolution_status TEXT NOT NULL,
            candidate_knowledge_item_ids_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            requested_version_hint TEXT,
            resolved_knowledge_item_id TEXT,
            resolved_knowledge_item_version_id TEXT,
            ambiguity_reason TEXT,
            failure_reason TEXT,
            FOREIGN KEY (research_question_id)
                REFERENCES core_alpha_research_questions(research_question_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_source_resolutions_question
        ON core_alpha_source_resolutions (research_question_id, created_at)
        """,
        """
        CREATE TABLE core_alpha_knowledge_scopes (
            knowledge_scope_id TEXT PRIMARY KEY,
            research_case_id TEXT NOT NULL,
            current_version_id TEXT NOT NULL,
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id)
        )
        """,
        """
        CREATE TABLE core_alpha_knowledge_scope_versions (
            knowledge_scope_version_id TEXT PRIMARY KEY,
            knowledge_scope_id TEXT NOT NULL,
            research_case_id TEXT NOT NULL,
            version INTEGER NOT NULL CHECK (version >= 1),
            lifecycle_status TEXT NOT NULL,
            scope_mode TEXT NOT NULL,
            default_access_policy TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            previous_version_id TEXT,
            UNIQUE (knowledge_scope_id, version),
            FOREIGN KEY (knowledge_scope_id)
                REFERENCES core_alpha_knowledge_scopes(knowledge_scope_id),
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_scope_versions_case
        ON core_alpha_knowledge_scope_versions (research_case_id, version)
        """,
        """
        CREATE TABLE core_alpha_knowledge_scope_bindings (
            knowledge_scope_source_binding_id TEXT PRIMARY KEY,
            knowledge_scope_version_id TEXT NOT NULL,
            source_resolution_id TEXT NOT NULL,
            knowledge_item_id TEXT NOT NULL,
            knowledge_item_version_id TEXT,
            access_policy TEXT NOT NULL,
            analysis_role TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (knowledge_scope_version_id)
                REFERENCES core_alpha_knowledge_scope_versions(knowledge_scope_version_id),
            FOREIGN KEY (source_resolution_id)
                REFERENCES core_alpha_source_resolutions(source_resolution_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_scope_bindings_version
        ON core_alpha_knowledge_scope_bindings (knowledge_scope_version_id)
        """,
        """
        CREATE TABLE core_alpha_research_plans (
            research_plan_id TEXT PRIMARY KEY,
            research_case_id TEXT NOT NULL,
            current_version_id TEXT NOT NULL,
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id)
        )
        """,
        """
        CREATE TABLE core_alpha_research_plan_versions (
            research_plan_version_id TEXT PRIMARY KEY,
            research_plan_id TEXT NOT NULL,
            research_case_id TEXT NOT NULL,
            knowledge_scope_version_id TEXT NOT NULL,
            version INTEGER NOT NULL CHECK (version >= 1),
            lifecycle_status TEXT NOT NULL,
            research_mode TEXT NOT NULL,
            primary_objective TEXT NOT NULL,
            minimum_completion_condition TEXT NOT NULL,
            created_at TEXT NOT NULL,
            previous_version_id TEXT,
            stop_conditions_json TEXT,
            research_budget_json TEXT,
            UNIQUE (research_plan_id, version),
            FOREIGN KEY (research_plan_id)
                REFERENCES core_alpha_research_plans(research_plan_id),
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id),
            FOREIGN KEY (knowledge_scope_version_id)
                REFERENCES core_alpha_knowledge_scope_versions(knowledge_scope_version_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_plan_versions_case
        ON core_alpha_research_plan_versions (research_case_id, version)
        """,
        """
        CREATE TABLE core_alpha_evidence_requirements (
            evidence_requirement_id TEXT PRIMARY KEY,
            research_plan_version_id TEXT NOT NULL,
            requirement_type_code TEXT NOT NULL,
            requirement_type_registry_version TEXT NOT NULL,
            description TEXT NOT NULL,
            required_binding_ids_json TEXT NOT NULL,
            counterevidence_required INTEGER NOT NULL,
            alternative_interpretation_required INTEGER NOT NULL,
            completion_condition TEXT NOT NULL,
            minimum_count INTEGER,
            FOREIGN KEY (research_plan_version_id)
                REFERENCES core_alpha_research_plan_versions(research_plan_version_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_requirements_plan
        ON core_alpha_evidence_requirements (research_plan_version_id)
        """,
    ),
    down_statements=(
        "DROP INDEX IF EXISTS idx_core_alpha_requirements_plan",
        "DROP TABLE IF EXISTS core_alpha_evidence_requirements",
        "DROP INDEX IF EXISTS idx_core_alpha_plan_versions_case",
        "DROP TABLE IF EXISTS core_alpha_research_plan_versions",
        "DROP TABLE IF EXISTS core_alpha_research_plans",
        "DROP INDEX IF EXISTS idx_core_alpha_scope_bindings_version",
        "DROP TABLE IF EXISTS core_alpha_knowledge_scope_bindings",
        "DROP INDEX IF EXISTS idx_core_alpha_scope_versions_case",
        "DROP TABLE IF EXISTS core_alpha_knowledge_scope_versions",
        "DROP TABLE IF EXISTS core_alpha_knowledge_scopes",
        "DROP INDEX IF EXISTS idx_core_alpha_source_resolutions_question",
        "DROP TABLE IF EXISTS core_alpha_source_resolutions",
        "DROP INDEX IF EXISTS idx_core_alpha_questions_case",
        "DROP TABLE IF EXISTS core_alpha_research_questions",
        "DROP INDEX IF EXISTS idx_core_alpha_cases_updated",
        "DROP TABLE IF EXISTS core_alpha_research_cases",
    ),
)


__all__ = ["MIGRATION"]
