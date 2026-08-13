from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from tests.holdout_config_fixture import synthetic_config
from tests.holdout_test_helpers import (
    CONFIG_SHA256,
    DATASET_SHA256,
    SOURCE_IDENTITIES,
    JsonObject,
)

from polis.evaluation.holdout_models import SourceIdentity


class _DatasetView(Protocol):
    sha256: str
    case_count: int
    source_count: int
    mode: str
    review_status: str


class _SignatureView(Protocol):
    method: str


class _AuthorizationSignatureView(Protocol):
    host_system: str
    host_machine: str
    ssh_keygen_path: Path


class _FailurePolicyView(Protocol):
    retry: str


class _PathsView(Protocol):
    marker: Path
    raw_report: Path
    normalized_report: Path
    result_manifest: Path
    dataset: Path
    merge_verification: Path
    run_authorization: Path
    run_authorization_signature: Path


class _ParsedConfigView(Protocol):
    dataset: _DatasetView
    signature: _SignatureView
    authorization_signature: _AuthorizationSignatureView
    failure_policy: _FailurePolicyView
    paths: _PathsView


@runtime_checkable
class _ContractApi(Protocol):
    def parse_holdout_config(
        self,
        raw: JsonObject,
        *,
        source_snapshot: object | None = None,
    ) -> _ParsedConfigView: ...

    def canonical_sha256(self, raw: JsonObject) -> str: ...


def _frozen_sources() -> tuple[SourceIdentity, ...]:
    return tuple(SourceIdentity(*identity) for identity in SOURCE_IDENTITIES)


def _contract() -> _ContractApi:
    try:
        module = importlib.import_module("polis.evaluation.holdout_contract")
    except ModuleNotFoundError as error:
        raise AssertionError(
            "planned preregistration parser implementation is absent"
        ) from error
    if not isinstance(module, _ContractApi):
        raise AssertionError("planned preregistration parser API is incomplete")
    return module


def test_preregistration_binds_approved_decisions_without_plaintext() -> None:
    raw = synthetic_config()
    parsed = _contract().parse_holdout_config(raw, source_snapshot=_frozen_sources)

    assert parsed.dataset.sha256 == DATASET_SHA256
    assert parsed.dataset.case_count == 52
    assert parsed.dataset.source_count == 20
    assert parsed.dataset.mode == "0600"
    assert parsed.dataset.review_status == "APPROVE"
    assert parsed.signature.method == "github-verified-merge-commit"
    assert parsed.authorization_signature.host_system == "Darwin"
    assert parsed.authorization_signature.host_machine == "arm64"
    assert parsed.authorization_signature.ssh_keygen_path == Path("/usr/bin/ssh-keygen")
    assert parsed.failure_policy.retry == "never"


def test_preregistered_paths_contain_only_future_artifact_names() -> None:
    parsed = _contract().parse_holdout_config(
        synthetic_config(), source_snapshot=_frozen_sources
    )

    assert parsed.paths.marker.name == "holdout.started"
    assert parsed.paths.raw_report.name == "report.json"
    assert parsed.paths.normalized_report.name == "normalized-report.json"
    assert parsed.paths.result_manifest.name == "result.manifest.json"
    assert not parsed.paths.dataset.is_absolute()
    assert parsed.paths.merge_verification.name == "merge-verification.json"
    assert parsed.paths.run_authorization.name == "run-authorization.json"
    assert parsed.paths.run_authorization_signature.name == "run-authorization.sig"


def test_tracked_preregistration_uses_the_strict_contract() -> None:
    config_path = Path("experiments/a-b-one-shot/config.json")
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)

    parsed = _contract().parse_holdout_config(raw, source_snapshot=_frozen_sources)

    assert parsed.dataset.sha256 == DATASET_SHA256
    assert _contract().canonical_sha256(raw) == CONFIG_SHA256


def test_tracked_preregistration_binds_independent_review_identity() -> None:
    raw = json.loads(Path("experiments/a-b-one-shot/preregistration.json").read_bytes())
    assert isinstance(raw, dict)

    assert raw["dataset_review_reviewer_role"] == "independent-dataset-reviewer"
    assert raw["dataset_review_verdict"] == "APPROVE"
    assert raw["dataset_review_coverage"] == "52/52"
    assert raw["dataset_review_manifest_sha256"] == (
        "f58f7c81ee46cb25968ca84e1f0ce6a842b14181c6151f041a4f30225aab3e4d"
    )
    assert raw["dataset_review_payload_sha256"] == (
        "f5312a257d634f240301dbdfe47fad3b0897e4a4e7f11f10af3a51df0a777cd0"
    )
    assert raw["authorization_signature_method"] == "ssh-ed25519-detached"
    assert raw["authorization_signer_identity"] == "PSyron"
    assert raw["authorization_signature_namespace"] == (
        "polis-holdout-authorization-v1"
    )
    assert raw["authorization_trusted_key_fingerprint"] == (
        "SHA256:JvdjEgHYEQPsrsthSO5GnrM7saNvsanY5uJl89B0lQk"
    )
    assert raw["authorization_signed_payload"] == (
        "canonical-json-sort-keys-compact-utf8-final-lf"
    )
    assert raw["authorization_host_system"] == "Darwin"
    assert raw["authorization_host_machine"] == "arm64"
    assert raw["authorization_ssh_keygen_path"] == "/usr/bin/ssh-keygen"
    assert raw["distribution"] == "repository-only-excluded-from-wheel-and-sdist"
