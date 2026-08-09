from __future__ import annotations

import platform
import re
from collections.abc import Callable
from pathlib import Path

from polis.evaluation.holdout_attestations import (
    exact_fields,
    metadata_bytes,
    required_string,
    utc_timestamp,
)
from polis.evaluation.holdout_contract import canonical_sha256
from polis.evaluation.holdout_models import (
    HoldoutAdmissionError,
    HoldoutConfig,
    JsonObject,
)
from polis.evaluation.holdout_preregistration import (
    AUTHORIZATION_COMMENT_ID_WATERMARK,
)
from polis.evaluation.holdout_ssh_authorization import _authorization_verifier

_SHA256 = re.compile(r"[0-9a-f]{64}")
_SSH_SIGNATURE = re.compile(
    rb"-----BEGIN SSH SIGNATURE-----\n(?:[A-Za-z0-9+/=]+\n)+"
    rb"-----END SSH SIGNATURE-----\n"
)


def _platform_adapter() -> tuple[str, str]:
    return platform.system(), platform.machine()


def _read_evidence(path: Path) -> bytes:
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


def _parse_authorization(
    config_document: JsonObject,
    config: HoldoutConfig,
    source_sha: str,
    load_evidence: Callable[[Path], bytes] = _read_evidence,
) -> tuple[str, str, str]:
    observed_host = _platform_adapter()
    required_host = (
        config.authorization_signature.host_system,
        config.authorization_signature.host_machine,
    )
    if observed_host != required_host:
        raise HoldoutAdmissionError("run authorization host class mismatch")
    content = load_evidence(config.paths.run_authorization)
    raw = metadata_bytes(content, config.paths.run_authorization.name)
    fields = {
        "schema_id",
        "schema_version",
        "run_authorization",
        "repository",
        "issue_number",
        "comment_id",
        "comment_url",
        "author",
        "created_at",
        "body",
        "evaluated_source_sha",
        "config_sha256",
        "dataset_sha256",
        "preflight_completed_at",
        "wheel_sha256",
        "sdist_sha256",
        "lock_sha256",
        "operator_attestation_sha256",
        "ssh_keygen_path",
        "ssh_keygen_sha256",
    }
    exact_fields(raw, fields, "run authorization")
    payload = canonical_authorization_payload(raw)
    if content != payload:
        raise HoldoutAdmissionError(
            "run authorization must use canonical signed payload bytes"
        )
    if (raw["schema_id"], raw["schema_version"], raw["run_authorization"]) != (
        "polis.a-b-one-shot.run-authorization",
        1,
        "approved",
    ):
        raise HoldoutAdmissionError("run_authorization is not approved")
    if (
        raw["repository"] != "PSyron/polis"
        or raw["issue_number"] != 243
        or raw["author"] != "PSyron"
    ):
        raise HoldoutAdmissionError("run authorization identity is invalid")
    comment_id = raw["comment_id"]
    if type(comment_id) is not int or comment_id <= AUTHORIZATION_COMMENT_ID_WATERMARK:
        raise HoldoutAdmissionError("run authorization comment_id is invalid")
    config_sha = canonical_sha256(config_document)
    executable_path = config.authorization_signature.ssh_keygen_path
    for name, expected in (
        ("evaluated_source_sha", source_sha),
        ("config_sha256", config_sha),
        ("dataset_sha256", config.dataset.sha256),
    ):
        if raw[name] != expected:
            raise HoldoutAdmissionError(f"run authorization {name} mismatch")
    created = utc_timestamp(
        required_string(raw, "created_at", "run authorization"), "created_at"
    )
    preflight = utc_timestamp(
        required_string(raw, "preflight_completed_at", "run authorization"),
        "preflight_completed_at",
    )
    if created <= preflight:
        raise HoldoutAdmissionError("run authorization predates completed preflight")
    url = f"https://github.com/PSyron/polis/issues/243#issuecomment-{comment_id}"
    if raw["comment_url"] != url:
        raise HoldoutAdmissionError("run authorization comment_url is invalid")
    executable_sha256 = required_string(raw, "ssh_keygen_sha256", "run authorization")
    if _SHA256.fullmatch(executable_sha256) is None:
        raise HoldoutAdmissionError("run authorization ssh_keygen_sha256 is invalid")
    body = "\n".join(
        (
            "run_authorization=approved",
            f"evaluated_source_sha={source_sha}",
            f"config_sha256={config_sha}",
            f"dataset_sha256={config.dataset.sha256}",
            f"ssh_keygen_path={executable_path}",
            f"ssh_keygen_sha256={executable_sha256}",
        )
    )
    if raw["body"] != body:
        raise HoldoutAdmissionError("run authorization body is invalid")
    if raw["ssh_keygen_path"] != str(executable_path):
        raise HoldoutAdmissionError("run authorization ssh_keygen_path mismatch")
    attestation = required_string(
        raw, "operator_attestation_sha256", "run authorization"
    )
    unsigned = dict(raw)
    del unsigned["operator_attestation_sha256"]
    if (
        _SHA256.fullmatch(attestation) is None
        or canonical_sha256(unsigned) != attestation
    ):
        raise HoldoutAdmissionError("operator_attestation_sha256 mismatch")
    artifacts = (
        required_string(raw, "wheel_sha256", "run authorization"),
        required_string(raw, "sdist_sha256", "run authorization"),
        required_string(raw, "lock_sha256", "run authorization"),
    )
    if any(_SHA256.fullmatch(value) is None for value in artifacts):
        raise HoldoutAdmissionError("run authorization artifact digest is invalid")
    signature = load_evidence(config.paths.run_authorization_signature)
    if len(signature) > 4096 or _SSH_SIGNATURE.fullmatch(signature) is None:
        raise HoldoutAdmissionError("run authorization signature is invalid")
    active_verifier = _authorization_verifier(executable_sha256)
    if not active_verifier.verify(payload, signature):
        raise HoldoutAdmissionError("authorization signature verification failed")
    return artifacts


def canonical_authorization_payload(raw: JsonObject) -> bytes:
    import json

    return (
        json.dumps(
            raw,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()
