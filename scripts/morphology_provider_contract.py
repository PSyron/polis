from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from scripts.morphology_provider_json import (
    ContractError,
    JsonValue,
    boolean,
    canonical_bytes,
    exact_fields,
    integer,
    mapping,
    number,
    optional_string,
    read_json,
    string,
)
from scripts.morphology_provider_scope import validate_case_scope


@dataclass(frozen=True, slots=True)
class QualityThresholds:
    precision: float
    recall: float
    correction_accuracy: float
    false_alarm_rate: float
    stable_repetitions: int
    require_ambiguity_abstention: bool
    require_unknown_abstention: bool


@dataclass(frozen=True, slots=True)
class QualificationCase:
    id: str
    phenomenon: str
    input_form: str
    source_lemma: str | None
    source_pos: str | None
    target_tag: str
    expected_outcome: str
    expected_form: str | None


@dataclass(frozen=True, slots=True)
class DatasetIdentity:
    dataset_id: str
    dataset_version: int
    canonical_sha256: str
    license: str


@dataclass(frozen=True, slots=True)
class QualificationDataset:
    identity: DatasetIdentity
    thresholds: QualityThresholds
    cases: tuple[QualificationCase, ...]


def canonical_file_sha256(path: Path) -> str:
    value = read_json(path)
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _parse_thresholds(value: JsonValue) -> QualityThresholds:
    fields = frozenset(
        {
            "precision",
            "recall",
            "correction_accuracy",
            "false_alarm_rate",
            "stable_repetitions",
            "require_ambiguity_abstention",
            "require_unknown_abstention",
        }
    )
    raw = mapping(value, "thresholds")
    exact_fields(raw, fields, "thresholds")
    result = QualityThresholds(
        precision=number(raw["precision"], "thresholds.precision"),
        recall=number(raw["recall"], "thresholds.recall"),
        correction_accuracy=number(
            raw["correction_accuracy"], "thresholds.correction_accuracy"
        ),
        false_alarm_rate=number(raw["false_alarm_rate"], "thresholds.false_alarm_rate"),
        stable_repetitions=integer(
            raw["stable_repetitions"], "thresholds.stable_repetitions"
        ),
        require_ambiguity_abstention=boolean(
            raw["require_ambiguity_abstention"],
            "thresholds.require_ambiguity_abstention",
        ),
        require_unknown_abstention=boolean(
            raw["require_unknown_abstention"], "thresholds.require_unknown_abstention"
        ),
    )
    preregistered = QualityThresholds(
        precision=1.0,
        recall=1.0,
        correction_accuracy=1.0,
        false_alarm_rate=0.0,
        stable_repetitions=5,
        require_ambiguity_abstention=True,
        require_unknown_abstention=True,
    )
    if result != preregistered:
        raise ContractError("thresholds do not match the preregistered contract")
    return result


def _parse_case(value: JsonValue, index: int) -> QualificationCase:
    fields = frozenset(
        {
            "id",
            "phenomenon",
            "input_form",
            "source_lemma",
            "source_pos",
            "target_tag",
            "expected_outcome",
            "expected_form",
        }
    )
    raw = mapping(value, f"cases[{index}]")
    exact_fields(raw, fields, f"cases[{index}]")
    outcome = string(raw["expected_outcome"], f"cases[{index}].expected_outcome")
    form = optional_string(raw["expected_form"], f"cases[{index}].expected_form")
    if outcome not in {"suggest", "abstain"}:
        raise ContractError(f"cases[{index}].expected_outcome is unsupported")
    if (outcome == "suggest") != (form is not None):
        raise ContractError(f"cases[{index}] outcome and expected_form disagree")
    return QualificationCase(
        id=string(raw["id"], f"cases[{index}].id"),
        phenomenon=string(raw["phenomenon"], f"cases[{index}].phenomenon"),
        input_form=string(raw["input_form"], f"cases[{index}].input_form"),
        source_lemma=optional_string(
            raw["source_lemma"], f"cases[{index}].source_lemma"
        ),
        source_pos=optional_string(raw["source_pos"], f"cases[{index}].source_pos"),
        target_tag=string(raw["target_tag"], f"cases[{index}].target_tag"),
        expected_outcome=outcome,
        expected_form=form,
    )


def _validate_manifest(
    value: JsonValue,
    dataset: QualificationDataset,
    *,
    require_reviewed: bool,
) -> None:
    raw = mapping(value, "manifest")
    fields = frozenset(
        {
            "schema_id",
            "schema_version",
            "dataset_id",
            "dataset_version",
            "canonical_sha256",
            "review",
        }
    )
    exact_fields(raw, fields, "manifest")
    if raw["schema_id"] != "polis.morphology-provider-qualification-manifest":
        raise ContractError("manifest schema identity mismatch")
    if raw["schema_version"] != 1:
        raise ContractError("manifest schema version mismatch")
    if raw["dataset_id"] != dataset.identity.dataset_id:
        raise ContractError("manifest dataset identity mismatch")
    if raw["dataset_version"] != dataset.identity.dataset_version:
        raise ContractError("manifest dataset version mismatch")
    if raw["canonical_sha256"] != dataset.identity.canonical_sha256:
        raise ContractError("manifest canonical hash mismatch")
    review = mapping(raw["review"], "manifest.review")
    review_fields = frozenset(
        {
            "status",
            "reviewer_role",
            "checklist_version",
            "reviewed_case_ids",
            "canonical_sha256",
        }
    )
    exact_fields(review, review_fields, "manifest.review")
    if review["canonical_sha256"] != dataset.identity.canonical_sha256:
        raise ContractError("review canonical hash mismatch")
    if require_reviewed and review["status"] != "independent-reviewed":
        raise ContractError("manifest review status must be independent-reviewed")
    reviewed = review["reviewed_case_ids"]
    if not isinstance(reviewed, list) or not all(
        isinstance(item, str) for item in reviewed
    ):
        raise ContractError("reviewed_case_ids must be a string list")
    if review["status"] == "independent-reviewed" and tuple(reviewed) != tuple(
        case.id for case in dataset.cases
    ):
        raise ContractError("independent review must cover every case in order")


def load_qualification_dataset(
    dataset_path: Path,
    manifest_path: Path,
    *,
    require_reviewed: bool = True,
) -> QualificationDataset:
    value = read_json(dataset_path)
    raw = mapping(value, "dataset")
    fields = frozenset(
        {
            "schema_id",
            "schema_version",
            "dataset_id",
            "dataset_version",
            "license",
            "source",
            "thresholds",
            "cases",
        }
    )
    exact_fields(raw, fields, "dataset")
    if raw["schema_id"] != "polis.morphology-provider-qualification":
        raise ContractError("dataset schema identity mismatch")
    if raw["schema_version"] != 1 or raw["dataset_version"] != 1:
        raise ContractError("dataset version mismatch")
    source = mapping(raw["source"], "source")
    exact_fields(source, frozenset({"author", "created", "description"}), "source")
    if source["author"] != "Paweł Cyroń" or raw["license"] != "CC0-1.0":
        raise ContractError("dataset provenance or license mismatch")
    cases_raw = raw["cases"]
    if not isinstance(cases_raw, list):
        raise ContractError("cases must be an array")
    cases = tuple(_parse_case(item, index) for index, item in enumerate(cases_raw))
    validate_case_scope(tuple((case.id, case.expected_outcome) for case in cases))
    canonical_sha256 = hashlib.sha256(canonical_bytes(value)).hexdigest()
    dataset = QualificationDataset(
        identity=DatasetIdentity(
            dataset_id=string(raw["dataset_id"], "dataset_id"),
            dataset_version=integer(raw["dataset_version"], "dataset_version"),
            canonical_sha256=canonical_sha256,
            license=string(raw["license"], "license"),
        ),
        thresholds=_parse_thresholds(raw["thresholds"]),
        cases=cases,
    )
    _validate_manifest(
        read_json(manifest_path), dataset, require_reviewed=require_reviewed
    )
    return dataset
