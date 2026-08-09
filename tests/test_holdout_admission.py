from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

import pytest
from tests.holdout_admission_fixtures import canonical_bytes, external_evidence
from tests.holdout_config_fixture import synthetic_config

from polis.evaluation.holdout_admission import (
    _load_external_admission,
    load_external_admission,
)
from polis.evaluation.holdout_models import HoldoutAdmissionError
from polis.evaluation.holdout_runner import run_from_config
from polis.evaluation.holdout_ssh_authorization import (
    _authorization_verifier,
    _SshCommandResult,
)
from polis.evaluation.holdout_ssh_executable import _VerifiedExecutable


class _AcceptAuthorizationAdapter:
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


def test_public_runner_and_admission_expose_no_authority_or_process_injection() -> None:
    admission_parameters = inspect.signature(load_external_admission).parameters
    runner_parameters = inspect.signature(run_from_config).parameters

    assert "authorization_command" not in admission_parameters
    assert "authorization_verifier" not in admission_parameters
    assert "authorization_command" not in runner_parameters
    assert "authorization_verifier" not in runner_parameters

    with pytest.raises(TypeError, match="unexpected keyword"):
        inspect.signature(run_from_config).bind(
            Path("experiments/a-b-one-shot/config.json"),
            authorization_command=_AcceptAuthorizationAdapter(),
        )


def test_authorization_module_exposes_no_constructible_process_boundary() -> None:
    module = importlib.import_module("polis.evaluation.holdout_ssh_authorization")
    executable_module = importlib.import_module(
        "polis.evaluation.holdout_ssh_executable"
    )

    for name in (
        "SshAuthorizationVerifier",
        "SshCommand",
        "SshCommandResult",
        "SystemSshCommand",
        "ssh_public_key_fingerprint",
    ):
        assert not hasattr(module, name)
    for name in ("VerifiedExecutable", "verified_executable", "assert_stable"):
        assert not hasattr(executable_module, name)
    assert tuple(inspect.signature(_authorization_verifier).parameters) == (
        "executable_sha256",
    )


def test_default_runner_fails_before_reservation_when_external_evidence_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "experiments/a-b-one-shot/config.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(synthetic_config()), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutAdmissionError):
        run_from_config(
            Path("experiments/a-b-one-shot/config.json"), repository_root=tmp_path
        )

    assert not (tmp_path / "experiments/a-b-one-shot/holdout.started").exists()


def test_external_merge_and_run_authorization_are_both_bound_before_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, config, merge, _authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    monkeypatch.chdir(tmp_path)
    verified: list[str] = []

    def verify_commit(sha: str) -> bool:
        verified.append(sha)
        return True

    with pytest.raises(
        HoldoutAdmissionError,
        match="run authorization signature|SSH authorization",
    ):
        load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=verify_commit,
        )

    assert verified == [source_sha]
    assert not (tmp_path / "holdout.started").exists()


def test_self_authored_consistent_authorization_cannot_admit_without_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, config, _merge, _authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(
        HoldoutAdmissionError,
        match="run authorization signature|SSH authorization",
    ):
        load_external_admission(
            raw,
            config,
            checkout_identity=lambda kind: (
                source_sha if kind == "commit" else source_tree
            ),
            verify_commit=lambda _sha: True,
        )

    assert not (tmp_path / "experiments/a-b-one-shot/holdout.started").exists()


def test_injected_subprocess_boundary_still_uses_offline_ssh_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, config, _merge, authorization, source_sha, source_tree = external_evidence(
        tmp_path
    )
    monkeypatch.chdir(tmp_path)
    adapter = _AcceptAuthorizationAdapter()
    monkeypatch.setattr(
        "polis.evaluation.holdout_ssh_authorization._run_ssh_verification", adapter
    )

    admitted = _load_external_admission(
        raw,
        config,
        checkout_identity=lambda kind: source_sha if kind == "commit" else source_tree,
        verify_commit=lambda _sha: True,
    )

    assert admitted.evidence.merge_commit == source_sha
    assert len(adapter.calls) == 1
    payload, signature = adapter.calls[0]
    assert b'"run_authorization":"approved"' in payload
    assert payload == canonical_bytes(authorization)
    assert signature == (
        b"-----BEGIN SSH SIGNATURE-----\nc3ludGhldGlj\n-----END SSH SIGNATURE-----\n"
    )
    assert not (tmp_path / "experiments/a-b-one-shot/holdout.started").exists()
