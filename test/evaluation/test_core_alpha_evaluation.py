from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from metaos.evaluation.core_alpha import (
    SEVEN_ASSERTION_LAYERS,
    CaseExecutionRecord,
    CaseManifestEntry,
    CaseResult,
    ExecutionProfile,
    LayerAssertionResult,
    MinimumSuite,
    ProfileRequirement,
    RepeatPolicy,
    aggregate_case_result,
    default_minimum_slice_manifest,
    evaluate_default_minimum_slice_gate,
    evaluate_minimum_slice_gate,
    minimum_slice_case_ids,
    minimum_slice_suite_for_case,
    render_gate_evaluation_markdown,
    validate_minimum_slice_manifest,
)


def test_minimum_slice_case_ids_match_frozen_suite_counts() -> None:
    case_ids = minimum_slice_case_ids()

    assert len(case_ids) == 51
    assert len(set(case_ids)) == 51
    assert sum(minimum_slice_suite_for_case(case_id) == MinimumSuite.semantic for case_id in case_ids) == 37
    assert (
        sum(
            minimum_slice_suite_for_case(case_id) == MinimumSuite.command_reliability
            for case_id in case_ids
        )
        == 9
    )
    assert (
        sum(
            minimum_slice_suite_for_case(case_id) == MinimumSuite.privacy_diagnostics
            for case_id in case_ids
        )
        == 3
    )
    assert (
        sum(
            minimum_slice_suite_for_case(case_id) == MinimumSuite.ui_end_to_end
            for case_id in case_ids
        )
        == 2
    )


def test_manifest_validation_rejects_missing_or_unexpected_cases() -> None:
    manifest = [_entry(case_id) for case_id in minimum_slice_case_ids()[:-1]]

    with pytest.raises(ValueError, match="missing"):
        validate_minimum_slice_manifest(manifest)

    with pytest.raises(ValueError, match="unexpected"):
        validate_minimum_slice_manifest(manifest + [_entry("GC-UNKNOWN-001")])


def test_default_minimum_slice_manifest_expands_profiles_and_fixtures() -> None:
    manifest = default_minimum_slice_manifest()
    by_case_id = {entry.case_id: entry for entry in manifest}

    validate_minimum_slice_manifest(manifest)

    assert len(manifest) == 51
    assert by_case_id["GC-SRC-001"].fixture_refs == ["FX-KNOW-001", "FX-KNOW-002"]
    assert by_case_id["GC-RET-001"].profile_requirements == [
        ProfileRequirement(
            execution_profile=ExecutionProfile.integrated_retrieval,
            repeat_policy=RepeatPolicy.three_runs,
        )
    ]
    assert by_case_id["GC-RET-004"].profile_requirements == [
        ProfileRequirement(
            execution_profile=ExecutionProfile.controlled_contract,
            repeat_policy=RepeatPolicy.once,
        ),
        ProfileRequirement(
            execution_profile=ExecutionProfile.integrated_retrieval,
            repeat_policy=RepeatPolicy.three_runs,
        ),
    ]
    assert by_case_id["GC-DEC-001"].profile_requirements == [
        ProfileRequirement(
            execution_profile=ExecutionProfile.controlled_contract,
            repeat_policy=RepeatPolicy.once,
        ),
        ProfileRequirement(
            execution_profile=ExecutionProfile.end_to_end,
            repeat_policy=RepeatPolicy.three_runs,
        ),
    ]
    assert by_case_id["GC-UI-001"].start_layer == "outcome_api"


def test_case_execution_record_requires_exactly_seven_layers() -> None:
    record = _record("GC-SRC-001", result=CaseResult.passed)

    assert len(record.layer_results) == 7

    with pytest.raises(ValidationError):
        CaseExecutionRecord(
            **{
                **record.model_dump(mode="python"),
                "layer_results": record.layer_results[:-1],
            }
        )

    with pytest.raises(ValidationError, match="review metadata"):
        _record("GC-SRC-001", result=CaseResult.inconclusive, reviewer_id=None)


def test_profile_aggregation_requires_all_three_runs_for_three_run_cases() -> None:
    entry = _entry(
        "GC-RET-001",
        repeat_policy=RepeatPolicy.three_runs,
        profiles=[ExecutionProfile.integrated_retrieval],
    )

    partial = aggregate_case_result(
        entry,
        [
            _record("GC-RET-001", profile=ExecutionProfile.integrated_retrieval),
            _record("GC-RET-001", profile=ExecutionProfile.integrated_retrieval),
        ],
    )
    complete = aggregate_case_result(
        entry,
        [
            _record("GC-RET-001", profile=ExecutionProfile.integrated_retrieval),
            _record("GC-RET-001", profile=ExecutionProfile.integrated_retrieval),
            _record("GC-RET-001", profile=ExecutionProfile.integrated_retrieval),
        ],
    )
    failed = aggregate_case_result(
        entry,
        [
            _record("GC-RET-001", profile=ExecutionProfile.integrated_retrieval),
            _record(
                "GC-RET-001",
                profile=ExecutionProfile.integrated_retrieval,
                result=CaseResult.failed,
            ),
            _record("GC-RET-001", profile=ExecutionProfile.integrated_retrieval),
        ],
    )

    assert partial.result == CaseResult.inconclusive
    assert complete.result == CaseResult.passed
    assert failed.result == CaseResult.failed


def test_gate_blocks_when_any_case_is_missing_or_not_run() -> None:
    manifest = [_entry(case_id) for case_id in minimum_slice_case_ids()]

    evaluation = evaluate_minimum_slice_gate(manifest, records=[])

    assert evaluation.result == CaseResult.failed
    assert not evaluation.is_release_authorized
    assert evaluation.missing_case_ids == []
    assert all(suite.result == CaseResult.failed for suite in evaluation.suite_results)


def test_default_gate_report_blocks_when_all_cases_are_not_run() -> None:
    evaluation = evaluate_default_minimum_slice_gate(records=[])
    markdown = render_gate_evaluation_markdown(evaluation)

    assert evaluation.result == CaseResult.failed
    assert not evaluation.is_release_authorized
    assert "Release authorized: `no`" in markdown
    assert "semantic" in markdown
    assert "GC-SRC-001" in markdown


def test_default_gate_passes_only_with_all_profile_records() -> None:
    manifest = default_minimum_slice_manifest()
    records: list[CaseExecutionRecord] = []
    for entry in manifest:
        for requirement in entry.profile_requirements or []:
            required_count = 1 if requirement.repeat_policy == RepeatPolicy.once else 3
            records.extend(
                _record(entry.case_id, profile=requirement.execution_profile)
                for _ in range(required_count)
            )

    evaluation = evaluate_minimum_slice_gate(manifest, records)

    assert evaluation.result == CaseResult.passed
    assert evaluation.is_release_authorized


def test_gate_passes_only_when_all_required_records_pass() -> None:
    manifest = [_entry(case_id) for case_id in minimum_slice_case_ids()]
    records = [_record(case_id) for case_id in minimum_slice_case_ids()]

    evaluation = evaluate_minimum_slice_gate(manifest, records)

    assert evaluation.result == CaseResult.passed
    assert evaluation.is_release_authorized
    assert all(suite.result == CaseResult.passed for suite in evaluation.suite_results)


def _entry(
    case_id: str,
    *,
    repeat_policy: RepeatPolicy = RepeatPolicy.once,
    profiles: list[ExecutionProfile] | None = None,
) -> CaseManifestEntry:
    return CaseManifestEntry(
        case_id=case_id,
        repeat_policy=repeat_policy,
        execution_profiles=profiles or [ExecutionProfile.controlled_contract],
        fixture_refs=["FX-KNOW-001"],
        metric_ids=["M-GC-PASS"],
        start_layer="source_resolution",
    )


def _record(
    case_id: str,
    *,
    profile: ExecutionProfile = ExecutionProfile.controlled_contract,
    result: CaseResult = CaseResult.passed,
    reviewer_id: str | None = "reviewer_1",
) -> CaseExecutionRecord:
    return CaseExecutionRecord(
        case_id=case_id,
        execution_profile=profile,
        fixture_version="fixture-v1",
        implementation_commit="commit_1",
        document_versions={
            "business": "A0-DOC-001-R7.1",
            "domain": "A0-DOC-003-R1.2.2",
            "api": "A0-DOC-004-R1.2.1",
            "retrieval": "A0-DOC-006-R1.3",
        },
        executed_at=datetime.now(timezone.utc),
        layer_results=[
            LayerAssertionResult(
                layer=layer,
                result=result,
                reason="layer passed" if result == CaseResult.passed else "layer failed",
            )
            for layer in SEVEN_ASSERTION_LAYERS
        ],
        result=result,
        reviewer_id=reviewer_id,
        review_basis="manual review" if reviewer_id else None,
    )
