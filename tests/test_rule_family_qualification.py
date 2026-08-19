from __future__ import annotations

import json
from pathlib import Path

import pytest

from polis.evaluation.rule_family_qualification import (
    QualificationError,
    matrix_digest,
    validate_children_document,
    validate_matrix_document,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs/project/rule-family-qualification-v1.json"


def _matrix() -> dict[str, object]:
    value = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _validate(matrix: dict[str, object]) -> None:
    validate_matrix_document(matrix, ROOT)


def _write_digest(matrix: dict[str, object]) -> None:
    integrity = matrix["integrity"]
    assert isinstance(integrity, dict)
    digest = matrix_digest(matrix)
    integrity["matrix_sha256"] = digest
    if matrix.get("stage") != "approved":
        return
    approval = matrix["approval"]
    rows = matrix["rows"]
    assert isinstance(approval, dict)
    assert isinstance(rows, list)
    approval["bound_matrix_sha256"] = digest
    for raw_row in rows:
        assert isinstance(raw_row, dict)
        decision = raw_row["decision"]
        assert isinstance(decision, dict)
        row_approval = decision["maintainer_approval"]
        assert isinstance(row_approval, dict)
        row_approval["bound_matrix_sha256"] = digest


def _mark_first_row_accepted(matrix: dict[str, object]) -> None:
    rows = matrix["rows"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    decision = row["decision"]
    assert isinstance(decision, dict)
    decision["disposition"] = "accept: deterministic provider-absent"
    decision["child_allowed"] = True


def _approve_matrix(matrix: dict[str, object]) -> str:
    proposal_digest = matrix_digest(matrix)
    matrix["stage"] = "approved"
    matrix["status"] = "approved"
    integrity = matrix["integrity"]
    approval = matrix["approval"]
    rows = matrix["rows"]
    assert isinstance(integrity, dict)
    assert isinstance(approval, dict)
    assert isinstance(rows, list)
    integrity["digest_status"] = "approved"
    integrity["matrix_sha256"] = proposal_digest
    approval.update(
        status="approved",
        approved_by="Paweł Cyroń",
        approved_at="2026-08-19",
        bound_matrix_sha256=proposal_digest,
        child_creation_allowed=True,
    )
    for raw_row in rows:
        assert isinstance(raw_row, dict)
        decision = raw_row["decision"]
        assert isinstance(decision, dict)
        row_approval = decision["maintainer_approval"]
        assert isinstance(row_approval, dict)
        row_approval.update(
            status="approved",
            approved_by="Paweł Cyroń",
            approved_at="2026-08-19",
            bound_matrix_sha256=proposal_digest,
        )
    assert isinstance(proposal_digest, str)
    return proposal_digest


def test_matrix_has_exact_pending_zero_acceptance_state() -> None:
    result: dict[str, object] = validate_matrix_document(_matrix(), ROOT)

    assert result["candidate_count"] == 4
    assert result["accepted_count"] == 0
    assert result["dispositions"] == {"reject: insufficient public evidence": 4}


def test_missing_input_fails_exact_universe_parity() -> None:
    matrix = _matrix()
    universe = matrix["candidate_universe"]
    assert isinstance(universe, dict)
    inputs = universe["inputs"]
    assert isinstance(inputs, list)
    del inputs[0]
    _write_digest(matrix)

    with pytest.raises(QualificationError, match="parity failure"):
        _validate(matrix)


def test_incomplete_accepted_row_cannot_use_follow_up_promise() -> None:
    matrix = _matrix()
    rows = matrix["rows"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    decision = row["decision"]
    assert isinstance(decision, dict)
    decision["disposition"] = "accept: deterministic provider-absent"
    decision["child_allowed"] = True
    _write_digest(matrix)

    with pytest.raises(QualificationError, match="public evidence gaps"):
        _validate(matrix)


def test_fabricated_public_evidence_cannot_admit_a_row() -> None:
    matrix = _matrix()
    rows = matrix["rows"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    decision = row["decision"]
    evidence = row["public_evidence"]
    assert isinstance(decision, dict)
    assert isinstance(evidence, dict)
    decision["disposition"] = "accept: deterministic provider-absent"
    decision["child_allowed"] = True
    evidence["evidence_gaps"] = []
    evidence["executable_risk_evidence"] = ["tests/fake.py"]
    evidence["v4_positive_case_ids"] = [f"fake-positive-{i}" for i in range(8)]
    evidence["v4_hard_negative_case_ids"] = [f"fake-negative-{i}" for i in range(16)]
    evidence["controlled_pair_ids"] = [f"fake-pair-{i}" for i in range(4)]
    evidence["conflict_abstention_case_ids"] = ["fake-control"]
    prioritization = matrix["prioritization"]
    assert isinstance(prioritization, dict)
    prioritization["accepted_row_ids"] = ["rjp-2026-03"]
    prioritization["ranked_rows"] = [{"candidate_id": "rjp-2026-03"}]
    _write_digest(matrix)

    with pytest.raises(QualificationError, match="unknown public evidence case"):
        _validate(matrix)


def test_duplicate_child_mapping_fails() -> None:
    matrix = _matrix()
    _mark_first_row_accepted(matrix)
    _approve_matrix(matrix)
    issue: dict[str, object] = {
        "body": "Qualification row ID: rjp-2026-03",
        "labels": [],
        "milestone": None,
    }

    with pytest.raises(QualificationError, match="exactly one child"):
        validate_children_document(matrix, [issue, issue])


def test_child_for_rejected_row_fails() -> None:
    matrix = _matrix()
    issue = {"body": "Qualification row ID: rjp-2026-03"}

    with pytest.raises(QualificationError, match="rejected/deferred"):
        validate_children_document(matrix, [issue])


def test_non_reproducible_prioritization_fails() -> None:
    matrix = _matrix()
    prioritization = matrix["prioritization"]
    assert isinstance(prioritization, dict)
    prioritization["accepted_row_ids"] = ["unexpected"]
    _write_digest(matrix)

    with pytest.raises(QualificationError, match="prioritization"):
        _validate(matrix)


def test_digest_and_approval_mismatch_fail_closed() -> None:
    digest_matrix = _matrix()
    integrity = digest_matrix["integrity"]
    assert isinstance(integrity, dict)
    integrity["matrix_sha256"] = "0" * 64
    with pytest.raises(QualificationError, match="digest mismatch"):
        _validate(digest_matrix)

    approval_matrix = _matrix()
    approval = approval_matrix["approval"]
    assert isinstance(approval, dict)
    approval["bound_matrix_sha256"] = "0" * 64
    with pytest.raises(QualificationError, match="approval"):
        _validate(approval_matrix)


def test_zero_child_pending_state_is_valid() -> None:
    result = validate_children_document(_matrix(), [])

    assert result == {"accepted_count": 0, "validated_child_ids": []}


def test_live_child_requires_exact_matrix_metadata_when_row_is_accepted() -> None:
    matrix = _matrix()
    _mark_first_row_accepted(matrix)
    _approve_matrix(matrix)
    with pytest.raises(QualificationError, match="missing template"):
        validate_children_document(
            matrix,
            [
                {
                    "body": "Qualification row ID: rjp-2026-03",
                    "labels": [],
                    "milestone": None,
                }
            ],
        )


def test_pending_matrix_with_accepted_row_fails_even_without_a_child() -> None:
    matrix = _matrix()
    _mark_first_row_accepted(matrix)
    matrix["stage"] = "pre-approval"
    matrix["status"] = "pending-maintainer-review"
    approval = matrix["approval"]
    rows = matrix["rows"]
    assert isinstance(approval, dict)
    assert isinstance(rows, list)
    approval.update(
        status="pending",
        approved_by=None,
        approved_at=None,
        bound_matrix_sha256=None,
        child_creation_allowed=False,
    )
    for raw_row in rows:
        assert isinstance(raw_row, dict)
        decision = raw_row["decision"]
        assert isinstance(decision, dict)
        row_approval = decision["maintainer_approval"]
        assert isinstance(row_approval, dict)
        row_approval.update(
            status="pending",
            approved_by=None,
            approved_at=None,
            bound_matrix_sha256=None,
        )
    _write_digest(matrix)

    with pytest.raises(QualificationError, match="final maintainer approval"):
        validate_children_document(matrix, [])


@pytest.mark.parametrize("digest_marker", [None, "0" * 64])
def test_approved_child_requires_exact_matrix_digest_marker(
    digest_marker: str | None,
) -> None:
    matrix = _matrix()
    _mark_first_row_accepted(matrix)
    _approve_matrix(matrix)
    body = "Qualification row ID: rjp-2026-03"
    if digest_marker is not None:
        body += f"\nQualification matrix SHA-256: {digest_marker}"

    with pytest.raises(QualificationError, match="matrix sha-256"):
        validate_children_document(
            matrix,
            [{"body": body, "labels": [], "milestone": None}],
        )


def test_matrix_digest_is_stable_for_json_round_trip() -> None:
    matrix = _matrix()
    round_tripped = json.loads(json.dumps(matrix, ensure_ascii=False))

    assert matrix_digest(matrix) == matrix_digest(round_tripped)


def test_proposal_digest_is_stable_when_maintainer_attests_exact_content() -> None:
    matrix = _matrix()
    proposal_digest = matrix_digest(matrix)
    matrix["stage"] = "approved"
    matrix["status"] = "approved"
    integrity = matrix["integrity"]
    assert isinstance(integrity, dict)
    integrity["digest_status"] = "approved"
    approval = matrix["approval"]
    assert isinstance(approval, dict)
    approval.update(
        {
            "status": "approved",
            "approved_by": "Paweł Cyroń",
            "approved_at": "2026-08-19",
            "bound_matrix_sha256": proposal_digest,
            "child_creation_allowed": True,
        }
    )
    rows = matrix["rows"]
    assert isinstance(rows, list)
    for raw_row in rows:
        assert isinstance(raw_row, dict)
        decision = raw_row["decision"]
        assert isinstance(decision, dict)
        row_approval = decision["maintainer_approval"]
        assert isinstance(row_approval, dict)
        row_approval.update(
            {
                "status": "approved",
                "approved_by": "Paweł Cyroń",
                "approved_at": "2026-08-19",
                "bound_matrix_sha256": proposal_digest,
            }
        )

    assert matrix_digest(matrix) == proposal_digest
    result = validate_matrix_document(matrix, ROOT)
    assert result["matrix_sha256"] == proposal_digest
