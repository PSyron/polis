from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.quality_report_helpers import _proposal_payload, _result, _write_proposal

from polis.evaluation.quality_report import (
    QualityReportError,
    baseline_file_sha256,
    load_quality_report,
    load_threshold_proposal,
    validate_threshold_proposal,
    write_quality_report,
)


def test_pending_proposal_copies_measured_baseline_and_is_not_enforced(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    proposal_path = tmp_path / "proposal.json"
    write_quality_report(_result(), baseline)
    payload = _proposal_payload(baseline)
    _write_proposal(proposal_path, payload)

    proposal = load_threshold_proposal(proposal_path)
    validate_threshold_proposal(proposal, baseline_path=baseline)
    report = load_quality_report(baseline)

    assert proposal.baseline_sha256 == baseline_file_sha256(baseline)
    assert proposal.dataset_sha256 == report.dataset_sha256
    assert proposal.minimum_precision == report.quality_precision
    assert proposal.minimum_recall == report.quality_recall
    assert proposal.minimum_f1 == report.quality_f1
    assert proposal.minimum_span_accuracy == report.quality_span_accuracy
    assert proposal.minimum_correction_accuracy == report.quality_correction_accuracy
    assert proposal.maximum_false_alarm_rate == report.quality_false_alarm_rate
    assert proposal.status == "pending_maintainer_approval"
    assert proposal.enforced is False


def test_proposal_rejects_baseline_byte_drift(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    proposal_path = tmp_path / "proposal.json"
    write_quality_report(_result(), baseline)
    _write_proposal(proposal_path, _proposal_payload(baseline))
    baseline.write_bytes(baseline.read_bytes().replace(b"\n", b"\r\n"))

    with pytest.raises(
        QualityReportError,
        match="threshold proposal baseline_sha256 mismatch",
    ):
        validate_threshold_proposal(
            load_threshold_proposal(proposal_path), baseline_path=baseline
        )


def test_proposal_rejects_baseline_for_foreign_dataset(tmp_path: Path) -> None:
    baseline = tmp_path / "foreign-baseline.json"
    proposal_path = tmp_path / "proposal.json"
    write_quality_report(_result(), baseline)
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    dataset = payload["dataset"]
    assert isinstance(dataset, dict)
    dataset["id"] = "unrelated_dataset"
    _write_proposal(baseline, payload)
    _write_proposal(proposal_path, _proposal_payload(baseline))

    with pytest.raises(QualityReportError, match="active dataset identity mismatch"):
        validate_threshold_proposal(
            load_threshold_proposal(proposal_path), baseline_path=baseline
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("baseline_path", "baseline_path mismatch"),
        ("dataset_sha256", "dataset_sha256 mismatch"),
        ("minimum_precision", "minimum_precision mismatch"),
        ("minimum_recall", "minimum_recall mismatch"),
        ("minimum_f1", "minimum_f1 mismatch"),
        ("minimum_span_accuracy", "minimum_span_accuracy mismatch"),
        ("minimum_correction_accuracy", "minimum_correction_accuracy mismatch"),
        ("maximum_false_alarm_rate", "maximum_false_alarm_rate mismatch"),
        ("status", "status must be pending_maintainer_approval"),
        ("enforced", "must not be enforced"),
    ),
)
def test_proposal_rejects_identity_value_and_policy_drift(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    baseline = tmp_path / "baseline.json"
    proposal_path = tmp_path / "proposal.json"
    write_quality_report(_result(), baseline)
    payload = _proposal_payload(baseline)
    proposed = payload["proposed_thresholds"]
    assert isinstance(proposed, dict)
    if mutation in proposed:
        proposed[mutation] = None
    elif mutation == "baseline_path":
        payload[mutation] = str(tmp_path / "other.json")
    elif mutation == "dataset_sha256":
        payload[mutation] = "e" * 64
    elif mutation == "status":
        payload[mutation] = "approved"
    else:
        payload[mutation] = True
    _write_proposal(proposal_path, payload)

    with pytest.raises(QualityReportError, match=message):
        validate_threshold_proposal(
            load_threshold_proposal(proposal_path), baseline_path=baseline
        )
