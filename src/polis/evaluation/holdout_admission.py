from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from polis.evaluation.holdout_attestations import (
    exact_fields,
    metadata_object,
    required_string,
    utc_timestamp,
)
from polis.evaluation.holdout_authorization import _parse_authorization
from polis.evaluation.holdout_contract import canonical_sha256
from polis.evaluation.holdout_models import (
    AdmissionEvidence,
    HoldoutAdmissionError,
    HoldoutConfig,
    JsonObject,
)
from polis.evaluation.holdout_sources import source_sha256

_COMMIT = re.compile(r"[0-9a-f]{40}")
_GIT_OBJECT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def _load_evidence(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        if path.name == "run-authorization.sig":
            raise HoldoutAdmissionError(
                "run authorization signature is unavailable"
            ) from error
        raise HoldoutAdmissionError(
            f"required authorization evidence is unavailable: {path.name}"
        ) from error


@dataclass(frozen=True, slots=True)
class ExternalAdmission:
    evidence: AdmissionEvidence
    wheel_sha256: str
    sdist_sha256: str
    lock_sha256: str


def checkout_identity(kind: str) -> str:
    revision = "HEAD" if kind == "commit" else "HEAD^{tree}"
    result = subprocess.run(
        ["git", "rev-parse", revision], check=False, capture_output=True, text=True
    )
    value = result.stdout.strip()
    if result.returncode != 0 or _GIT_OBJECT.fullmatch(value) is None:
        raise HoldoutAdmissionError("current checkout identity is unavailable")
    return value


def verify_commit(source_sha: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "verify-commit", source_sha],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def _verified_merge(
    config: HoldoutConfig,
    *,
    identify: Callable[[str], str],
    verify: Callable[[str], bool],
    load_metadata: Callable[[Path], JsonObject],
) -> tuple[str, str]:
    merge = load_metadata(config.paths.merge_verification)
    exact_fields(
        merge,
        {
            "schema_id",
            "schema_version",
            "evaluated_source_sha",
            "evaluated_source_tree_sha256",
            "github_verification",
            "github_verification_sha256",
        },
        "merge verification",
    )
    if (
        merge["schema_id"] != "polis.a-b-one-shot.merge-verification"
        or merge["schema_version"] != 1
    ):
        raise HoldoutAdmissionError("merge verification schema is invalid")
    verification = merge["github_verification"]
    if not isinstance(verification, dict):
        raise HoldoutAdmissionError("GitHub verification payload must be an object")
    exact_fields(
        verification,
        {"verified", "reason", "signature", "payload", "verified_at"},
        "GitHub verification payload",
    )
    if verification["verified"] is not True or verification["reason"] != "valid":
        raise HoldoutAdmissionError("GitHub merge verification is not valid")
    required_string(verification, "signature", "GitHub verification")
    required_string(verification, "payload", "GitHub verification")
    utc_timestamp(
        required_string(verification, "verified_at", "GitHub verification"),
        "GitHub verification verified_at",
    )
    digest = canonical_sha256(verification)
    if merge["github_verification_sha256"] != digest:
        raise HoldoutAdmissionError("github_verification_sha256 mismatch")
    source_sha = required_string(merge, "evaluated_source_sha", "merge verification")
    source_tree = required_string(
        merge, "evaluated_source_tree_sha256", "merge verification"
    )
    if _COMMIT.fullmatch(source_sha) is None or source_sha != identify("commit"):
        raise HoldoutAdmissionError("evaluated_source_sha does not match checkout")
    if _GIT_OBJECT.fullmatch(source_tree) is None or source_tree != identify("tree"):
        raise HoldoutAdmissionError(
            "evaluated_source_tree_sha256 does not match checkout"
        )
    if not verify(source_sha):
        raise HoldoutAdmissionError("local commit signature verification failed")
    return source_sha, digest


def load_external_admission(
    config_document: JsonObject,
    config: HoldoutConfig,
    *,
    checkout_identity: Callable[[str], str] = checkout_identity,
    verify_commit: Callable[[str], bool] = verify_commit,
    load_metadata: Callable[[Path], JsonObject] = metadata_object,
    load_evidence: Callable[[Path], bytes] | None = None,
) -> ExternalAdmission:
    return _load_external_admission(
        config_document,
        config,
        checkout_identity=checkout_identity,
        verify_commit=verify_commit,
        load_metadata=load_metadata,
        load_evidence=load_evidence,
    )


def _load_external_admission(
    config_document: JsonObject,
    config: HoldoutConfig,
    *,
    checkout_identity: Callable[[str], str],
    verify_commit: Callable[[str], bool],
    load_metadata: Callable[[Path], JsonObject] = metadata_object,
    load_evidence: Callable[[Path], bytes] | None = None,
) -> ExternalAdmission:
    source_sha, verification_digest = _verified_merge(
        config,
        identify=checkout_identity,
        verify=verify_commit,
        load_metadata=load_metadata,
    )
    wheel, sdist, lock = _parse_authorization(
        config_document,
        config,
        source_sha,
        load_evidence or _load_evidence,
    )
    evidence = AdmissionEvidence(
        canonical_sha256(config_document),
        source_sha256(config),
        config.dataset.sha256,
        source_sha,
        True,
        "valid",
        verification_digest,
    )
    return ExternalAdmission(evidence, wheel, sdist, lock)
