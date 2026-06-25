"""Command line report generation for the Core Alpha evaluation gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from metaos.evaluation.core_alpha import (
    CaseExecutionRecord,
    CaseResult,
    GateEvaluation,
    evaluate_default_minimum_slice_gate,
    render_gate_evaluation_markdown,
)


def load_case_execution_records(path: Path) -> list[CaseExecutionRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records_payload = _records_payload(payload)
    return [CaseExecutionRecord.model_validate(record) for record in records_payload]


def build_default_gate_report(
    records: list[CaseExecutionRecord],
) -> tuple[GateEvaluation, str]:
    evaluation = evaluate_default_minimum_slice_gate(records)
    return evaluation, render_gate_evaluation_markdown(evaluation)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Core Alpha Minimum Slice gate report.",
    )
    parser.add_argument(
        "--records",
        type=Path,
        help="JSON file containing CaseExecutionRecord objects, or an object with a records field.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Markdown output path. Defaults to stdout.",
    )
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="Return a non-zero exit code when the gate does not pass.",
    )
    args = parser.parse_args(argv)

    records = load_case_execution_records(args.records) if args.records else []
    evaluation, markdown = build_default_gate_report(records)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)

    if args.fail_on_blocked and evaluation.result != CaseResult.passed:
        return 1
    return 0


def _records_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        return payload["records"]
    raise ValueError("records JSON must be a list or an object with a records list")


if __name__ == "__main__":
    raise SystemExit(main())
