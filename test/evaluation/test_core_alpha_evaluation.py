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
    RepeatPolicy,
    aggregate_case_result,
    evaluate_minimum_slice_gate,
    minimum_slice_case_ids,
    minimum_slice_suite_for_case,
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
