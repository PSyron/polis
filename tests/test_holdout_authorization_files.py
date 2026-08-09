from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.holdout_admission_fixtures import external_evidence

from polis.evaluation.holdout_admission import _load_external_admission
from polis.evaluation.holdout_models import HoldoutAdmissionError
from polis.evaluation.holdout_ssh_authorization import _SshCommandResult
from polis.evaluation.holdout_ssh_executable import _VerifiedExecutable


class _RecordingAdapter:
    __slots__ = ("calls",)

    def __init__(self) -> None:
        self.calls: list[tuple[bytes, bytes]] = []

    def __call__(
        self,
        executable: _VerifiedExecutable,
        arguments: tuple[str, ...],
        payload: bytes,
        timeout_seconds: float,
    ) -> _SshCommandResult:
        self.calls.append((payload, Path(arguments[10]).read_bytes()))
        return _SshCommandResult(0, b"Good signature")


def test_noncanonical_authorization_bytes_are_rejected_before_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, config, _merge, authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    path = tmp_path / ".omo/sealed/a-b-one-shot-v1/run-authorization.json"
    path.write_text(json.dumps(authorization, indent=2), encoding="utf-8")
    adapter = _RecordingAdapter()
    monkeypatch.setattr(
        "polis.evaluation.holdout_ssh_authorization._run_ssh_verification", adapter
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutAdmissionError, match="canonical"):
        _load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=lambda _sha: True,
        )

    assert adapter.calls == []
    assert not (tmp_path / "holdout.started").exists()


def test_missing_detached_signature_is_rejected_before_verifier_and_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, config, _merge, _authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    (tmp_path / ".omo/sealed/a-b-one-shot-v1/run-authorization.sig").unlink()
    adapter = _RecordingAdapter()
    monkeypatch.setattr(
        "polis.evaluation.holdout_ssh_authorization._run_ssh_verification", adapter
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutAdmissionError, match="signature"):
        _load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=lambda _sha: True,
        )

    assert adapter.calls == []
    assert not (tmp_path / "holdout.started").exists()


@pytest.mark.parametrize("host", [("Linux", "arm64"), ("Darwin", "x86_64")])
def test_wrong_host_class_fails_before_authorization_evidence_or_verifier(
    host: tuple[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, config, _merge, _authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    adapter = _RecordingAdapter()
    monkeypatch.setattr(
        "polis.evaluation.holdout_ssh_authorization._run_ssh_verification", adapter
    )
    evidence_reads: list[Path] = []

    def record_evidence(path: Path) -> bytes:
        evidence_reads.append(path)
        return b""

    monkeypatch.setattr(
        "polis.evaluation.holdout_authorization._platform_adapter", lambda: host
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutAdmissionError, match="host class"):
        _load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=lambda _sha: True,
            load_evidence=record_evidence,
        )

    assert evidence_reads == []
    assert adapter.calls == []
    assert not (tmp_path / "holdout.started").exists()
