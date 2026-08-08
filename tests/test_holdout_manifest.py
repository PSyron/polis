from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from tests.holdout_config_fixture import synthetic_config
from tests.holdout_test_helpers import DATASET_SHA256, JsonObject, JsonValue

from polis.evaluation.holdout_contract import parse_holdout_config
from polis.evaluation.holdout_models import HoldoutContractError
from polis.evaluation.holdout_runner import run_from_config

REVIEW_MANIFEST_SHA256 = (
    "f58f7c81ee46cb25968ca84e1f0ce6a842b14181c6151f041a4f30225aab3e4d"
)
REVIEW_PAYLOAD_SHA256 = (
    "f5312a257d634f240301dbdfe47fad3b0897e4a4e7f11f10af3a51df0a777cd0"
)


def synthetic_manifest() -> JsonObject:
    return {
        "schema_id": "polis.a-b-one-shot.dataset-manifest",
        "schema_version": 1,
        "dataset_id": "polis-a-b-one-shot-v1",
        "dataset_schema": "polis.a-b-one-shot.dataset/1",
        "sha256": DATASET_SHA256,
        "size_bytes": 17370,
        "mode": "0600",
        "case_count": 52,
        "source_count": 20,
        "expected_finding_count": 19,
        "role_counts": {"error": 14, "correct": 27, "abstain": 10, "conflict": 1},
        "license": "CC0-1.0",
        "provenance": "project-authored-independent-review",
        "review": {
            "reviewer_role": "independent-dataset-reviewer",
            "verdict": "APPROVE",
            "reviewed_case_count": 52,
            "total_case_count": 52,
            "reviewed_source_count": 20,
            "review_manifest_sha256": REVIEW_MANIFEST_SHA256,
            "review_payload_sha256": REVIEW_PAYLOAD_SHA256,
            "analyzer_executed": False,
            "protected_artifacts_used": False,
        },
        "plaintext_in_repository": False,
    }


def test_independent_review_manifest_is_machine_bound_to_config() -> None:
    from polis.evaluation.holdout_manifest import parse_dataset_manifest

    parsed = parse_dataset_manifest(
        synthetic_manifest(), parse_holdout_config(synthetic_config())
    )

    assert parsed.reviewer_role == "independent-dataset-reviewer"
    assert parsed.reviewed_case_count == parsed.total_case_count == 52
    assert parsed.review_manifest_sha256 == REVIEW_MANIFEST_SHA256
    assert parsed.review_payload_sha256 == REVIEW_PAYLOAD_SHA256


def test_tracked_manifest_contains_the_approved_independent_review_binding() -> None:
    from polis.evaluation.holdout_manifest import parse_dataset_manifest

    raw = json.loads(
        Path("experiments/a-b-one-shot/dataset.manifest.json").read_bytes()
    )
    assert isinstance(raw, dict)

    parsed = parse_dataset_manifest(raw, parse_holdout_config(synthetic_config()))

    assert parsed.reviewer_role == "independent-dataset-reviewer"
    assert parsed.review_manifest_sha256 == REVIEW_MANIFEST_SHA256


def test_runner_rejects_manifest_drift_before_reservation_or_evidence_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    experiment = tmp_path / "experiments/a-b-one-shot"
    experiment.mkdir(parents=True)
    (tmp_path / ".omo/sealed/a-b-one-shot-v1").mkdir(parents=True)
    (experiment / "config.json").write_text(
        json.dumps(synthetic_config()), encoding="utf-8"
    )
    manifest = synthetic_manifest()
    review = manifest["review"]
    assert isinstance(review, dict)
    review["review_payload_sha256"] = "0" * 64
    (experiment / "dataset.manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutContractError, match="independent review"):
        run_from_config(
            Path("experiments/a-b-one-shot/config.json"),
            repository_root=tmp_path,
        )

    assert not (experiment / "holdout.started").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reviewer_role", "dataset-author"),
        ("verdict", "REJECT"),
        ("reviewed_case_count", 51),
        ("total_case_count", 53),
        ("review_manifest_sha256", "0" * 64),
        ("review_payload_sha256", "1" * 64),
    ],
)
def test_manifest_review_identity_drift_fails_closed(
    field: str, value: JsonValue
) -> None:
    from polis.evaluation.holdout_manifest import parse_dataset_manifest

    manifest = deepcopy(synthetic_manifest())
    review = manifest["review"]
    assert isinstance(review, dict)
    review[field] = value

    with pytest.raises(HoldoutContractError, match="independent review"):
        parse_dataset_manifest(manifest, parse_holdout_config(synthetic_config()))
