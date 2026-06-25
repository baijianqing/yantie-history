from __future__ import annotations

import json
from datetime import datetime, timezone

from metaos.evaluation.core_alpha import (
    SEVEN_ASSERTION_LAYERS,
    CaseExecutionRecord,
    CaseResult,
    ExecutionProfile,
    LayerAssertionResult,
)
from metaos.evaluation.core_alpha_report import (
    build_default_gate_report,
    load_case_execution_records,
    main,
)


def test_build_default_gate_report_blocks_without_records() -> None:
    evaluation, markdown = build_default_gate_report([])

    assert evaluation.result == CaseResult.failed
    assert not evaluation.is_release_authorized
    assert "Gate result: `failed`" in markdown
    assert "Release authorized: `no`" in markdown
    assert "GC-SRC-001" in markdown


def test_load_case_execution_records_accepts_records_wrapper(tmp_path) -> None:
    record = _record("GC-SRC-001")
    records_path = tmp_path / "records.json"
    records_path.write_text(
        json.dumps({"records": [record.model_dump(mode="json")]}),
        encoding="utf-8",
    )

    loaded = load_case_execution_records(records_path)

    assert loaded == [record]


def test_cli_writes_blocked_report_and_can_fail_on_blocked(tmp_path) -> None:
    output_path = tmp_path / "gate-report.md"

    exit_code = main(["--output", str(output_path), "--fail-on-blocked"])

    assert exit_code == 1
    assert "Gate result: `failed`" in output_path.read_text(encoding="utf-8")


def _record(
    case_id: str,
    *,
    profile: ExecutionProfile = ExecutionProfile.controlled_contract,
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
        executed_at=datetime(2026, 6, 26, tzinfo=timezone.utc),
        layer_results=[
            LayerAssertionResult(
                layer=layer,
                result=CaseResult.passed,
                reason="layer passed",
            )
            for layer in SEVEN_ASSERTION_LAYERS
        ],
        result=CaseResult.passed,
    )
