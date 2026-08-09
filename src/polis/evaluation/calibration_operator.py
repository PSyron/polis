from __future__ import annotations

import hashlib
import sys
from typing import Literal, assert_never

from polis.evaluation.calibration_freeze import verify_frozen_bindings
from polis.evaluation.calibration_freeze_models import (
    FINITE_OVERLAP_APPROVAL,
    FINITE_OVERLAP_HISTOGRAM,
    PREREGISTERED_FINITE_EXACT_MATCHES,
    FreezeInputs,
    OverlapResult,
)
from polis.evaluation.calibration_json import (
    canonical_bytes,
    fail,
)
from polis.evaluation.calibration_models import (
    CalibrationContractError,
    JsonObject,
)
from polis.evaluation.calibration_operator_io import (
    _open_repository,
    _SecureRepository,
)
from polis.evaluation.calibration_operator_overlap import parse_overlap as _overlap
from polis.evaluation.calibration_operator_public import _public_references
from polis.evaluation.calibration_operator_validation import (
    _CALIBRATION,
    _EXPERIMENT,
    _HOLDOUT,
    _validated,
    _ValidatedDataset,
)
from polis.evaluation.calibration_overlap import (
    DatasetLike,
    build_keyed_overlap,
)
from polis.evaluation.calibration_review import parse_dataset_review

type OperatorCommand = Literal[
    "validate-calibration", "validate-holdout", "build-overlap", "verify-freeze"
]

_OVERLAP = (".omo", "sealed", "a-b-qualification-v2-v1")
_OVERLAP_OUTPUT = (*_OVERLAP, "overlap.oracle.json")


def _parse_command(argv: list[str]) -> OperatorCommand:
    if argv == ["validate-calibration"]:
        return "validate-calibration"
    if argv == ["validate-holdout"]:
        return "validate-holdout"
    if argv == ["build-overlap"]:
        return "build-overlap"
    if argv == ["verify-freeze"]:
        return "verify-freeze"
    raise CalibrationContractError("operator accepts exactly one frozen command")


def _aggregate(command: OperatorCommand, validated: _ValidatedDataset) -> JsonObject:
    errors = sum(case.role == "error" for case in validated.dataset.cases)
    return {
        "schema_id": "polis.a-b-qualification-v2.operator-result",
        "schema_version": 1,
        "command": command,
        "status": "APPROVE",
        "dataset_kind": validated.manifest.kind,
        "case_count": len(validated.dataset.cases),
        "error_case_count": errors,
        "correct_case_count": len(validated.dataset.cases) - errors,
        "dataset_sha256": validated.manifest.dataset_sha256,
        "dataset_size_bytes": validated.manifest.dataset_size_bytes,
        "dataset_mode": "0600",
    }


def _overlap_document(
    calibration: _ValidatedDataset,
    holdout: _ValidatedDataset,
    references: tuple[DatasetLike, ...],
    result: OverlapResult,
) -> JsonObject:
    representations = sum(
        len(dataset.cases) + sum(case.role == "error" for case in dataset.cases)
        for dataset in (calibration.dataset, holdout.dataset, *references)
    )
    return {
        "schema_id": "polis.a-b-qualification-v2.overlap-oracle",
        "schema_version": 1,
        "status": "APPROVE",
        "calibration_sha256": calibration.manifest.dataset_sha256,
        "holdout_sha256": holdout.manifest.dataset_sha256,
        "representation_count": representations,
        "comparison_count": result.comparison_count,
        "preregistered_finite_exact_matches": (
            result.preregistered_finite_exact_matches
        ),
        "finite_match_histogram": {
            "calibration_calibration": (
                result.finite_match_histogram.calibration_calibration
            ),
            "calibration_public_quality": (
                result.finite_match_histogram.calibration_public_quality
            ),
            "calibration_public_v1": (
                result.finite_match_histogram.calibration_public_v1
            ),
            "calibration_public_conservative": (
                result.finite_match_histogram.calibration_public_conservative
            ),
        },
        "unexpected_exact_collisions": result.unexpected_exact_collisions,
        "near_collisions": result.near_collisions,
        "finite_overlap_approval": {
            "comment_id": result.approval.comment_id,
            "comment_url": result.approval.comment_url,
            "comment_author": result.approval.comment_author,
            "body_sha256": result.approval.body_sha256,
        },
        "output_mode": "0600",
        "verdict": result.verdict,
    }


def _build(repo: _SecureRepository) -> JsonObject:
    calibration = _validated(repo, "calibration")
    holdout = _validated(repo, "holdout")
    key = repo.read((*_OVERLAP, "overlap.key"), expected_mode=0o600)
    references = _public_references(repo)
    result = build_keyed_overlap(calibration.dataset, holdout.dataset, references, key)
    if (
        result.verdict != "APPROVE"
        or result.preregistered_finite_exact_matches
        != PREREGISTERED_FINITE_EXACT_MATCHES
        or result.finite_match_histogram != FINITE_OVERLAP_HISTOGRAM
        or result.unexpected_exact_collisions
        or result.near_collisions
        or result.approval != FINITE_OVERLAP_APPROVAL
    ):
        fail("overlap oracle requires only the preregistered finite matches")
    output = _overlap_document(calibration, holdout, references, result)
    repo.create(_OVERLAP_OUTPUT, canonical_bytes(output))
    return output


def _verify(repo: _SecureRepository) -> JsonObject:
    calibration = _validated(repo, "calibration")
    holdout = _validated(repo, "holdout")
    overlap_bytes = repo.read(_OVERLAP_OUTPUT, expected_mode=0o600)
    overlap = _overlap(overlap_bytes)
    calibration_review = parse_dataset_review(
        repo.read((*_EXPERIMENT, "calibration.review.json"), expected_mode=0o644),
        "calibration",
        repo.read((*_CALIBRATION, "review.payload.json"), expected_mode=0o600),
    )
    holdout_review = parse_dataset_review(
        repo.read((*_EXPERIMENT, "holdout.review.json"), expected_mode=0o644),
        "holdout",
        repo.read((*_HOLDOUT, "review.payload.json"), expected_mode=0o600),
    )
    verification = verify_frozen_bindings(
        FreezeInputs(
            calibration.manifest,
            holdout.manifest,
            calibration_review,
            holdout_review,
            overlap,
            "polis-269-overlap-custodian-v1",
            "polis-269-freeze-verifier-a-v1",
            "polis-269-freeze-verifier-b-v1",
        )
    )
    digest = hashlib.sha256(overlap_bytes).hexdigest()
    return {
        "schema_id": "polis.a-b-qualification-v2.operator-result",
        "schema_version": 1,
        "command": "verify-freeze",
        "status": verification.verdict,
        "artifact_count": 7,
        "verification_sha256": digest,
        "artifact_mode": "0600",
    }


def _execute(repo: _SecureRepository, command: OperatorCommand) -> JsonObject:
    match command:
        case "validate-calibration":
            return _aggregate(command, _validated(repo, "calibration"))
        case "validate-holdout":
            return _aggregate(command, _validated(repo, "holdout"))
        case "build-overlap":
            return _build(repo)
        case "verify-freeze":
            return _verify(repo)
        case unreachable:
            assert_never(unreachable)


def _emit(value: JsonObject) -> None:
    sys.stdout.buffer.write(canonical_bytes(value))


def _error(command: str) -> JsonObject:
    return {
        "schema_id": "polis.a-b-qualification-v2.operator-error",
        "schema_version": 1,
        "command": command,
        "status": "ERROR",
        "error_code": "admission_failed",
    }


def run_operator(argv: list[str]) -> int:
    command: OperatorCommand | None = None
    repository: _SecureRepository | None = None
    try:
        command = _parse_command(argv)
        repository = _open_repository()
        _emit(_execute(repository, command))
    except (CalibrationContractError, OSError, ValueError):
        _emit(_error(command or "invalid"))
        return 2
    finally:
        if repository is not None:
            repository.close()
    return 0
