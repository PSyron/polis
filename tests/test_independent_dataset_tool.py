from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Literal

import pytest
from tests.independent_dataset_test_helpers import (
    canonical_bytes,
    dataset_document,
    dataset_manifest,
    dataset_review,
    review_payload_bytes,
)

SCRIPT = Path(__file__).parents[1] / "scripts" / "freeze_independent_datasets.py"
type DatasetKind = Literal["calibration", "holdout"]

if (
    not SCRIPT.exists()
    or importlib.util.find_spec("polis.evaluation.calibration_operator") is None
):

    def test_planned_fixed_path_operator_tool_is_absent() -> None:
        pytest.fail("planned independent dataset operator tool is absent")

else:
    from polis.evaluation import calibration_operator, calibration_operator_io
    from polis.evaluation.calibration_freeze_models import (
        FINITE_OVERLAP_APPROVAL,
        FINITE_OVERLAP_HISTOGRAM,
        PREREGISTERED_FINITE_EXACT_MATCHES,
        OverlapResult,
    )

    COMMANDS = (
        "validate-calibration",
        "validate-holdout",
        "build-overlap",
        "verify-freeze",
    )

    def _write(path: Path, data: bytes, mode: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(data)
        path.chmod(mode)

    def _kind_paths(
        root: Path, kind: DatasetKind
    ) -> tuple[Path, Path, Path, Path, Path]:
        stem = "a-b-calibration-v2-v1" if kind == "calibration" else "a-b-holdout-v2-v1"
        sealed = root / ".omo" / "sealed" / stem
        tracked = root / "experiments" / "a-b-qualification-v2"
        return (
            sealed / "cases.json",
            tracked / f"{kind}.dataset.manifest.json",
            tracked / f"{kind}.review.json",
            sealed / "review.payload.json",
            sealed / "pii-scan.json",
        )

    def _write_kind(root: Path, kind: DatasetKind) -> None:
        dataset = canonical_bytes(dataset_document(kind))
        review = dataset_review(kind, dataset)
        review_bytes = canonical_bytes(review)
        payload = review_payload_bytes(review)
        pii = canonical_bytes(
            {
                "schema_id": "polis.a-b-qualification-v2.pii-scan",
                "schema_version": 1,
                "status": "absent",
            }
        )
        manifest = dataset_manifest(kind, dataset)
        manifest["review_manifest_sha256"] = hashlib.sha256(review_bytes).hexdigest()
        manifest["review_payload_sha256"] = hashlib.sha256(payload).hexdigest()
        manifest["pii_scan_sha256"] = hashlib.sha256(pii).hexdigest()
        paths = _kind_paths(root, kind)
        for path, data, mode in zip(
            paths,
            (dataset, canonical_bytes(manifest), review_bytes, payload, pii),
            (0o600, 0o644, 0o644, 0o600, 0o600),
            strict=True,
        ):
            _write(path, data, mode)

    @pytest.fixture
    def repository(tmp_path: Path) -> Path:
        (tmp_path / ".git").mkdir(mode=0o700)
        _write(tmp_path / "pyproject.toml", b"[project]\nname='synthetic'\n", 0o644)
        _write_kind(tmp_path, "calibration")
        _write_kind(tmp_path, "holdout")
        key = tmp_path / ".omo" / "sealed" / "a-b-qualification-v2-v1" / "overlap.key"
        _write(key, b"k" * 32, 0o600)
        return tmp_path

    def _run(monkeypatch: pytest.MonkeyPatch, root: Path, command: str) -> int:
        monkeypatch.chdir(root)
        return 0 if calibration_operator.run_operator([command]) == 0 else 2

    @pytest.mark.parametrize("command", COMMANDS)
    def test_parser_accepts_only_four_literal_commands(command: str) -> None:
        assert calibration_operator._parse_command([command]) == command

    @pytest.mark.parametrize(
        "argv",
        [
            [],
            ["validate-calibration", "extra"],
            ["--dataset", "/tmp/cases.json"],
            ["validate-holdout", "../cases.json"],
            ["build-overlap", "alias.json"],
        ],
    )
    def test_arguments_and_path_overrides_fail_before_repository_open(
        argv: list[str],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        entered = False

        def forbidden() -> calibration_operator_io.SecureRepository:
            nonlocal entered
            entered = True
            raise AssertionError("repository must not open")

        monkeypatch.setattr(calibration_operator, "_open_repository", forbidden)
        assert calibration_operator.run_operator(argv) == 2
        assert not entered
        assert json.loads(capsys.readouterr().out)["status"] == "ERROR"

    @pytest.mark.parametrize("kind", ["calibration", "holdout"])
    def test_validate_commands_emit_canonical_privacy_safe_aggregates(
        repository: Path,
        kind: DatasetKind,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert _run(monkeypatch, repository, f"validate-{kind}") == 0
        raw = capsys.readouterr().out.encode()
        result = json.loads(raw)
        assert raw == canonical_bytes(result)
        assert set(result) == {
            "schema_id",
            "schema_version",
            "command",
            "status",
            "dataset_kind",
            "case_count",
            "error_case_count",
            "correct_case_count",
            "dataset_sha256",
            "dataset_size_bytes",
            "dataset_mode",
        }
        assert "Żółty" not in raw.decode() and str(repository) not in raw.decode()

    def test_wrong_cwd_fails_without_sealed_read(
        repository: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nested = repository / "nested"
        nested.mkdir()
        monkeypatch.chdir(nested)
        assert calibration_operator.run_operator(["validate-calibration"]) == 2

    @pytest.mark.parametrize("flag", ["O_NOFOLLOW", "O_DIRECTORY"])
    def test_missing_secure_open_flag_fails_closed(
        repository: Path, flag: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(repository)
        monkeypatch.delattr(calibration_operator_io.os, flag)
        assert calibration_operator.run_operator(["validate-calibration"]) == 2

    def _fast_overlap(monkeypatch: pytest.MonkeyPatch, result: OverlapResult) -> None:
        monkeypatch.setattr(
            calibration_operator, "build_keyed_overlap", lambda *args: result
        )
        monkeypatch.setattr(calibration_operator, "_public_references", lambda repo: ())

    def test_build_overlap_is_exclusive_and_cleans_partial_output(
        repository: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _fast_overlap(
            monkeypatch,
            OverlapResult(
                0,
                0,
                1,
                "APPROVE",
                PREREGISTERED_FINITE_EXACT_MATCHES,
                FINITE_OVERLAP_HISTOGRAM,
                FINITE_OVERLAP_APPROVAL,
            ),
        )
        output = (
            repository
            / ".omo"
            / "sealed"
            / "a-b-qualification-v2-v1"
            / "overlap.oracle.json"
        )
        _write(output, b"existing\n", 0o600)
        assert _run(monkeypatch, repository, "build-overlap") == 2
        assert output.read_bytes() == b"existing\n"
        output.unlink()

        def partial(descriptor: int, data: bytes) -> None:
            os.write(descriptor, data[:5])
            raise OSError("synthetic partial write")

        monkeypatch.setattr(calibration_operator_io, "_write_all", partial)
        assert _run(monkeypatch, repository, "build-overlap") == 2
        assert not output.exists()

    def test_overlap_block_creates_no_output(
        repository: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _fast_overlap(
            monkeypatch,
            OverlapResult(
                1,
                0,
                1,
                "BLOCK",
                PREREGISTERED_FINITE_EXACT_MATCHES,
                FINITE_OVERLAP_HISTOGRAM,
                FINITE_OVERLAP_APPROVAL,
            ),
        )
        assert _run(monkeypatch, repository, "build-overlap") == 2
        output = (
            repository
            / ".omo"
            / "sealed"
            / "a-b-qualification-v2-v1"
            / "overlap.oracle.json"
        )
        assert not output.exists()

    def test_build_and_verify_use_the_fixed_exclusive_overlap_output(
        repository: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _fast_overlap(
            monkeypatch,
            OverlapResult(
                0,
                0,
                7,
                "APPROVE",
                PREREGISTERED_FINITE_EXACT_MATCHES,
                FINITE_OVERLAP_HISTOGRAM,
                FINITE_OVERLAP_APPROVAL,
            ),
        )
        assert _run(monkeypatch, repository, "build-overlap") == 0
        built = json.loads(capsys.readouterr().out)
        output = (
            repository
            / ".omo"
            / "sealed"
            / "a-b-qualification-v2-v1"
            / "overlap.oracle.json"
        )
        assert output.read_bytes() == canonical_bytes(built)
        assert output.stat().st_mode & 0o777 == 0o600
        assert _run(monkeypatch, repository, "verify-freeze") == 0
        verified = json.loads(capsys.readouterr().out)
        assert verified["command"] == "verify-freeze"
        assert verified["status"] == "APPROVE"
