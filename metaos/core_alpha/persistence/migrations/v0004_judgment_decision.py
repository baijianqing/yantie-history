"""Create Core Alpha Judgment and Decision repository tables."""

from metaos.core_alpha.persistence.migration import Migration


MIGRATION = Migration(
    version=4,
    name="judgment_decision",
    up_statements=(
        """
        CREATE TABLE core_alpha_judgment_cards (
            judgment_card_id TEXT PRIMARY KEY,
            research_case_id TEXT NOT NULL,
            research_run_id TEXT NOT NULL,
            current_version_id TEXT NOT NULL,
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id),
            FOREIGN KEY (research_run_id)
                REFERENCES core_alpha_research_runs(research_run_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_judgment_cards_case
        ON core_alpha_judgment_cards (research_case_id)
        """,
        """
        CREATE TABLE core_alpha_judgment_card_versions (
            judgment_card_version_id TEXT PRIMARY KEY,
            judgment_card_id TEXT NOT NULL,
            research_case_id TEXT NOT NULL,
            research_run_id TEXT NOT NULL,
            version INTEGER NOT NULL CHECK (version >= 1),
            revision INTEGER NOT NULL CHECK (revision >= 1),
            claim_version_ids_json TEXT NOT NULL,
            summary TEXT NOT NULL,
            uncertainties_json TEXT NOT NULL,
            evidence_gaps_json TEXT NOT NULL,
            audit_status TEXT NOT NULL,
            validity_status TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            previous_version_id TEXT,
            current_judgment_audit_id TEXT,
            decision_fitness_id TEXT,
            UNIQUE (judgment_card_id, version),
            FOREIGN KEY (judgment_card_id)
                REFERENCES core_alpha_judgment_cards(judgment_card_id),
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id),
            FOREIGN KEY (research_run_id)
                REFERENCES core_alpha_research_runs(research_run_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_judgment_versions_run
        ON core_alpha_judgment_card_versions (research_run_id, version)
        """,
        """
        CREATE TABLE core_alpha_claim_versions (
            claim_version_id TEXT PRIMARY KEY,
            claim_id TEXT NOT NULL,
            judgment_card_version_id TEXT NOT NULL,
            claim_text TEXT NOT NULL,
            epistemic_type TEXT NOT NULL,
            expression_role TEXT NOT NULL,
            evidence_status TEXT NOT NULL,
            importance TEXT NOT NULL,
            confidence_level TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL,
            user_attitude TEXT NOT NULL,
            version INTEGER NOT NULL CHECK (version >= 1),
            created_at TEXT NOT NULL,
            judgment_rationale_id TEXT,
            previous_version_id TEXT,
            UNIQUE (claim_id, version),
            FOREIGN KEY (judgment_card_version_id)
                REFERENCES core_alpha_judgment_card_versions(judgment_card_version_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_claims_judgment
        ON core_alpha_claim_versions (judgment_card_version_id)
        """,
        """
        CREATE TABLE core_alpha_claim_evidence_links (
            claim_evidence_link_id TEXT PRIMARY KEY,
            claim_version_id TEXT NOT NULL,
            research_evidence_use_id TEXT NOT NULL,
            evidence_unit_id TEXT NOT NULL,
            evidence_role TEXT NOT NULL,
            support_strength_level TEXT NOT NULL,
            support_strength_reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            scope_note TEXT,
            FOREIGN KEY (claim_version_id)
                REFERENCES core_alpha_claim_versions(claim_version_id),
            FOREIGN KEY (research_evidence_use_id)
                REFERENCES core_alpha_research_evidence_uses(research_evidence_use_id),
            FOREIGN KEY (evidence_unit_id)
                REFERENCES core_alpha_evidence_units(evidence_unit_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_claim_links_claim
        ON core_alpha_claim_evidence_links (claim_version_id)
        """,
        """
        CREATE TABLE core_alpha_judgment_rationales (
            judgment_rationale_id TEXT PRIMARY KEY,
            claim_version_id TEXT NOT NULL,
            rationale_profile_json TEXT NOT NULL,
            evidence_link_ids_json TEXT NOT NULL,
            reasoning_summary TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (claim_version_id)
                REFERENCES core_alpha_claim_versions(claim_version_id)
        )
        """,
        """
        CREATE TABLE core_alpha_judgment_audits (
            judgment_audit_id TEXT PRIMARY KEY,
            judgment_card_version_id TEXT NOT NULL,
            audit_policy_version TEXT NOT NULL,
            audit_run_status TEXT NOT NULL,
            finding_ids_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            gate_result TEXT,
            started_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (judgment_card_version_id)
                REFERENCES core_alpha_judgment_card_versions(judgment_card_version_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_audits_judgment
        ON core_alpha_judgment_audits (judgment_card_version_id, created_at)
        """,
        """
        CREATE TABLE core_alpha_audit_findings (
            audit_finding_id TEXT PRIMARY KEY,
            judgment_audit_id TEXT NOT NULL,
            affected_claim_version_ids_json TEXT NOT NULL,
            finding_type_code TEXT NOT NULL,
            finding_type_registry_version TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            supporting_reason TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            recommended_revision TEXT,
            risk_trigger_condition TEXT,
            FOREIGN KEY (judgment_audit_id)
                REFERENCES core_alpha_judgment_audits(judgment_audit_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_findings_audit
        ON core_alpha_audit_findings (judgment_audit_id)
        """,
        """
        CREATE TABLE core_alpha_warning_acknowledgements (
            warning_acknowledgement_id TEXT PRIMARY KEY,
            audit_finding_id TEXT NOT NULL,
            judgment_card_version_id TEXT NOT NULL,
            acknowledged_by TEXT NOT NULL,
            acknowledged_at TEXT NOT NULL,
            acknowledgement_note TEXT,
            FOREIGN KEY (audit_finding_id)
                REFERENCES core_alpha_audit_findings(audit_finding_id),
            FOREIGN KEY (judgment_card_version_id)
                REFERENCES core_alpha_judgment_card_versions(judgment_card_version_id)
        )
        """,
        """
        CREATE TABLE core_alpha_decision_fitnesses (
            decision_fitness_id TEXT PRIMARY KEY,
            judgment_card_version_id TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            allowed_uses_json TEXT NOT NULL,
            forbidden_uses_json TEXT NOT NULL,
            required_conditions_json TEXT NOT NULL,
            risk_ceiling_json TEXT NOT NULL,
            escalation_triggers_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (judgment_card_version_id)
                REFERENCES core_alpha_judgment_card_versions(judgment_card_version_id)
        )
        """,
        """
        CREATE TABLE core_alpha_disposition_proposals (
            disposition_proposal_id TEXT PRIMARY KEY,
            research_case_id TEXT NOT NULL,
            current_version_id TEXT NOT NULL,
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_disposition_proposals_case
        ON core_alpha_disposition_proposals (research_case_id)
        """,
        """
        CREATE TABLE core_alpha_disposition_proposal_versions (
            disposition_proposal_version_id TEXT PRIMARY KEY,
            disposition_proposal_id TEXT NOT NULL,
            research_case_id TEXT NOT NULL,
            judgment_card_version_id TEXT NOT NULL,
            decision_fitness_id TEXT NOT NULL,
            proposed_disposition_type TEXT NOT NULL,
            reason TEXT NOT NULL,
            user_decision_status TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL,
            version INTEGER NOT NULL CHECK (version >= 1),
            revision INTEGER NOT NULL CHECK (revision >= 1),
            created_at TEXT NOT NULL,
            warning_acknowledgement_ids_json TEXT NOT NULL,
            previous_version_id TEXT,
            expires_at TEXT,
            defer_until TEXT,
            observation_condition TEXT,
            UNIQUE (disposition_proposal_id, version),
            FOREIGN KEY (disposition_proposal_id)
                REFERENCES core_alpha_disposition_proposals(disposition_proposal_id),
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id),
            FOREIGN KEY (judgment_card_version_id)
                REFERENCES core_alpha_judgment_card_versions(judgment_card_version_id),
            FOREIGN KEY (decision_fitness_id)
                REFERENCES core_alpha_decision_fitnesses(decision_fitness_id)
        )
        """,
        """
        CREATE TABLE core_alpha_research_dispositions (
            research_disposition_id TEXT PRIMARY KEY,
            research_case_id TEXT NOT NULL,
            source_disposition_proposal_version_id TEXT NOT NULL,
            judgment_card_version_id TEXT NOT NULL,
            decision_fitness_id TEXT NOT NULL,
            disposition_type TEXT NOT NULL,
            confirmed_by TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            supersedes_disposition_id TEXT,
            defer_until TEXT,
            observation_condition TEXT,
            FOREIGN KEY (research_case_id)
                REFERENCES core_alpha_research_cases(research_case_id),
            FOREIGN KEY (source_disposition_proposal_version_id)
                REFERENCES core_alpha_disposition_proposal_versions(disposition_proposal_version_id),
            FOREIGN KEY (judgment_card_version_id)
                REFERENCES core_alpha_judgment_card_versions(judgment_card_version_id),
            FOREIGN KEY (decision_fitness_id)
                REFERENCES core_alpha_decision_fitnesses(decision_fitness_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_dispositions_case
        ON core_alpha_research_dispositions (research_case_id, confirmed_at)
        """,
    ),
    down_statements=(
        "DROP INDEX IF EXISTS idx_core_alpha_dispositions_case",
        "DROP TABLE IF EXISTS core_alpha_research_dispositions",
        "DROP TABLE IF EXISTS core_alpha_disposition_proposal_versions",
        "DROP INDEX IF EXISTS idx_core_alpha_disposition_proposals_case",
        "DROP TABLE IF EXISTS core_alpha_disposition_proposals",
        "DROP TABLE IF EXISTS core_alpha_decision_fitnesses",
        "DROP TABLE IF EXISTS core_alpha_warning_acknowledgements",
        "DROP INDEX IF EXISTS idx_core_alpha_findings_audit",
        "DROP TABLE IF EXISTS core_alpha_audit_findings",
        "DROP INDEX IF EXISTS idx_core_alpha_audits_judgment",
        "DROP TABLE IF EXISTS core_alpha_judgment_audits",
        "DROP TABLE IF EXISTS core_alpha_judgment_rationales",
        "DROP INDEX IF EXISTS idx_core_alpha_claim_links_claim",
        "DROP TABLE IF EXISTS core_alpha_claim_evidence_links",
        "DROP INDEX IF EXISTS idx_core_alpha_claims_judgment",
        "DROP TABLE IF EXISTS core_alpha_claim_versions",
        "DROP INDEX IF EXISTS idx_core_alpha_judgment_versions_run",
        "DROP TABLE IF EXISTS core_alpha_judgment_card_versions",
        "DROP INDEX IF EXISTS idx_core_alpha_judgment_cards_case",
        "DROP TABLE IF EXISTS core_alpha_judgment_cards",
    ),
)


__all__ = ["MIGRATION"]
