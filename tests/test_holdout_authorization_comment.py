from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.holdout_admission_fixtures import (
    DEFAULT_AUTHORIZATION_COMMENT,
    AuthorizationComment,
    authorization_body,
    canonical_bytes,
    external_evidence,
    write_authorization,
)
from tests.holdout_test_helpers import JsonObject, JsonValue

from polis.evaluation.holdout_admission import _load_external_admission
from polis.evaluation.holdout_models import HoldoutAdmissionError
from polis.evaluation.holdout_ssh_authorization import _SshCommandResult
from polis.evaluation.holdout_ssh_executable import _VerifiedExecutable

_WATERMARK = 5228447541


@dataclass(slots=True)
class _RecordingVerifier:
    calls: list[bytes]
    accepts: bool = True

    def __call__(
        self,
        executable: _VerifiedExecutable,
        arguments: tuple[str, ...],
        payload: bytes,
        timeout_seconds: float,
    ) -> _SshCommandResult:
        self.calls.append(payload)
        if self.accepts:
            return _SshCommandResult(0, b"Good signature")
        return _SshCommandResult(1, b"bad signature")


@dataclass(frozen=True, slots=True)
class _AdmissionHarness:
    root: Path
    monkeypatch: pytest.MonkeyPatch
    verifier: _RecordingVerifier

    def admit(
        self,
        comment: AuthorizationComment = DEFAULT_AUTHORIZATION_COMMENT,
    ) -> tuple[JsonObject, JsonObject]:
        raw, config, _merge, authorization, source_sha, source_tree = external_evidence(
            self.root, comment
        )
        self.monkeypatch.setattr(
            "polis.evaluation.holdout_ssh_authorization._run_ssh_verification",
            self.verifier,
        )
        self.monkeypatch.chdir(self.root)
        admitted = _load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=lambda _sha: True,
        )
        assert admitted.evidence.merge_commit == source_sha
        return raw, authorization


def _assert_no_outputs(root: Path) -> None:
    experiment = root / "experiments/a-b-one-shot"
    assert not (experiment / "holdout.started").exists()
    assert not (experiment / "report.json").exists()
    assert not (experiment / "normalized-report.json").exists()
    assert not (experiment / "result.manifest.json").exists()


def _guard_dataset_reads(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    reads: list[Path] = []
    read_bytes = Path.read_bytes

    def guarded(path: Path) -> bytes:
        if path.name == "cases.json":
            reads.append(path)
            raise AssertionError("dataset loader must not be entered")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    return reads


@pytest.mark.parametrize("comment_id", [_WATERMARK + 1, _WATERMARK + 991])
def test_two_distinct_newer_canonical_signed_comments_are_admitted(
    comment_id: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = _RecordingVerifier([])
    dataset_reads = _guard_dataset_reads(monkeypatch)

    _raw, authorization = _AdmissionHarness(tmp_path, monkeypatch, verifier).admit(
        AuthorizationComment(comment_id=comment_id),
    )

    assert verifier.calls == [canonical_bytes(authorization)]
    assert authorization["comment_url"] == (
        f"https://github.com/PSyron/polis/issues/243#issuecomment-{comment_id}"
    )
    _assert_no_outputs(tmp_path)
    assert dataset_reads == []


@pytest.mark.parametrize("comment_id", [_WATERMARK, _WATERMARK - 1, True])
def test_old_lower_or_boolean_comment_id_is_rejected_before_signature(
    comment_id: JsonValue, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = _RecordingVerifier([])
    dataset_reads = _guard_dataset_reads(monkeypatch)

    with pytest.raises(HoldoutAdmissionError, match="comment_id"):
        _AdmissionHarness(tmp_path, monkeypatch, verifier).admit(
            AuthorizationComment(comment_id=comment_id),
        )

    assert verifier.calls == []
    _assert_no_outputs(tmp_path)
    assert dataset_reads == []


@pytest.mark.parametrize(
    "comment_url",
    [
        "https://github.com/PSyron/polis/issues/243#issuecomment-5228447541",
        "https://github.com/PSyron/polis/issues/243#issuecomment-5228447543",
    ],
)
def test_newer_comment_rejects_reused_or_wrong_url_before_signature(
    comment_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = _RecordingVerifier([])
    dataset_reads = _guard_dataset_reads(monkeypatch)
    raw, config, _merge, authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    authorization["comment_url"] = comment_url
    write_authorization(tmp_path, authorization)
    monkeypatch.setattr(
        "polis.evaluation.holdout_ssh_authorization._run_ssh_verification",
        verifier,
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutAdmissionError, match="comment_url"):
        _load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=lambda _sha: True,
        )

    assert verifier.calls == []
    _assert_no_outputs(tmp_path)
    assert dataset_reads == []


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("author", "dataset-reviewer", "identity"),
        ("created_at", "2026-08-08T20:10:00Z", "predates"),
        ("created_at", "2026-08-08T20:09:59Z", "predates"),
        ("body", "run_authorization=approved", "body"),
        ("evaluated_source_sha", "f" * 40, "evaluated_source_sha"),
        ("config_sha256", "f" * 64, "config_sha256"),
        ("dataset_sha256", "f" * 64, "dataset_sha256"),
    ],
)
def test_newer_comment_rejects_wrong_stale_or_malformed_signed_metadata(
    field: str,
    value: JsonValue,
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = _RecordingVerifier([])
    dataset_reads = _guard_dataset_reads(monkeypatch)
    raw, config, _merge, authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    authorization[field] = value
    if field in {"evaluated_source_sha", "config_sha256", "dataset_sha256"}:
        authorization["body"] = authorization_body(authorization)
    write_authorization(tmp_path, authorization)
    monkeypatch.setattr(
        "polis.evaluation.holdout_ssh_authorization._run_ssh_verification",
        verifier,
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutAdmissionError, match=message):
        _load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=lambda _sha: True,
        )

    assert verifier.calls == []
    _assert_no_outputs(tmp_path)
    assert dataset_reads == []


def test_newer_comment_with_invalid_signature_is_rejected_without_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = _RecordingVerifier([], accepts=False)
    dataset_reads = _guard_dataset_reads(monkeypatch)

    with pytest.raises(HoldoutAdmissionError, match="signature verification"):
        _AdmissionHarness(tmp_path, monkeypatch, verifier).admit()

    assert len(verifier.calls) == 1
    _assert_no_outputs(tmp_path)
    assert dataset_reads == []
