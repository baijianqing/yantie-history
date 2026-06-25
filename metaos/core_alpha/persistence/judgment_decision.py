"""Repositories for Core Alpha judgment and decision persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from metaos.core_alpha.contracts.common import OpenCodeValue
from metaos.core_alpha.contracts.decision import (
    DispositionProposalVersionResponse,
    DispositionType,
    ResearchDispositionResponse,
)
from metaos.core_alpha.contracts.judgment import (
    AuditFindingResponse,
    AuditFindingSeverity,
    ClaimEvidenceLinkResponse,
    ClaimUserAttitude,
    ClaimVersionResponse,
    DecisionFitnessResponse,
    DecisionRiskCeiling,
    JudgmentAuditResponse,
    JudgmentCardVersionResponse,
    JudgmentRationaleResponse,
    WarningAcknowledgementResponse,
)
from metaos.core_alpha.persistence.repositories import (
    ConcurrencyConflictError,
    RecordNotFoundError,
    RepositoryBase,
    _canonical_json,
    _utc_iso,
)


def _json(value: Any) -> str:
    return _canonical_json(value)


def _load_json(value: str | None, default: Any) -> Any:
    return json.loads(value) if value is not None else default


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def _open_code(code: str, registry_version: str) -> OpenCodeValue:
    return OpenCodeValue(code=code, registry_version=registry_version)


class JudgmentDecisionRepository(RepositoryBase):
    table_name = "core_alpha_judgment_cards"
    id_column = "judgment_card_id"

    def create_judgment_version(
        self,
        *,
        judgment_card: JudgmentCardVersionResponse,
        claims: list[ClaimVersionResponse],
        evidence_links: list[ClaimEvidenceLinkResponse],
        rationales: list[JudgmentRationaleResponse],
        decision_fitness: DecisionFitnessResponse | None = None,
    ) -> None:
        self._validate_judgment_version_payload(
            judgment_card=judgment_card,
            claims=claims,
            evidence_links=evidence_links,
            rationales=rationales,
            decision_fitness=decision_fitness,
        )
        if judgment_card.version == 1:
            self.connection.execute(
                """
                INSERT INTO core_alpha_judgment_cards (
                    judgment_card_id, research_case_id, research_run_id,
                    current_version_id
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    judgment_card.judgment_card_id,
                    judgment_card.research_case_id,
                    judgment_card.research_run_id,
                    judgment_card.judgment_card_version_id,
                ),
            )
        else:
            current = self.connection.execute(
                """
                SELECT current_version_id FROM core_alpha_judgment_cards
                WHERE judgment_card_id = ?
                """,
                (judgment_card.judgment_card_id,),
            ).fetchone()
            if current is None:
                raise RecordNotFoundError(
                    f"judgment card not found: {judgment_card.judgment_card_id}"
                )
            if current["current_version_id"] != judgment_card.previous_version_id:
                raise ConcurrencyConflictError("judgment previous_version_id is not current")
            self.connection.execute(
                """
                UPDATE core_alpha_judgment_card_versions
                SET lifecycle_status = 'superseded'
                WHERE judgment_card_version_id = ? AND lifecycle_status = 'current'
                """,
                (judgment_card.previous_version_id,),
            )

        self.connection.execute(
            """
            INSERT INTO core_alpha_judgment_card_versions (
                judgment_card_version_id, judgment_card_id, research_case_id,
                research_run_id, version, revision, claim_version_ids_json,
                summary, uncertainties_json, evidence_gaps_json, audit_status,
                validity_status, lifecycle_status, created_at, previous_version_id,
                current_judgment_audit_id, decision_fitness_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._judgment_values(judgment_card),
        )
        for claim in claims:
            self.connection.execute(
                """
                INSERT INTO core_alpha_claim_versions (
                    claim_version_id, claim_id, judgment_card_version_id,
                    claim_text, epistemic_type, expression_role, evidence_status,
                    importance, confidence_level, lifecycle_status, user_attitude,
                    version, created_at, judgment_rationale_id, previous_version_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._claim_values(claim),
            )
        for link in evidence_links:
            self.connection.execute(
                """
                INSERT INTO core_alpha_claim_evidence_links (
                    claim_evidence_link_id, claim_version_id,
                    research_evidence_use_id, evidence_unit_id, evidence_role,
                    support_strength_level, support_strength_reason, created_at,
                    scope_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._evidence_link_values(link),
            )
        for rationale in rationales:
            self.connection.execute(
                """
                INSERT INTO core_alpha_judgment_rationales (
                    judgment_rationale_id, claim_version_id, rationale_profile_json,
                    evidence_link_ids_json, reasoning_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                self._rationale_values(rationale),
            )
        if decision_fitness is not None:
            self._insert_decision_fitness(decision_fitness)
        if judgment_card.version > 1:
            self.connection.execute(
                """
                UPDATE core_alpha_judgment_cards
                SET current_version_id = ?
                WHERE judgment_card_id = ?
                """,
                (judgment_card.judgment_card_version_id, judgment_card.judgment_card_id),
            )

    def get_judgment_card_version(
        self,
        judgment_card_version_id: str,
    ) -> JudgmentCardVersionResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_judgment_card_versions
            WHERE judgment_card_version_id = ?
            """,
            (judgment_card_version_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"judgment card version not found: {judgment_card_version_id}"
            )
        return self._judgment(row)

    def get_current_judgment_card(
        self,
        judgment_card_id: str,
    ) -> JudgmentCardVersionResponse:
        row = self.connection.execute(
            """
            SELECT current_version_id FROM core_alpha_judgment_cards
            WHERE judgment_card_id = ?
            """,
            (judgment_card_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"judgment card not found: {judgment_card_id}")
        return self.get_judgment_card_version(row["current_version_id"])

    def list_claims(self, judgment_card_version_id: str) -> list[ClaimVersionResponse]:
        rows = self.connection.execute(
            """
            SELECT * FROM core_alpha_claim_versions
            WHERE judgment_card_version_id = ?
            ORDER BY created_at, claim_version_id
            """,
            (judgment_card_version_id,),
        ).fetchall()
        return [self._claim(row) for row in rows]

    def get_claim(self, claim_version_id: str) -> ClaimVersionResponse:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_claim_versions WHERE claim_version_id = ?",
            (claim_version_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"claim version not found: {claim_version_id}")
        return self._claim(row)

    def set_claim_user_attitude(
        self,
        claim_version_id: str,
        *,
        user_attitude: ClaimUserAttitude,
    ) -> ClaimVersionResponse:
        before = self.get_claim(claim_version_id)
        self.connection.execute(
            """
            UPDATE core_alpha_claim_versions
            SET user_attitude = ?
            WHERE claim_version_id = ?
            """,
            (user_attitude.value, claim_version_id),
        )
        after = self.get_claim(claim_version_id)
        if after.evidence_status != before.evidence_status:
            raise RuntimeError("user attitude update changed evidence status")
        return after

    def list_claim_evidence_links(
        self,
        claim_version_id: str,
    ) -> list[ClaimEvidenceLinkResponse]:
        rows = self.connection.execute(
            """
            SELECT * FROM core_alpha_claim_evidence_links
            WHERE claim_version_id = ?
            ORDER BY created_at, claim_evidence_link_id
            """,
            (claim_version_id,),
        ).fetchall()
        return [self._evidence_link(row) for row in rows]

    def get_judgment_rationale(self, judgment_rationale_id: str) -> JudgmentRationaleResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_judgment_rationales
            WHERE judgment_rationale_id = ?
            """,
            (judgment_rationale_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"judgment rationale not found: {judgment_rationale_id}")
        return self._rationale(row)

    def append_judgment_audit(
        self,
        *,
        audit: JudgmentAuditResponse,
        findings: list[AuditFindingResponse],
    ) -> None:
        judgment = self.get_judgment_card_version(audit.judgment_card_version_id)
        if set(audit.finding_ids) != {finding.audit_finding_id for finding in findings}:
            raise ValueError("audit finding ids must match supplied findings")
        claim_ids = set(judgment.claim_version_ids)
        for finding in findings:
            if finding.judgment_audit_id != audit.judgment_audit_id:
                raise ValueError("finding must belong to the audit")
            if not set(finding.affected_claim_version_ids).issubset(claim_ids):
                raise ValueError("finding references a claim outside the judgment")
        self.connection.execute(
            """
            INSERT INTO core_alpha_judgment_audits (
                judgment_audit_id, judgment_card_version_id, audit_policy_version,
                audit_run_status, finding_ids_json, created_at, gate_result,
                started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._audit_values(audit),
        )
        for finding in findings:
            self.connection.execute(
                """
                INSERT INTO core_alpha_audit_findings (
                    audit_finding_id, judgment_audit_id,
                    affected_claim_version_ids_json, finding_type_code,
                    finding_type_registry_version, severity, description,
                    supporting_reason, policy_version, created_at,
                    recommended_revision, risk_trigger_condition
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._finding_values(finding),
            )

    def get_judgment_audit(self, judgment_audit_id: str) -> JudgmentAuditResponse:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_judgment_audits WHERE judgment_audit_id = ?",
            (judgment_audit_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"judgment audit not found: {judgment_audit_id}")
        return self._audit(row)

    def list_audit_findings(self, judgment_audit_id: str) -> list[AuditFindingResponse]:
        rows = self.connection.execute(
            """
            SELECT * FROM core_alpha_audit_findings
            WHERE judgment_audit_id = ?
            ORDER BY created_at, audit_finding_id
            """,
            (judgment_audit_id,),
        ).fetchall()
        return [self._finding(row) for row in rows]

    def acknowledge_warning(
        self,
        acknowledgement: WarningAcknowledgementResponse,
    ) -> None:
        finding = self._get_finding_row(acknowledgement.audit_finding_id)
        if finding["severity"] != AuditFindingSeverity.warning.value:
            raise ValueError("only non-blocking warning findings can be acknowledged")
        audit = self.get_judgment_audit(finding["judgment_audit_id"])
        if audit.judgment_card_version_id != acknowledgement.judgment_card_version_id:
            raise ValueError("acknowledgement judgment does not match finding judgment")
        self.connection.execute(
            """
            INSERT INTO core_alpha_warning_acknowledgements (
                warning_acknowledgement_id, audit_finding_id,
                judgment_card_version_id, acknowledged_by, acknowledged_at,
                acknowledgement_note
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                acknowledgement.warning_acknowledgement_id,
                acknowledgement.audit_finding_id,
                acknowledgement.judgment_card_version_id,
                acknowledgement.acknowledged_by,
                _utc_iso(acknowledgement.acknowledged_at),
                acknowledgement.acknowledgement_note,
            ),
        )

    def get_warning_acknowledgement(
        self,
        warning_acknowledgement_id: str,
    ) -> WarningAcknowledgementResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_warning_acknowledgements
            WHERE warning_acknowledgement_id = ?
            """,
            (warning_acknowledgement_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"warning acknowledgement not found: {warning_acknowledgement_id}"
            )
        return self._warning_acknowledgement(row)

    def add_decision_fitness(self, decision_fitness: DecisionFitnessResponse) -> None:
        judgment = self.get_judgment_card_version(decision_fitness.judgment_card_version_id)
        if judgment.decision_fitness_id not in {None, decision_fitness.decision_fitness_id}:
            raise ValueError("judgment references another decision fitness")
        self._insert_decision_fitness(decision_fitness)

    def get_decision_fitness(self, decision_fitness_id: str) -> DecisionFitnessResponse:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_decision_fitnesses WHERE decision_fitness_id = ?",
            (decision_fitness_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"decision fitness not found: {decision_fitness_id}")
        return self._decision_fitness(row)

    def create_disposition_proposal(
        self,
        proposal: DispositionProposalVersionResponse,
    ) -> None:
        if proposal.version != 1 or proposal.previous_version_id is not None:
            raise ValueError("create_disposition_proposal requires the initial version")
        self._validate_proposal_references(proposal)
        self.connection.execute(
            """
            INSERT INTO core_alpha_disposition_proposals (
                disposition_proposal_id, research_case_id, current_version_id
            ) VALUES (?, ?, ?)
            """,
            (
                proposal.disposition_proposal_id,
                proposal.research_case_id,
                proposal.disposition_proposal_version_id,
            ),
        )
        self._insert_disposition_proposal_version(proposal)

    def adjust_disposition_proposal(
        self,
        proposal: DispositionProposalVersionResponse,
    ) -> None:
        if proposal.version <= 1 or proposal.previous_version_id is None:
            raise ValueError("adjust_disposition_proposal requires a later version")
        current = self.connection.execute(
            """
            SELECT current_version_id FROM core_alpha_disposition_proposals
            WHERE disposition_proposal_id = ? AND research_case_id = ?
            """,
            (proposal.disposition_proposal_id, proposal.research_case_id),
        ).fetchone()
        if current is None:
            raise RecordNotFoundError(
                f"disposition proposal not found: {proposal.disposition_proposal_id}"
            )
        if current["current_version_id"] != proposal.previous_version_id:
            raise ConcurrencyConflictError("proposal previous_version_id is not current")
        self._validate_proposal_references(proposal)
        self.connection.execute(
            """
            UPDATE core_alpha_disposition_proposal_versions
            SET lifecycle_status = 'superseded'
            WHERE disposition_proposal_version_id = ? AND lifecycle_status = 'current'
            """,
            (proposal.previous_version_id,),
        )
        self._insert_disposition_proposal_version(proposal)
        self.connection.execute(
            """
            UPDATE core_alpha_disposition_proposals
            SET current_version_id = ?
            WHERE disposition_proposal_id = ?
            """,
            (
                proposal.disposition_proposal_version_id,
                proposal.disposition_proposal_id,
            ),
        )

    def get_disposition_proposal_version(
        self,
        disposition_proposal_version_id: str,
    ) -> DispositionProposalVersionResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_disposition_proposal_versions
            WHERE disposition_proposal_version_id = ?
            """,
            (disposition_proposal_version_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"disposition proposal version not found: {disposition_proposal_version_id}"
            )
        return self._disposition_proposal(row)

    def get_current_disposition_proposal(
        self,
        disposition_proposal_id: str,
    ) -> DispositionProposalVersionResponse:
        row = self.connection.execute(
            """
            SELECT current_version_id FROM core_alpha_disposition_proposals
            WHERE disposition_proposal_id = ?
            """,
            (disposition_proposal_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"disposition proposal not found: {disposition_proposal_id}"
            )
        return self.get_disposition_proposal_version(row["current_version_id"])

    def list_current_disposition_proposals_for_case(
        self,
        research_case_id: str,
    ) -> list[DispositionProposalVersionResponse]:
        case = self.connection.execute(
            "SELECT 1 FROM core_alpha_research_cases WHERE research_case_id = ?",
            (research_case_id,),
        ).fetchone()
        if case is None:
            raise RecordNotFoundError(f"research case not found: {research_case_id}")
        rows = self.connection.execute(
            """
            SELECT versions.*
            FROM core_alpha_disposition_proposals proposals
            JOIN core_alpha_disposition_proposal_versions versions
              ON versions.disposition_proposal_version_id = proposals.current_version_id
            WHERE proposals.research_case_id = ?
            ORDER BY versions.created_at, versions.disposition_proposal_version_id
            """,
            (research_case_id,),
        ).fetchall()
        return [self._disposition_proposal(row) for row in rows]

    def accept_disposition_proposal(
        self,
        *,
        accepted_proposal: DispositionProposalVersionResponse,
        disposition: ResearchDispositionResponse,
        expected_proposal_revision: int,
        expected_case_revision: int,
        case_updated_at: datetime,
    ) -> ResearchDispositionResponse:
        current = self.get_current_disposition_proposal(
            accepted_proposal.disposition_proposal_id
        )
        if current.disposition_proposal_version_id != (
            accepted_proposal.disposition_proposal_version_id
        ):
            raise ConcurrencyConflictError("accepted proposal is not current")
        if current.revision != expected_proposal_revision:
            raise ConcurrencyConflictError("proposal revision conflict")
        if accepted_proposal.revision != expected_proposal_revision + 1:
            raise ValueError("accepted proposal revision must advance by one")
        if accepted_proposal.user_decision_status.value != "accepted":
            raise ValueError("accepted proposal must carry accepted user decision status")
        if disposition.source_disposition_proposal_version_id != (
            accepted_proposal.disposition_proposal_version_id
        ):
            raise ValueError("disposition must reference the accepted proposal")
        if disposition.disposition_type != accepted_proposal.proposed_disposition_type:
            raise ValueError("disposition type must match accepted proposal")
        if disposition.judgment_card_version_id != accepted_proposal.judgment_card_version_id:
            raise ValueError("disposition judgment must match accepted proposal")
        if disposition.decision_fitness_id != accepted_proposal.decision_fitness_id:
            raise ValueError("disposition fitness must match accepted proposal")
        self.connection.execute(
            """
            UPDATE core_alpha_disposition_proposal_versions
            SET user_decision_status = ?, revision = ?
            WHERE disposition_proposal_version_id = ? AND revision = ?
            """,
            (
                accepted_proposal.user_decision_status.value,
                accepted_proposal.revision,
                accepted_proposal.disposition_proposal_version_id,
                expected_proposal_revision,
            ),
        )
        self.connection.execute(
            """
            INSERT INTO core_alpha_research_dispositions (
                research_disposition_id, research_case_id,
                source_disposition_proposal_version_id, judgment_card_version_id,
                decision_fitness_id, disposition_type, confirmed_by,
                confirmed_at, supersedes_disposition_id, defer_until,
                observation_condition
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._research_disposition_values(disposition),
        )
        self._update_case_current_disposition(
            disposition.research_case_id,
            expected_revision=expected_case_revision,
            research_disposition_id=disposition.research_disposition_id,
            updated_at=case_updated_at,
        )
        return disposition

    def get_research_disposition(
        self,
        research_disposition_id: str,
    ) -> ResearchDispositionResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_research_dispositions
            WHERE research_disposition_id = ?
            """,
            (research_disposition_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"research disposition not found: {research_disposition_id}"
            )
        return self._research_disposition(row)

    def _validate_judgment_version_payload(
        self,
        *,
        judgment_card: JudgmentCardVersionResponse,
        claims: list[ClaimVersionResponse],
        evidence_links: list[ClaimEvidenceLinkResponse],
        rationales: list[JudgmentRationaleResponse],
        decision_fitness: DecisionFitnessResponse | None,
    ) -> None:
        run = self.connection.execute(
            """
            SELECT research_case_id FROM core_alpha_research_runs
            WHERE research_run_id = ?
            """,
            (judgment_card.research_run_id,),
        ).fetchone()
        if run is None:
            raise RecordNotFoundError(f"research run not found: {judgment_card.research_run_id}")
        if run["research_case_id"] != judgment_card.research_case_id:
            raise ValueError("judgment run must belong to the research case")

        claims_by_id = {claim.claim_version_id: claim for claim in claims}
        if set(judgment_card.claim_version_ids) != set(claims_by_id):
            raise ValueError("judgment claim ids must match supplied claims")
        for claim in claims:
            if claim.judgment_card_version_id != judgment_card.judgment_card_version_id:
                raise ValueError("claim must belong to the judgment version")

        link_ids = {link.claim_evidence_link_id for link in evidence_links}
        for link in evidence_links:
            if link.claim_version_id not in claims_by_id:
                raise ValueError("evidence link references unknown claim")
            use = self.connection.execute(
                """
                SELECT research_run_id, evidence_unit_id, validity_result
                FROM core_alpha_research_evidence_uses
                WHERE research_evidence_use_id = ?
                """,
                (link.research_evidence_use_id,),
            ).fetchone()
            if use is None:
                raise RecordNotFoundError(
                    f"research evidence use not found: {link.research_evidence_use_id}"
                )
            if use["research_run_id"] != judgment_card.research_run_id:
                raise ValueError("evidence use must belong to the judgment run")
            if use["evidence_unit_id"] != link.evidence_unit_id:
                raise ValueError("evidence link unit must match evidence use")
            if use["validity_result"] == "invalid":
                raise ValueError("invalid evidence use cannot be linked to a claim")

        rationales_by_id = {rationale.judgment_rationale_id: rationale for rationale in rationales}
        for claim in claims:
            if claim.judgment_rationale_id is not None:
                rationale = rationales_by_id.get(claim.judgment_rationale_id)
                if rationale is None:
                    raise ValueError("claim rationale is missing")
                if rationale.claim_version_id != claim.claim_version_id:
                    raise ValueError("claim rationale must belong to the claim")
        for rationale in rationales:
            if rationale.claim_version_id not in claims_by_id:
                raise ValueError("rationale references unknown claim")
            if not set(rationale.evidence_link_ids).issubset(link_ids):
                raise ValueError("rationale references unknown evidence link")

        if judgment_card.decision_fitness_id is None:
            if decision_fitness is not None:
                raise ValueError("non-adoptable judgment cannot include decision fitness")
        else:
            if decision_fitness is None:
                raise ValueError("adoptable judgment requires decision fitness")
            if decision_fitness.decision_fitness_id != judgment_card.decision_fitness_id:
                raise ValueError("decision fitness id must match judgment")
            if decision_fitness.judgment_card_version_id != (
                judgment_card.judgment_card_version_id
            ):
                raise ValueError("decision fitness must belong to the judgment")

    def _validate_proposal_references(
        self,
        proposal: DispositionProposalVersionResponse,
    ) -> None:
        judgment = self.get_judgment_card_version(proposal.judgment_card_version_id)
        if judgment.research_case_id != proposal.research_case_id:
            raise ValueError("proposal judgment must belong to the research case")
        if judgment.decision_fitness_id != proposal.decision_fitness_id:
            raise ValueError("proposal decision fitness must match judgment")
        self.get_decision_fitness(proposal.decision_fitness_id)
        for warning_id in proposal.warning_acknowledgement_ids:
            warning = self.get_warning_acknowledgement(warning_id)
            if warning.judgment_card_version_id != proposal.judgment_card_version_id:
                raise ValueError("proposal warning acknowledgement belongs to another judgment")

    def _insert_decision_fitness(self, fitness: DecisionFitnessResponse) -> None:
        self.connection.execute(
            """
            INSERT INTO core_alpha_decision_fitnesses (
                decision_fitness_id, judgment_card_version_id, policy_version,
                allowed_uses_json, forbidden_uses_json, required_conditions_json,
                risk_ceiling_json, escalation_triggers_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._decision_fitness_values(fitness),
        )

    def _insert_disposition_proposal_version(
        self,
        proposal: DispositionProposalVersionResponse,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO core_alpha_disposition_proposal_versions (
                disposition_proposal_version_id, disposition_proposal_id,
                research_case_id, judgment_card_version_id, decision_fitness_id,
                proposed_disposition_type, reason, user_decision_status,
                lifecycle_status, version, revision, created_at,
                warning_acknowledgement_ids_json, previous_version_id, expires_at,
                defer_until, observation_condition
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._disposition_proposal_values(proposal),
        )

    def _update_case_current_disposition(
        self,
        research_case_id: str,
        *,
        expected_revision: int,
        research_disposition_id: str,
        updated_at: datetime,
    ) -> None:
        cursor = self.connection.execute(
            """
            UPDATE core_alpha_research_cases
            SET current_research_disposition_id = ?, updated_at = ?, revision = ?
            WHERE research_case_id = ? AND revision = ?
            """,
            (
                research_disposition_id,
                _utc_iso(updated_at),
                expected_revision + 1,
                research_case_id,
                expected_revision,
            ),
        )
        if cursor.rowcount == 1:
            return
        exists = self.connection.execute(
            "SELECT 1 FROM core_alpha_research_cases WHERE research_case_id = ?",
            (research_case_id,),
        ).fetchone()
        if exists is None:
            raise RecordNotFoundError(f"research case not found: {research_case_id}")
        raise ConcurrencyConflictError(
            f"case revision conflict for {research_case_id}: expected {expected_revision}"
        )

    @staticmethod
    def _judgment_values(judgment: JudgmentCardVersionResponse) -> tuple[Any, ...]:
        return (
            judgment.judgment_card_version_id,
            judgment.judgment_card_id,
            judgment.research_case_id,
            judgment.research_run_id,
            judgment.version,
            judgment.revision,
            _json(judgment.claim_version_ids),
            judgment.summary,
            _json(judgment.uncertainties),
            _json(judgment.evidence_gaps),
            judgment.audit_status.value,
            judgment.validity_status.value,
            judgment.lifecycle_status.value,
            _utc_iso(judgment.created_at),
            judgment.previous_version_id,
            judgment.current_judgment_audit_id,
            judgment.decision_fitness_id,
        )

    @staticmethod
    def _claim_values(claim: ClaimVersionResponse) -> tuple[Any, ...]:
        return (
            claim.claim_version_id,
            claim.claim_id,
            claim.judgment_card_version_id,
            claim.claim_text,
            claim.epistemic_type.value,
            claim.expression_role.value,
            claim.evidence_status.value,
            claim.importance.value,
            claim.confidence_level.value,
            claim.lifecycle_status.value,
            claim.user_attitude.value,
            claim.version,
            _utc_iso(claim.created_at),
            claim.judgment_rationale_id,
            claim.previous_version_id,
        )

    @staticmethod
    def _evidence_link_values(link: ClaimEvidenceLinkResponse) -> tuple[Any, ...]:
        return (
            link.claim_evidence_link_id,
            link.claim_version_id,
            link.research_evidence_use_id,
            link.evidence_unit_id,
            link.evidence_role.value,
            link.support_strength.level.value,
            link.support_strength.reason,
            _utc_iso(link.created_at),
            link.scope_note,
        )

    @staticmethod
    def _rationale_values(rationale: JudgmentRationaleResponse) -> tuple[Any, ...]:
        return (
            rationale.judgment_rationale_id,
            rationale.claim_version_id,
            _json(rationale.rationale_profile.model_dump(mode="json")),
            _json(rationale.evidence_link_ids),
            rationale.reasoning_summary,
            _utc_iso(rationale.created_at),
        )

    @staticmethod
    def _audit_values(audit: JudgmentAuditResponse) -> tuple[Any, ...]:
        return (
            audit.judgment_audit_id,
            audit.judgment_card_version_id,
            audit.audit_policy_version,
            audit.audit_run_status.value,
            _json(audit.finding_ids),
            _utc_iso(audit.created_at),
            audit.gate_result.value if audit.gate_result else None,
            _utc_iso(audit.started_at) if audit.started_at else None,
            _utc_iso(audit.completed_at) if audit.completed_at else None,
        )

    @staticmethod
    def _finding_values(finding: AuditFindingResponse) -> tuple[Any, ...]:
        return (
            finding.audit_finding_id,
            finding.judgment_audit_id,
            _json(finding.affected_claim_version_ids),
            finding.finding_type.code,
            finding.finding_type.registry_version,
            finding.severity.value,
            finding.description,
            finding.supporting_reason,
            finding.policy_version,
            _utc_iso(finding.created_at),
            finding.recommended_revision,
            finding.risk_trigger_condition,
        )

    @staticmethod
    def _decision_fitness_values(fitness: DecisionFitnessResponse) -> tuple[Any, ...]:
        return (
            fitness.decision_fitness_id,
            fitness.judgment_card_version_id,
            fitness.policy_version,
            _json([use.value for use in fitness.allowed_uses]),
            _json([use.value for use in fitness.forbidden_uses]),
            _json(fitness.required_conditions),
            _json(fitness.risk_ceiling.model_dump(mode="json")),
            _json(fitness.escalation_triggers),
            _utc_iso(fitness.created_at),
        )

    @staticmethod
    def _disposition_proposal_values(
        proposal: DispositionProposalVersionResponse,
    ) -> tuple[Any, ...]:
        return (
            proposal.disposition_proposal_version_id,
            proposal.disposition_proposal_id,
            proposal.research_case_id,
            proposal.judgment_card_version_id,
            proposal.decision_fitness_id,
            proposal.proposed_disposition_type.value,
            proposal.reason,
            proposal.user_decision_status.value,
            proposal.lifecycle_status.value,
            proposal.version,
            proposal.revision,
            _utc_iso(proposal.created_at),
            _json(proposal.warning_acknowledgement_ids),
            proposal.previous_version_id,
            _utc_iso(proposal.expires_at) if proposal.expires_at else None,
            _utc_iso(proposal.defer_until) if proposal.defer_until else None,
            proposal.observation_condition,
        )

    @staticmethod
    def _research_disposition_values(
        disposition: ResearchDispositionResponse,
    ) -> tuple[Any, ...]:
        return (
            disposition.research_disposition_id,
            disposition.research_case_id,
            disposition.source_disposition_proposal_version_id,
            disposition.judgment_card_version_id,
            disposition.decision_fitness_id,
            disposition.disposition_type.value,
            disposition.confirmed_by,
            _utc_iso(disposition.confirmed_at),
            disposition.supersedes_disposition_id,
            _utc_iso(disposition.defer_until) if disposition.defer_until else None,
            disposition.observation_condition,
        )

    @staticmethod
    def _judgment(row: sqlite3.Row) -> JudgmentCardVersionResponse:
        return JudgmentCardVersionResponse(
            judgment_card_id=row["judgment_card_id"],
            judgment_card_version_id=row["judgment_card_version_id"],
            research_case_id=row["research_case_id"],
            research_run_id=row["research_run_id"],
            version=row["version"],
            revision=row["revision"],
            claim_version_ids=_load_json(row["claim_version_ids_json"], []),
            summary=row["summary"],
            uncertainties=_load_json(row["uncertainties_json"], []),
            evidence_gaps=_load_json(row["evidence_gaps_json"], []),
            audit_status=row["audit_status"],
            validity_status=row["validity_status"],
            lifecycle_status=row["lifecycle_status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            previous_version_id=row["previous_version_id"],
            current_judgment_audit_id=row["current_judgment_audit_id"],
            decision_fitness_id=row["decision_fitness_id"],
        )

    @staticmethod
    def _claim(row: sqlite3.Row) -> ClaimVersionResponse:
        return ClaimVersionResponse(
            claim_id=row["claim_id"],
            claim_version_id=row["claim_version_id"],
            judgment_card_version_id=row["judgment_card_version_id"],
            claim_text=row["claim_text"],
            epistemic_type=row["epistemic_type"],
            expression_role=row["expression_role"],
            evidence_status=row["evidence_status"],
            importance=row["importance"],
            confidence_level=row["confidence_level"],
            lifecycle_status=row["lifecycle_status"],
            user_attitude=row["user_attitude"],
            version=row["version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            judgment_rationale_id=row["judgment_rationale_id"],
            previous_version_id=row["previous_version_id"],
        )

    @staticmethod
    def _evidence_link(row: sqlite3.Row) -> ClaimEvidenceLinkResponse:
        return ClaimEvidenceLinkResponse(
            claim_evidence_link_id=row["claim_evidence_link_id"],
            claim_version_id=row["claim_version_id"],
            research_evidence_use_id=row["research_evidence_use_id"],
            evidence_unit_id=row["evidence_unit_id"],
            evidence_role=row["evidence_role"],
            support_strength={
                "level": row["support_strength_level"],
                "reason": row["support_strength_reason"],
            },
            created_at=datetime.fromisoformat(row["created_at"]),
            scope_note=row["scope_note"],
        )

    @staticmethod
    def _rationale(row: sqlite3.Row) -> JudgmentRationaleResponse:
        return JudgmentRationaleResponse(
            judgment_rationale_id=row["judgment_rationale_id"],
            claim_version_id=row["claim_version_id"],
            rationale_profile=_load_json(row["rationale_profile_json"], {}),
            evidence_link_ids=_load_json(row["evidence_link_ids_json"], []),
            reasoning_summary=row["reasoning_summary"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _audit(row: sqlite3.Row) -> JudgmentAuditResponse:
        return JudgmentAuditResponse(
            judgment_audit_id=row["judgment_audit_id"],
            judgment_card_version_id=row["judgment_card_version_id"],
            audit_policy_version=row["audit_policy_version"],
            audit_run_status=row["audit_run_status"],
            finding_ids=_load_json(row["finding_ids_json"], []),
            created_at=datetime.fromisoformat(row["created_at"]),
            gate_result=row["gate_result"],
            started_at=_dt(row["started_at"]),
            completed_at=_dt(row["completed_at"]),
        )

    @staticmethod
    def _finding(row: sqlite3.Row) -> AuditFindingResponse:
        return AuditFindingResponse(
            audit_finding_id=row["audit_finding_id"],
            judgment_audit_id=row["judgment_audit_id"],
            affected_claim_version_ids=_load_json(
                row["affected_claim_version_ids_json"],
                [],
            ),
            finding_type=_open_code(
                row["finding_type_code"],
                row["finding_type_registry_version"],
            ),
            severity=row["severity"],
            description=row["description"],
            supporting_reason=row["supporting_reason"],
            policy_version=row["policy_version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            recommended_revision=row["recommended_revision"],
            risk_trigger_condition=row["risk_trigger_condition"],
        )

    def _get_finding_row(self, audit_finding_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_audit_findings WHERE audit_finding_id = ?",
            (audit_finding_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"audit finding not found: {audit_finding_id}")
        return row

    @staticmethod
    def _warning_acknowledgement(row: sqlite3.Row) -> WarningAcknowledgementResponse:
        return WarningAcknowledgementResponse(
            warning_acknowledgement_id=row["warning_acknowledgement_id"],
            audit_finding_id=row["audit_finding_id"],
            judgment_card_version_id=row["judgment_card_version_id"],
            acknowledged_by=row["acknowledged_by"],
            acknowledged_at=datetime.fromisoformat(row["acknowledged_at"]),
            acknowledgement_note=row["acknowledgement_note"],
        )

    @staticmethod
    def _decision_fitness(row: sqlite3.Row) -> DecisionFitnessResponse:
        return DecisionFitnessResponse(
            decision_fitness_id=row["decision_fitness_id"],
            judgment_card_version_id=row["judgment_card_version_id"],
            policy_version=row["policy_version"],
            allowed_uses=_load_json(row["allowed_uses_json"], []),
            forbidden_uses=_load_json(row["forbidden_uses_json"], []),
            required_conditions=_load_json(row["required_conditions_json"], []),
            risk_ceiling=DecisionRiskCeiling.model_validate(
                _load_json(row["risk_ceiling_json"], {}),
            ),
            escalation_triggers=_load_json(row["escalation_triggers_json"], []),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _disposition_proposal(row: sqlite3.Row) -> DispositionProposalVersionResponse:
        return DispositionProposalVersionResponse(
            disposition_proposal_id=row["disposition_proposal_id"],
            disposition_proposal_version_id=row["disposition_proposal_version_id"],
            research_case_id=row["research_case_id"],
            judgment_card_version_id=row["judgment_card_version_id"],
            decision_fitness_id=row["decision_fitness_id"],
            proposed_disposition_type=row["proposed_disposition_type"],
            reason=row["reason"],
            user_decision_status=row["user_decision_status"],
            lifecycle_status=row["lifecycle_status"],
            version=row["version"],
            revision=row["revision"],
            created_at=datetime.fromisoformat(row["created_at"]),
            warning_acknowledgement_ids=_load_json(
                row["warning_acknowledgement_ids_json"],
                [],
            ),
            previous_version_id=row["previous_version_id"],
            expires_at=_dt(row["expires_at"]),
            defer_until=_dt(row["defer_until"]),
            observation_condition=row["observation_condition"],
        )

    @staticmethod
    def _research_disposition(row: sqlite3.Row) -> ResearchDispositionResponse:
        return ResearchDispositionResponse(
            research_disposition_id=row["research_disposition_id"],
            research_case_id=row["research_case_id"],
            source_disposition_proposal_version_id=row[
                "source_disposition_proposal_version_id"
            ],
            judgment_card_version_id=row["judgment_card_version_id"],
            decision_fitness_id=row["decision_fitness_id"],
            disposition_type=row["disposition_type"],
            confirmed_by=row["confirmed_by"],
            confirmed_at=datetime.fromisoformat(row["confirmed_at"]),
            supersedes_disposition_id=row["supersedes_disposition_id"],
            defer_until=_dt(row["defer_until"]),
            observation_condition=row["observation_condition"],
        )


__all__ = ["JudgmentDecisionRepository"]
