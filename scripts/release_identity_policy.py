from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.release_identity_authority import JsonValue
from scripts.release_identity_models import (
    COMMIT_RE,
    SHA256_RE,
    ReleaseIdentityError,
    ReleasePolicy,
)

_APPROVED_PLAN_SHA256 = (
    "98d87cec471291987d7df83fb8ee14382978349ef4f517dfec89567fdcc0d9b9"
)
_RECEIPT_FIELDS = {
    "schema_version",
    "source_commit",
    "release_manifest_sha256",
    "wheelhouse_manifest_sha256",
    "qualify_run_id",
    "plan_sha256",
    "approvals",
    "user_approval",
    "recorded_at",
}
_APPROVALS = {"P1", "P2", "P3", "P4"}
_RECORDED_AT_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


@dataclass(frozen=True)
class GateReceiptBinding:
    source_commit: str
    release_manifest: Path
    wheelhouse_manifest: Path
    qualify_run_id: int
    plan: str
    release_policy: Path
    approvals: tuple[str, str, str, str]
    user_approval: str


def read_release_policy(policy: Path) -> ReleasePolicy:
    try:
        payload = json.loads(policy.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseIdentityError("release policy is unreadable") from error
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "approved_plan_sha256",
    }:
        raise ReleaseIdentityError("release policy has an invalid schema")
    schema_version = payload["schema_version"]
    digest = payload["approved_plan_sha256"]
    if schema_version != 1 or isinstance(schema_version, bool):
        raise ReleaseIdentityError("release policy schema version is invalid")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise ReleaseIdentityError("release policy digest must be lowercase SHA-256")
    if digest != _APPROVED_PLAN_SHA256:
        raise ReleaseIdentityError(
            "release policy digest does not match the approved plan"
        )
    return ReleasePolicy(digest)


def create_gate_receipt(binding: GateReceiptBinding, output: Path) -> None:
    validate_binding(binding)
    if output.exists() or output.is_symlink():
        raise ReleaseIdentityError("release gate receipt output already exists")
    if not output.parent.is_dir():
        raise ReleaseIdentityError("release gate receipt output parent is unavailable")
    payload = receipt_payload(binding)
    try:
        with output.open("x", encoding="utf-8") as target:
            target.write(
                json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
            )
    except OSError as error:
        raise ReleaseIdentityError(
            "release gate receipt output is unwritable"
        ) from error


def validate_gate_receipt(receipt: Path, binding: GateReceiptBinding) -> None:
    validate_binding(binding)
    expected_plan = read_release_policy(binding.release_policy).approved_plan_sha256
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseIdentityError("release gate receipt is unreadable") from error
    if not isinstance(payload, dict) or set(payload) != _RECEIPT_FIELDS:
        raise ReleaseIdentityError("release gate receipt has an invalid schema")
    validate_receipt_values(payload, expected_plan)
    expected = receipt_payload(binding)
    for field in _RECEIPT_FIELDS - {"recorded_at"}:
        if payload[field] != expected[field]:
            raise ReleaseIdentityError(
                f"release gate receipt {field} does not match bound input"
            )


def validate_binding(binding: GateReceiptBinding) -> None:
    expected_plan = read_release_policy(binding.release_policy).approved_plan_sha256
    if not COMMIT_RE.fullmatch(binding.source_commit):
        raise ReleaseIdentityError("release gate receipt source commit is invalid")
    if (
        not isinstance(binding.qualify_run_id, int)
        or isinstance(binding.qualify_run_id, bool)
        or binding.qualify_run_id < 1
    ):
        raise ReleaseIdentityError("release gate receipt qualify run id is invalid")
    if plan_sha256(binding.plan) != expected_plan:
        raise ReleaseIdentityError(
            "release gate receipt plan digest does not match policy"
        )
    if binding.approvals != ("APPROVE", "APPROVE", "APPROVE", "APPROVE"):
        raise ReleaseIdentityError("release gate receipt approvals are invalid")
    if binding.user_approval != "okay":
        raise ReleaseIdentityError("release gate receipt user approval is invalid")
    manifest_sha256(binding.release_manifest)
    manifest_sha256(binding.wheelhouse_manifest)


def receipt_payload(binding: GateReceiptBinding) -> dict[str, JsonValue]:
    return {
        "schema_version": 1,
        "source_commit": binding.source_commit,
        "release_manifest_sha256": manifest_sha256(binding.release_manifest),
        "wheelhouse_manifest_sha256": manifest_sha256(binding.wheelhouse_manifest),
        "qualify_run_id": binding.qualify_run_id,
        "plan_sha256": plan_sha256(binding.plan),
        "approvals": {
            "P1": binding.approvals[0],
            "P2": binding.approvals[1],
            "P3": binding.approvals[2],
            "P4": binding.approvals[3],
        },
        "user_approval": binding.user_approval,
        "recorded_at": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }


def manifest_sha256(manifest: Path) -> str:
    if not manifest.is_file():
        raise ReleaseIdentityError("release gate receipt manifest input is unavailable")
    digest = hashlib.sha256()
    try:
        with manifest.open("rb") as source:
            for chunk in iter(lambda: source.read(8192), b""):
                digest.update(chunk)
    except OSError as error:
        raise ReleaseIdentityError(
            "release gate receipt manifest input is unreadable"
        ) from error
    return digest.hexdigest()


def plan_sha256(plan: str) -> str:
    candidate = Path(plan)
    if candidate.is_file():
        return manifest_sha256(candidate)
    if SHA256_RE.fullmatch(plan):
        return plan
    raise ReleaseIdentityError("release gate receipt plan input is invalid")


def validate_receipt_values(payload: dict[str, JsonValue], expected_plan: str) -> None:
    schema_version = payload["schema_version"]
    source_commit = payload["source_commit"]
    release_manifest = payload["release_manifest_sha256"]
    wheelhouse_manifest = payload["wheelhouse_manifest_sha256"]
    run_id = payload["qualify_run_id"]
    plan = payload["plan_sha256"]
    approvals = payload["approvals"]
    user_approval = payload["user_approval"]
    recorded_at = payload["recorded_at"]
    if schema_version != 1 or isinstance(schema_version, bool):
        raise ReleaseIdentityError("release gate receipt schema version is invalid")
    if not isinstance(source_commit, str) or not COMMIT_RE.fullmatch(source_commit):
        raise ReleaseIdentityError("release gate receipt source commit is invalid")
    if not isinstance(release_manifest, str) or not SHA256_RE.fullmatch(
        release_manifest
    ):
        raise ReleaseIdentityError(
            "release gate receipt release manifest digest is invalid"
        )
    if not isinstance(wheelhouse_manifest, str) or not SHA256_RE.fullmatch(
        wheelhouse_manifest
    ):
        raise ReleaseIdentityError(
            "release gate receipt wheelhouse manifest digest is invalid"
        )
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
        raise ReleaseIdentityError("release gate receipt qualify run id is invalid")
    if not isinstance(plan, str) or plan != expected_plan:
        raise ReleaseIdentityError(
            "release gate receipt plan digest does not match policy"
        )
    if (
        not isinstance(approvals, dict)
        or set(approvals) != _APPROVALS
        or any(value != "APPROVE" for value in approvals.values())
    ):
        raise ReleaseIdentityError("release gate receipt approvals are invalid")
    if not isinstance(user_approval, str) or user_approval != "okay":
        raise ReleaseIdentityError("release gate receipt user approval is invalid")
    if not isinstance(recorded_at, str) or not _RECORDED_AT_RE.fullmatch(recorded_at):
        raise ReleaseIdentityError("release gate receipt timestamp is invalid")
    try:
        datetime.strptime(recorded_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ReleaseIdentityError(
            "release gate receipt timestamp is invalid"
        ) from error
