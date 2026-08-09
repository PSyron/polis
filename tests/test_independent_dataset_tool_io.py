from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Literal, assert_never

import pytest
from tests.independent_dataset_test_helpers import canonical_bytes
from tests.test_independent_dataset_freeze import _inputs
from tests.test_independent_dataset_tool import _kind_paths, _run

from polis.evaluation import calibration_operator, calibration_operator_io
from polis.evaluation.calibration_freeze import verify_frozen_bindings
from polis.evaluation.calibration_freeze_models import OverlapResult
from polis.evaluation.calibration_models import CalibrationContractError, JsonObject

pytest_plugins = ("tests.test_independent_dataset_tool",)


def _approved_overlap_document() -> JsonObject:
    return {
        "schema_id": "polis.a-b-qualification-v2.overlap-oracle",
        "schema_version": 1,
        "status": "APPROVE",
        "calibration_sha256": "1" * 64,
        "holdout_sha256": "2" * 64,
        "representation_count": 1630,
        "comparison_count": 2200000,
        "preregistered_finite_exact_matches": 78,
        "finite_match_histogram": {
            "calibration_calibration": 18,
            "calibration_public_quality": 39,
            "calibration_public_v1": 21,
            "calibration_public_conservative": 0,
        },
        "unexpected_exact_collisions": 0,
        "near_collisions": 0,
        "finite_overlap_approval": {
            "comment_id": 5234058206,
            "comment_url": (
                "https://github.com/PSyron/polis/issues/269#issuecomment-5234058206"
            ),
            "comment_author": "PSyron",
            "body_sha256": (
                "e895bba130d5e13bedc02a49cff53eb43ec435e783ca539b7620c842f6a46b79"
            ),
        },
        "output_mode": "0600",
        "verdict": "APPROVE",
    }


@pytest.mark.parametrize("component", ["file", "directory"])
def test_symlink_component_is_rejected_before_dataset_parser(
    repository: Path, component: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = _kind_paths(repository, "calibration")[0]
    if component == "file":
        alternate = repository / "alternate.json"
        alternate.write_bytes(dataset.read_bytes())
        dataset.unlink()
        dataset.symlink_to(alternate)
    else:
        sealed = dataset.parent
        alternate = repository / "alternate-sealed"
        sealed.rename(alternate)
        sealed.symlink_to(alternate, target_is_directory=True)
    assert _run(monkeypatch, repository, "validate-calibration") == 2


@pytest.mark.parametrize("defect", ["mode", "owner"])
def test_sealed_file_mode_and_owner_are_enforced(
    repository: Path, defect: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = _kind_paths(repository, "calibration")[0]
    if defect == "mode":
        dataset.chmod(0o644)
    else:
        current_uid = os.getuid()
        monkeypatch.setattr(
            calibration_operator_io.os, "getuid", lambda: current_uid + 1
        )
    assert _run(monkeypatch, repository, "validate-calibration") == 2


@pytest.mark.parametrize("mutation", ["replace", "resize"])
def test_path_replacement_and_size_change_during_read_fail_closed(
    repository: Path, mutation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _kind_paths(repository, "calibration")[0]
    original = calibration_operator_io._read_exact

    def mutate(descriptor: int, size: int) -> bytes:
        data = bytes(original(descriptor, size))
        if mutation == "replace":
            replacement = target.with_suffix(".new")
            replacement.write_bytes(data)
            replacement.chmod(0o600)
            os.replace(replacement, target)
        else:
            with target.open("ab") as handle:
                handle.write(b"x")
        return data

    monkeypatch.setattr(calibration_operator_io, "_read_exact", mutate)
    assert _run(monkeypatch, repository, "validate-calibration") == 2


def test_overlap_parser_accepts_only_the_bound_finite_classification() -> None:
    result = calibration_operator._overlap(
        canonical_bytes(_approved_overlap_document())
    )

    assert result.verdict == "APPROVE"
    assert result.preregistered_finite_exact_matches == 78
    assert result.unexpected_exact_collisions == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "count",
        "histogram",
        "unexpected",
        "near",
        "comment_id",
        "url",
        "author",
        "digest",
    ],
)
def test_overlap_parser_rejects_mutated_classification_or_approval(
    mutation: Literal[
        "count",
        "histogram",
        "unexpected",
        "near",
        "comment_id",
        "url",
        "author",
        "digest",
    ],
) -> None:
    document = deepcopy(_approved_overlap_document())
    approval = document["finite_overlap_approval"]
    assert isinstance(approval, dict)
    match mutation:
        case "count":
            document["preregistered_finite_exact_matches"] = 77
        case "histogram":
            histogram = document["finite_match_histogram"]
            assert isinstance(histogram, dict)
            histogram["calibration_calibration"] = 17
        case "unexpected":
            document["unexpected_exact_collisions"] = 1
        case "near":
            document["near_collisions"] = 1
        case "comment_id":
            approval["comment_id"] = 5234058205
        case "url":
            approval["comment_url"] = "https://example.invalid"
        case "author":
            approval["comment_author"] = "someone"
        case "digest":
            approval["body_sha256"] = "0" * 64
        case unreachable:
            assert_never(unreachable)

    with pytest.raises(CalibrationContractError):
        calibration_operator._overlap(canonical_bytes(document))


@pytest.mark.parametrize("mutation", ["id", "url", "author", "body", "histogram"])
def test_freeze_rejects_a_forged_finite_overlap_binding(
    mutation: Literal["id", "url", "author", "body", "histogram"],
) -> None:
    inputs = _inputs()
    match mutation:
        case "id":
            overlap = replace(
                inputs.overlap,
                approval=replace(inputs.overlap.approval, comment_id=5234058205),
            )
        case "url":
            overlap = replace(
                inputs.overlap,
                approval=replace(inputs.overlap.approval, comment_url="wrong"),
            )
        case "author":
            overlap = replace(
                inputs.overlap,
                approval=replace(inputs.overlap.approval, comment_author="wrong"),
            )
        case "body":
            overlap = replace(
                inputs.overlap,
                approval=replace(inputs.overlap.approval, body_sha256="0" * 64),
            )
        case "histogram":
            overlap = replace(
                inputs.overlap,
                finite_match_histogram=replace(
                    inputs.overlap.finite_match_histogram,
                    calibration_calibration=17,
                ),
            )
        case unreachable:
            assert_never(unreachable)
    forged = replace(
        inputs,
        overlap=overlap,
    )

    with pytest.raises(CalibrationContractError):
        verify_frozen_bindings(forged)


def test_overlap_result_cannot_default_unobserved_finite_matches() -> None:
    with pytest.raises(TypeError):
        OverlapResult(0, 0, 1, "APPROVE")


def _gitfile(repository: Path, content: bytes) -> Path:
    marker = repository / ".git"
    marker.rmdir()
    marker.write_bytes(content)
    marker.chmod(0o644)
    return marker


def test_linked_worktree_gitfile_is_admitted(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gitfile(repository, b"gitdir: /synthetic/repo/.git/worktrees/issue-269\n")

    assert _run(monkeypatch, repository, "validate-calibration") == 0


@pytest.mark.parametrize(
    "defect", ["malformed", "mode", "owner", "symlink", "unstable"]
)
def test_linked_worktree_gitfile_defects_fail_closed(
    repository: Path,
    defect: Literal["malformed", "mode", "owner", "symlink", "unstable"],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = _gitfile(repository, b"gitdir: /synthetic/repo/.git/worktrees/issue-269\n")
    match defect:
        case "malformed":
            marker.write_bytes(b"not-a-gitfile\n")
        case "mode":
            marker.chmod(0o600)
        case "owner":
            marker_inode = marker.stat().st_ino
            original_fstat = calibration_operator_io.os.fstat

            def wrong_owner(descriptor: int) -> os.stat_result:
                info = os.stat_result(original_fstat(descriptor))
                if info.st_ino != marker_inode:
                    return info
                values = list(info)
                values[4] = os.getuid() + 1
                return os.stat_result(values)

            monkeypatch.setattr(calibration_operator_io.os, "fstat", wrong_owner)
        case "symlink":
            alternate = repository / "alternate-gitfile"
            marker.rename(alternate)
            marker.symlink_to(alternate)
        case "unstable":
            original = calibration_operator_io._read_exact

            def replace_marker(descriptor: int, size: int) -> bytes:
                data = bytes(original(descriptor, size))
                replacement = marker.with_suffix(".new")
                replacement.write_bytes(data)
                replacement.chmod(0o644)
                os.replace(replacement, marker)
                return data

            monkeypatch.setattr(calibration_operator_io, "_read_exact", replace_marker)
        case unreachable:
            assert_never(unreachable)

    assert _run(monkeypatch, repository, "validate-calibration") == 2
