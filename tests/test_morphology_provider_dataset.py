from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.morphology_provider_contract import (
    ContractError,
    canonical_file_sha256,
    load_qualification_dataset,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "tests/fixtures/v1/morphology_provider_qualification.json"
MANIFEST = DATASET.with_suffix(".manifest.json")


def test_fixture_has_preregistered_scope_and_thresholds() -> None:
    dataset = load_qualification_dataset(DATASET, MANIFEST, require_reviewed=False)

    assert len(dataset.cases) == 9
    assert sum(case.expected_form is not None for case in dataset.cases) == 3
    assert dataset.thresholds.precision == 1.0
    assert dataset.thresholds.recall == 1.0
    assert dataset.thresholds.correction_accuracy == 1.0
    assert dataset.thresholds.false_alarm_rate == 0.0
    assert dataset.thresholds.stable_repetitions == 5


def test_pending_review_is_rejected_by_benchmark_loader(tmp_path: Path) -> None:
    payload = json.loads(MANIFEST.read_text())
    payload["review"]["status"] = "pending-independent-review"
    payload["review"]["reviewed_case_ids"] = []
    pending = tmp_path / "pending.manifest.json"
    pending.write_text(json.dumps(payload))

    with pytest.raises(ContractError, match="independent-reviewed"):
        load_qualification_dataset(DATASET, pending)


def test_dataset_rejects_unknown_fields(tmp_path: Path) -> None:
    payload = json.loads(DATASET.read_text())
    payload["unexpected"] = True
    changed = tmp_path / "dataset.json"
    changed.write_text(json.dumps(payload))

    with pytest.raises(ContractError, match="unexpected fields"):
        load_qualification_dataset(changed, MANIFEST, require_reviewed=False)


def test_dataset_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    payload = json.loads(DATASET.read_text())
    payload["cases"].append(payload["cases"][0])
    changed = tmp_path / "dataset.json"
    changed.write_text(json.dumps(payload))

    with pytest.raises(ContractError, match="duplicate case id"):
        load_qualification_dataset(changed, MANIFEST, require_reviewed=False)


def test_manifest_hash_is_canonical_file_hash() -> None:
    payload = json.loads(MANIFEST.read_text())
    assert payload["canonical_sha256"] == canonical_file_sha256(DATASET)
    assert payload["review"]["canonical_sha256"] == canonical_file_sha256(DATASET)


def test_dataset_rejects_post_hoc_threshold_changes(tmp_path: Path) -> None:
    dataset_payload = json.loads(DATASET.read_text())
    dataset_payload["thresholds"]["recall"] = 0.5
    changed_dataset = tmp_path / "changed.json"
    changed_dataset.write_text(json.dumps(dataset_payload))
    changed_hash = canonical_file_sha256(changed_dataset)
    manifest_payload = json.loads(MANIFEST.read_text())
    manifest_payload["canonical_sha256"] = changed_hash
    manifest_payload["review"]["canonical_sha256"] = changed_hash
    changed_manifest = tmp_path / "changed.manifest.json"
    changed_manifest.write_text(json.dumps(manifest_payload))

    with pytest.raises(ContractError, match="preregistered"):
        load_qualification_dataset(
            changed_dataset, changed_manifest, require_reviewed=False
        )


def test_dataset_rejects_incomplete_preregistered_case_set(tmp_path: Path) -> None:
    dataset_payload = json.loads(DATASET.read_text())
    dataset_payload["cases"] = dataset_payload["cases"][:-1]
    changed_dataset = tmp_path / "changed.json"
    changed_dataset.write_text(json.dumps(dataset_payload))
    changed_hash = canonical_file_sha256(changed_dataset)
    manifest_payload = json.loads(MANIFEST.read_text())
    manifest_payload["canonical_sha256"] = changed_hash
    manifest_payload["review"]["canonical_sha256"] = changed_hash
    manifest_payload["review"]["reviewed_case_ids"] = [
        case["id"] for case in dataset_payload["cases"]
    ]
    changed_manifest = tmp_path / "changed.manifest.json"
    changed_manifest.write_text(json.dumps(manifest_payload))

    with pytest.raises(ContractError, match="preregistered case set"):
        load_qualification_dataset(changed_dataset, changed_manifest)
