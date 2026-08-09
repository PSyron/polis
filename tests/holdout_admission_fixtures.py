from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from tests.holdout_config_fixture import synthetic_config
from tests.holdout_test_helpers import (
    DATASET_SHA256,
    SOURCE_IDENTITIES,
    JsonObject,
    JsonValue,
)

from polis.evaluation.holdout_contract import canonical_sha256, parse_holdout_config
from polis.evaluation.holdout_models import HoldoutConfig, SourceIdentity


def canonical_digest(document: JsonObject) -> str:
    return hashlib.sha256(
        json.dumps(
            document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def canonical_bytes(document: JsonObject) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def ssh_keygen_identity() -> tuple[str, str]:
    path = Path("/usr/bin/ssh-keygen")
    return str(path), hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthorizationComment:
    comment_id: JsonValue = 5228447542
    created_at: str = "2026-08-08T20:20:00Z"
    preflight_completed_at: str = "2026-08-08T20:10:00Z"


DEFAULT_AUTHORIZATION_COMMENT = AuthorizationComment()


def external_evidence(
    root: Path,
    comment: AuthorizationComment = DEFAULT_AUTHORIZATION_COMMENT,
) -> tuple[JsonObject, HoldoutConfig, JsonObject, JsonObject, str, str]:
    raw = synthetic_config()
    config = parse_holdout_config(
        raw,
        source_snapshot=lambda: tuple(
            SourceIdentity(*identity) for identity in SOURCE_IDENTITIES
        ),
    )
    sealed = root / ".omo/sealed/a-b-one-shot-v1"
    sealed.mkdir(parents=True)
    verification: JsonObject = {
        "verified": True,
        "reason": "valid",
        "signature": "synthetic-signature",
        "payload": "synthetic-payload",
        "verified_at": "2026-08-08T20:00:00Z",
    }
    source_sha = "a" * 40
    source_tree = "b" * 40
    merge: JsonObject = {
        "schema_id": "polis.a-b-one-shot.merge-verification",
        "schema_version": 1,
        "evaluated_source_sha": source_sha,
        "evaluated_source_tree_sha256": source_tree,
        "github_verification": verification,
        "github_verification_sha256": canonical_digest(verification),
    }
    body = "\n".join(
        (
            "run_authorization=approved",
            f"evaluated_source_sha={source_sha}",
            f"config_sha256={canonical_sha256(raw)}",
            f"dataset_sha256={DATASET_SHA256}",
            f"ssh_keygen_path={ssh_keygen_identity()[0]}",
            f"ssh_keygen_sha256={ssh_keygen_identity()[1]}",
        )
    )
    authorization: JsonObject = {
        "schema_id": "polis.a-b-one-shot.run-authorization",
        "schema_version": 1,
        "run_authorization": "approved",
        "repository": "PSyron/polis",
        "issue_number": 243,
        "comment_id": comment.comment_id,
        "comment_url": (
            "https://github.com/PSyron/polis/issues/243#issuecomment-"
            f"{comment.comment_id}"
        ),
        "author": "PSyron",
        "created_at": comment.created_at,
        "body": body,
        "evaluated_source_sha": source_sha,
        "config_sha256": canonical_sha256(raw),
        "dataset_sha256": DATASET_SHA256,
        "preflight_completed_at": comment.preflight_completed_at,
        "wheel_sha256": "c" * 64,
        "sdist_sha256": "d" * 64,
        "lock_sha256": "e" * 64,
        "ssh_keygen_path": ssh_keygen_identity()[0],
        "ssh_keygen_sha256": ssh_keygen_identity()[1],
    }
    authorization["operator_attestation_sha256"] = canonical_digest(authorization)
    (sealed / "merge-verification.json").write_text(json.dumps(merge), encoding="utf-8")
    (sealed / "run-authorization.json").write_bytes(canonical_bytes(authorization))
    (sealed / "run-authorization.sig").write_bytes(
        b"-----BEGIN SSH SIGNATURE-----\nc3ludGhldGlj\n-----END SSH SIGNATURE-----\n"
    )
    return raw, config, merge, authorization, source_sha, source_tree


def write_authorization(root: Path, authorization: JsonObject) -> None:
    authorization.pop("operator_attestation_sha256", None)
    authorization["operator_attestation_sha256"] = canonical_digest(authorization)
    path = root / ".omo/sealed/a-b-one-shot-v1/run-authorization.json"
    path.write_bytes(canonical_bytes(authorization))


def authorization_body(authorization: JsonObject) -> str:
    return "\n".join(
        (
            "run_authorization=approved",
            f"evaluated_source_sha={authorization['evaluated_source_sha']}",
            f"config_sha256={authorization['config_sha256']}",
            f"dataset_sha256={authorization['dataset_sha256']}",
            f"ssh_keygen_path={authorization['ssh_keygen_path']}",
            f"ssh_keygen_sha256={authorization['ssh_keygen_sha256']}",
        )
    )
