"""Executable contracts for the Core Alpha Golden Case gate."""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from metaos.core_alpha.contracts.common import StrictContractModel, UtcDateTime


SEVEN_ASSERTION_LAYERS = (
    "source_resolution",
    "source_routing",
    "retrieval_execution",
    "evidence_use",
    "judgment",
    "audit_and_fitness",
    "outcome_api",
)


class CaseResult(str, Enum):
    passed = "passed"
    failed = "failed"
    inconclusive = "inconclusive"
    not_run = "not_run"


class ExecutionProfile(str, Enum):
    controlled_contract = "controlled_contract"
    integrated_retrieval = "integrated_retrieval"
    end_to_end = "end_to_end"


class RepeatPolicy(str, Enum):
    once = "once"
    three_runs = "three_runs"


class MinimumSuite(str, Enum):
    semantic = "semantic"
    command_reliability = "command_reliability"
    privacy_diagnostics = "privacy_diagnostics"
    ui_end_to_end = "ui_end_to_end"


class ProfileRequirement(StrictContractModel):
    execution_profile: ExecutionProfile
    repeat_policy: RepeatPolicy


class LayerAssertionResult(StrictContractModel):
    layer: str
    result: CaseResult
    reason: str

    @model_validator(mode="after")
    def validate_layer(self) -> "LayerAssertionResult":
        if self.layer not in SEVEN_ASSERTION_LAYERS:
            raise ValueError(f"unknown assertion layer: {self.layer}")
        if self.result == CaseResult.not_run and not self.reason:
            raise ValueError("not_run layer assertions require a reason")
        return self


class CaseManifestEntry(StrictContractModel):
    case_id: str
    delivery_layer: str = "minimum_slice"
    severity: str = "blocking"
    profile_requirements: list[ProfileRequirement] | None = None
    repeat_policy: RepeatPolicy | None = None
    execution_profiles: list[ExecutionProfile] | None = None
    fixture_refs: list[str] = Field(min_length=1)
    metric_ids: list[str] = Field(min_length=1)
    start_layer: str

    @model_validator(mode="after")
    def validate_manifest_entry(self) -> "CaseManifestEntry":
        if self.delivery_layer != "minimum_slice":
            raise ValueError("this runner only accepts minimum_slice cases")
        if self.severity != "blocking":
            raise ValueError("minimum_slice cases must be blocking")
        if self.profile_requirements is None:
            if self.repeat_policy is None or self.execution_profiles is None:
                raise ValueError(
                    "manifest entries require profile_requirements or legacy "
                    "repeat_policy + execution_profiles"
                )
            self.profile_requirements = [
                ProfileRequirement(
                    execution_profile=profile,
                    repeat_policy=self.repeat_policy,
                )
                for profile in self.execution_profiles
            ]
        profile_ids = [
            requirement.execution_profile
            for requirement in self.profile_requirements
        ]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("execution profiles must be unique")
        if self.start_layer not in SEVEN_ASSERTION_LAYERS:
            raise ValueError(f"unknown start layer: {self.start_layer}")
        return self


class CaseExecutionRecord(StrictContractModel):
    case_id: str
    execution_profile: ExecutionProfile
    fixture_version: str
    implementation_commit: str
    document_versions: dict[str, str]
    executed_at: UtcDateTime
    layer_results: list[LayerAssertionResult] = Field(min_length=7, max_length=7)
    result: CaseResult
    reviewer_id: str | None = None
    review_basis: str | None = None

    @model_validator(mode="after")
    def validate_execution_record(self) -> "CaseExecutionRecord":
        layers = [layer_result.layer for layer_result in self.layer_results]
        if set(layers) != set(SEVEN_ASSERTION_LAYERS):
            raise ValueError("execution records must contain exactly the seven assertion layers")
        if len(layers) != len(set(layers)):
            raise ValueError("layer assertion results must be unique")
        if self.result == CaseResult.passed:
            failing_layers = [
                layer
                for layer in self.layer_results
                if layer.result != CaseResult.passed
            ]
            if failing_layers:
                raise ValueError("passed records cannot contain failing layer assertions")
        if self.result in {CaseResult.failed, CaseResult.inconclusive}:
            if self.reviewer_id is None or self.review_basis is None:
                raise ValueError("failed and inconclusive records require review metadata")
        return self


class ProfileEvaluation(StrictContractModel):
    case_id: str
    execution_profile: ExecutionProfile
    result: CaseResult
    record_count: int
    reason: str


class CaseEvaluation(StrictContractModel):
    case_id: str
    suite: MinimumSuite
    result: CaseResult
    profile_results: list[ProfileEvaluation]


class SuiteEvaluation(StrictContractModel):
    suite: MinimumSuite
    result: CaseResult
    passed_cases: int
    total_cases: int
    blocking_case_ids: list[str]


class GateEvaluation(StrictContractModel):
    result: CaseResult
    suite_results: list[SuiteEvaluation]
    case_results: list[CaseEvaluation]
    missing_case_ids: list[str]
    unexpected_case_ids: list[str]

    @property
    def is_release_authorized(self) -> bool:
        return self.result == CaseResult.passed


def minimum_slice_case_ids() -> tuple[str, ...]:
    return (
        *_range_ids("GC-SRC", 1, 8),
        *_range_ids("GC-RET", 1, 14),
        *_range_ids("GC-MODE", 1, 3),
        *_range_ids("GC-JDG", 1, 8),
        *_range_ids("GC-DEC", 1, 4),
        *_range_ids("GC-API", 1, 3),
        *_range_ids("GC-CMD", 1, 5),
        "GC-OUT-001",
        *_range_ids("GC-EGR", 1, 3),
        *_range_ids("GC-UI", 1, 2),
    )


def default_minimum_slice_manifest() -> list[CaseManifestEntry]:
    entries = [
        CaseManifestEntry(
            case_id=case_id,
            profile_requirements=_default_profile_requirements(case_id),
            fixture_refs=_default_fixture_refs(case_id),
            metric_ids=_default_metric_ids(case_id),
            start_layer=_default_start_layer(case_id),
        )
        for case_id in minimum_slice_case_ids()
    ]
    validate_minimum_slice_manifest(entries)
    return entries


def minimum_slice_suite_for_case(case_id: str) -> MinimumSuite:
    prefix = _case_prefix(case_id)
    if prefix in {"GC-SRC", "GC-RET", "GC-MODE", "GC-JDG", "GC-DEC"}:
        return MinimumSuite.semantic
    if prefix in {"GC-API", "GC-CMD", "GC-OUT"}:
        return MinimumSuite.command_reliability
    if prefix == "GC-EGR":
        return MinimumSuite.privacy_diagnostics
    if prefix == "GC-UI":
        return MinimumSuite.ui_end_to_end
    raise ValueError(f"unknown minimum slice case id: {case_id}")


def validate_minimum_slice_manifest(entries: list[CaseManifestEntry]) -> None:
    expected = set(minimum_slice_case_ids())
    actual = {entry.case_id for entry in entries}
    if len(actual) != len(entries):
        raise ValueError("minimum slice manifest contains duplicate case ids")
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        raise ValueError(
            "minimum slice manifest case ids do not match the frozen evaluation set: "
            f"missing={missing}, unexpected={unexpected}"
        )


def aggregate_case_result(
    entry: CaseManifestEntry,
    records: list[CaseExecutionRecord],
) -> CaseEvaluation:
    profile_results = [
        _aggregate_profile(
            case_id=entry.case_id,
            profile=requirement.execution_profile,
            repeat_policy=requirement.repeat_policy,
            records=[
                record
                for record in records
                if record.case_id == entry.case_id
                and record.execution_profile == requirement.execution_profile
            ],
        )
        for requirement in entry.profile_requirements or []
    ]
    result = _worst_result(profile.result for profile in profile_results)
    return CaseEvaluation(
        case_id=entry.case_id,
        suite=minimum_slice_suite_for_case(entry.case_id),
        result=result,
        profile_results=profile_results,
    )


def evaluate_minimum_slice_gate(
    manifest: list[CaseManifestEntry],
    records: list[CaseExecutionRecord],
) -> GateEvaluation:
    expected = set(minimum_slice_case_ids())
    manifest_by_id = {entry.case_id: entry for entry in manifest}
    missing = sorted(expected - set(manifest_by_id))
    unexpected = sorted(set(manifest_by_id) - expected)
    case_results = [
        aggregate_case_result(entry, records)
        for entry in sorted(manifest, key=lambda item: item.case_id)
        if entry.case_id in expected
    ]
    suite_results: list[SuiteEvaluation] = []
    for suite in MinimumSuite:
        suite_cases = [
            case_result
            for case_result in case_results
            if case_result.suite == suite
        ]
        total_expected = sum(
            minimum_slice_suite_for_case(case_id) == suite for case_id in expected
        )
        blocking_case_ids = [
            case_result.case_id
            for case_result in suite_cases
            if case_result.result != CaseResult.passed
        ]
        present_passed = sum(
            case_result.result == CaseResult.passed for case_result in suite_cases
        )
        missing_for_suite = [
            case_id
            for case_id in missing
            if minimum_slice_suite_for_case(case_id) == suite
        ]
        blocking_case_ids.extend(missing_for_suite)
        suite_results.append(
            SuiteEvaluation(
                suite=suite,
                result=CaseResult.passed if not blocking_case_ids else CaseResult.failed,
                passed_cases=present_passed,
                total_cases=total_expected,
                blocking_case_ids=sorted(blocking_case_ids),
            )
        )
    gate_result = (
        CaseResult.passed
        if not missing
        and not unexpected
        and all(suite.result == CaseResult.passed for suite in suite_results)
        else CaseResult.failed
    )
    return GateEvaluation(
        result=gate_result,
        suite_results=suite_results,
        case_results=case_results,
        missing_case_ids=missing,
        unexpected_case_ids=unexpected,
    )


def evaluate_default_minimum_slice_gate(
    records: list[CaseExecutionRecord],
) -> GateEvaluation:
    return evaluate_minimum_slice_gate(default_minimum_slice_manifest(), records)


def render_gate_evaluation_markdown(evaluation: GateEvaluation) -> str:
    lines = [
        "# Core Alpha Minimum Slice Gate Report",
        "",
        f"Gate result: `{evaluation.result.value}`",
        f"Release authorized: `{'yes' if evaluation.is_release_authorized else 'no'}`",
        "",
        "## Suites",
        "",
        "| Suite | Result | Passed / Total | Blocking cases |",
        "| --- | --- | ---: | --- |",
    ]
    for suite in evaluation.suite_results:
        blocking_cases = ", ".join(suite.blocking_case_ids) or "-"
        lines.append(
            "| "
            f"{suite.suite.value} | "
            f"`{suite.result.value}` | "
            f"{suite.passed_cases} / {suite.total_cases} | "
            f"{blocking_cases} |"
        )
    if evaluation.missing_case_ids or evaluation.unexpected_case_ids:
        lines.extend(
            [
                "",
                "## Manifest Issues",
                "",
                f"- Missing: {', '.join(evaluation.missing_case_ids) or '-'}",
                f"- Unexpected: {', '.join(evaluation.unexpected_case_ids) or '-'}",
            ]
        )
    return "\n".join(lines) + "\n"


def _aggregate_profile(
    *,
    case_id: str,
    profile: ExecutionProfile,
    repeat_policy: RepeatPolicy,
    records: list[CaseExecutionRecord],
) -> ProfileEvaluation:
    required_count = 1 if repeat_policy == RepeatPolicy.once else 3
    if not records:
        return ProfileEvaluation(
            case_id=case_id,
            execution_profile=profile,
            result=CaseResult.not_run,
            record_count=0,
            reason="No execution records were supplied for this profile.",
        )
    if any(record.result == CaseResult.failed for record in records):
        return ProfileEvaluation(
            case_id=case_id,
            execution_profile=profile,
            result=CaseResult.failed,
            record_count=len(records),
            reason="At least one execution record failed.",
        )
    if any(record.result == CaseResult.inconclusive for record in records):
        return ProfileEvaluation(
            case_id=case_id,
            execution_profile=profile,
            result=CaseResult.inconclusive,
            record_count=len(records),
            reason="At least one execution record was inconclusive.",
        )
    if len(records) < required_count:
        return ProfileEvaluation(
            case_id=case_id,
            execution_profile=profile,
            result=CaseResult.inconclusive,
            record_count=len(records),
            reason=f"Expected {required_count} execution records, got {len(records)}.",
        )
    if any(record.result == CaseResult.not_run for record in records):
        result = (
            CaseResult.not_run
            if all(record.result == CaseResult.not_run for record in records)
            else CaseResult.inconclusive
        )
        return ProfileEvaluation(
            case_id=case_id,
            execution_profile=profile,
            result=result,
            record_count=len(records),
            reason="One or more execution records were not run.",
        )
    return ProfileEvaluation(
        case_id=case_id,
        execution_profile=profile,
        result=CaseResult.passed,
        record_count=len(records),
        reason="All required execution records passed.",
    )


def _worst_result(results: Any) -> CaseResult:
    severity = {
        CaseResult.passed: 0,
        CaseResult.not_run: 1,
        CaseResult.inconclusive: 2,
        CaseResult.failed: 3,
    }
    return max(results, key=lambda result: severity[result])


def _range_ids(prefix: str, start: int, end: int) -> tuple[str, ...]:
    return tuple(f"{prefix}-{index:03d}" for index in range(start, end + 1))


def _case_prefix(case_id: str) -> str:
    parts = case_id.split("-")
    if len(parts) != 3:
        raise ValueError(f"invalid case id: {case_id}")
    return f"{parts[0]}-{parts[1]}"


def _default_profile_requirements(case_id: str) -> list[ProfileRequirement]:
    requirements: list[ProfileRequirement] = []
    if case_id in _controlled_contract_case_ids():
        requirements.append(
            ProfileRequirement(
                execution_profile=ExecutionProfile.controlled_contract,
                repeat_policy=RepeatPolicy.once,
            )
        )
    if case_id in _integrated_retrieval_case_ids():
        requirements.append(
            ProfileRequirement(
                execution_profile=ExecutionProfile.integrated_retrieval,
                repeat_policy=RepeatPolicy.three_runs,
            )
        )
    if case_id in _end_to_end_case_ids():
        requirements.append(
            ProfileRequirement(
                execution_profile=ExecutionProfile.end_to_end,
                repeat_policy=RepeatPolicy.three_runs,
            )
        )
    if not requirements:
        raise ValueError(f"no execution profile requirements configured for {case_id}")
    return requirements


def _default_fixture_refs(case_id: str) -> list[str]:
    fixtures_by_case = {
        "GC-SRC-001": ["FX-KNOW-001", "FX-KNOW-002"],
        "GC-SRC-002": ["FX-KNOW-001", "FX-KNOW-002"],
        "GC-SRC-003": ["FX-KNOW-003"],
        "GC-SRC-004": ["FX-KNOW-001", "FX-KNOW-002"],
        "GC-SRC-005": ["FX-KNOW-005"],
        "GC-SRC-006": ["FX-KNOW-006"],
        "GC-SRC-007": ["FX-KNOW-009"],
        "GC-SRC-008": ["FX-KNOW-009"],
        "GC-RET-001": ["FX-KNOW-001", "FX-KNOW-002"],
        "GC-RET-002": ["FX-KNOW-010"],
        "GC-RET-003": ["FX-KNOW-007"],
        "GC-RET-004": ["FX-KNOW-008"],
        "GC-RET-005": ["FX-KNOW-011"],
        "GC-RET-006": ["FX-KNOW-011"],
        "GC-RET-007": ["FX-KNOW-012"],
        "GC-RET-008": ["FX-KNOW-013"],
        "GC-RET-009": ["FX-KNOW-013"],
        "GC-RET-010": ["FX-KNOW-013"],
        "GC-RET-011": ["FX-KNOW-014"],
        "GC-RET-012": ["FX-KNOW-004"],
        "GC-RET-013": ["FX-KNOW-001"],
        "GC-RET-014": ["FX-KNOW-001", "FX-KNOW-002", "FX-KNOW-003"],
        "GC-MODE-001": ["FX-KNOW-004"],
        "GC-MODE-002": ["FX-KNOW-004"],
        "GC-MODE-003": ["FX-KNOW-001", "FX-KNOW-002", "FX-KNOW-003"],
        "GC-JDG-001": ["FX-STATE-001", "FX-STATE-002"],
        "GC-JDG-002": ["FX-STATE-001"],
        "GC-JDG-003": ["FX-STATE-001"],
        "GC-JDG-004": ["FX-STATE-001", "FX-KNOW-004"],
        "GC-JDG-005": ["FX-STATE-001", "FX-STATE-002"],
        "GC-JDG-006": ["FX-STATE-001"],
        "GC-JDG-007": ["FX-STATE-001", "FX-KNOW-012"],
        "GC-JDG-008": ["FX-STATE-001", "FX-STATE-002"],
        "GC-DEC-001": ["FX-STATE-001"],
        "GC-DEC-002": ["FX-STATE-001"],
        "GC-DEC-003": ["FX-STATE-001"],
        "GC-DEC-004": ["FX-STATE-001"],
        "GC-API-001": ["FX-CMD-001"],
        "GC-API-002": ["FX-CMD-001"],
        "GC-API-003": ["FX-CMD-001"],
        "GC-CMD-001": ["FX-CMD-001"],
        "GC-CMD-002": ["FX-CMD-001"],
        "GC-CMD-003": ["FX-CMD-001"],
        "GC-CMD-004": ["FX-CMD-001"],
        "GC-CMD-005": ["FX-CMD-001"],
        "GC-OUT-001": ["FX-CMD-001"],
        "GC-EGR-001": ["FX-EGR-001"],
        "GC-EGR-002": ["FX-EGR-001"],
        "GC-EGR-003": ["FX-EGR-001"],
        "GC-UI-001": ["FX-UI-001"],
        "GC-UI-002": ["FX-UI-001"],
    }
    return fixtures_by_case[case_id]


def _default_metric_ids(case_id: str) -> list[str]:
    prefix = _case_prefix(case_id)
    metric_by_prefix = {
        "GC-SRC": "M-SRC-REQ",
        "GC-RET": "M-EVD-TRACE",
        "GC-MODE": "M-COUNTER",
        "GC-JDG": "M-AUDIT",
        "GC-DEC": "M-DISPOSITION",
        "GC-API": "M-API",
        "GC-CMD": "M-IDEMPOTENCY",
        "GC-OUT": "M-OUTCOME",
        "GC-EGR": "M-EGRESS-VIOLATION",
        "GC-UI": "M-UI-STATE",
    }
    return ["M-GC-PASS", metric_by_prefix[prefix]]


def _default_start_layer(case_id: str) -> str:
    prefix = _case_prefix(case_id)
    start_layer_by_prefix = {
        "GC-SRC": "source_resolution",
        "GC-RET": "retrieval_execution",
        "GC-MODE": "retrieval_execution",
        "GC-JDG": "judgment",
        "GC-DEC": "outcome_api",
        "GC-API": "outcome_api",
        "GC-CMD": "outcome_api",
        "GC-OUT": "outcome_api",
        "GC-EGR": "outcome_api",
        "GC-UI": "outcome_api",
    }
    return start_layer_by_prefix[prefix]


def _controlled_contract_case_ids() -> set[str]:
    return {
        "GC-SRC-006",
        "GC-SRC-008",
        *_range_ids("GC-RET", 2, 7),
        *_range_ids("GC-RET", 11, 13),
        *_range_ids("GC-JDG", 1, 8),
        *_range_ids("GC-DEC", 1, 4),
        *_range_ids("GC-API", 1, 3),
        *_range_ids("GC-CMD", 1, 5),
        "GC-OUT-001",
        *_range_ids("GC-EGR", 1, 3),
    }


def _integrated_retrieval_case_ids() -> set[str]:
    return {
        *_range_ids("GC-SRC", 1, 5),
        "GC-SRC-007",
        "GC-RET-001",
        "GC-RET-004",
        *_range_ids("GC-RET", 8, 14),
        *_range_ids("GC-MODE", 1, 3),
        "GC-JDG-004",
        "GC-JDG-007",
    }


def _end_to_end_case_ids() -> set[str]:
    return {
        *_range_ids("GC-DEC", 1, 4),
        "GC-OUT-001",
        *_range_ids("GC-EGR", 1, 3),
        *_range_ids("GC-UI", 1, 2),
    }
