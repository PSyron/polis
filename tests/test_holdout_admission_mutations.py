from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.holdout_admission_fixtures import canonical_digest, external_evidence
from tests.holdout_test_helpers import JsonValue

from polis.evaluation.holdout_admission import load_external_admission
from polis.evaluation.holdout_models import HoldoutAdmissionError


@pytest.mark.parametrize(
    ("document", "field", "value"),
    [
        ("merge", "evaluated_source_sha", "f" * 40),
        ("merge", "evaluated_source_tree_sha256", "f" * 40),
        ("authorization", "repository", "attacker/private"),
        ("authorization", "issue_number", 244),
        ("authorization", "comment_id", 2),
        (
            "authorization",
            "comment_url",
            "https://github.com/PSyron/polis/issues/243#issuecomment-2",
        ),
        ("authorization", "author", "attacker"),
        ("authorization", "created_at", "2026-08-08T20:00:00Z"),
        ("authorization", "body", "run_authorization=approved"),
        ("authorization", "evaluated_source_sha", "f" * 40),
        ("authorization", "config_sha256", "f" * 64),
        ("authorization", "dataset_sha256", "f" * 64),
        ("authorization", "ssh_keygen_path", "/tmp/ssh-keygen"),
        ("authorization", "ssh_keygen_sha256", "f" * 64),
    ],
)
def test_forged_operator_evidence_is_rejected_before_reservation(
    document: str,
    field: str,
    value: JsonValue,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, config, merge, authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    target = merge if document == "merge" else authorization
    target[field] = value
    if document == "authorization":
        target.pop("operator_attestation_sha256")
        target["operator_attestation_sha256"] = canonical_digest(target)
    sealed = tmp_path / ".omo/sealed/a-b-one-shot-v1"
    filename = (
        "merge-verification.json" if document == "merge" else "run-authorization.json"
    )
    (sealed / filename).write_text(json.dumps(target), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutAdmissionError):
        load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=lambda _sha: True,
        )

    assert not (tmp_path / "holdout.started").exists()


def test_local_commit_signature_failure_stops_before_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, config, _merge, _authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutAdmissionError, match="local commit signature"):
        load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=lambda _sha: False,
        )

    assert not (tmp_path / "holdout.started").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("verified", False),
        ("reason", "unsigned"),
        ("signature", ""),
        ("payload", ""),
        ("verified_at", "not-a-timestamp"),
    ],
)
def test_mutated_github_payload_is_rejected_before_reservation(
    field: str,
    value: JsonValue,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, config, merge, _authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    verification = merge["github_verification"]
    assert isinstance(verification, dict)
    verification[field] = value
    merge["github_verification_sha256"] = canonical_digest(verification)
    sealed = tmp_path / ".omo/sealed/a-b-one-shot-v1"
    (sealed / "merge-verification.json").write_text(json.dumps(merge), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutAdmissionError):
        load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=lambda _sha: True,
        )

    assert not (tmp_path / "holdout.started").exists()
