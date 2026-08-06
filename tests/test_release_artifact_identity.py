from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.release_identity_policy import (
    GateReceiptBinding,
    create_gate_receipt,
    read_release_policy,
)
from tests.release_artifact_identity_helpers import (
    SOURCE_COMMIT,
    write_adversarial_artifacts,
    write_manifest,
)
from tests.release_workflow_helpers import (
    ROOT,
    STAGER,
    _publish_fixture,
    _pypi_server,
    _run,
)

CASES = (
    ("evil-outer", "artifact name does not match release version"),
    ("wrong-distribution-outer", "artifact name does not match release version"),
    ("wrong-version-outer", "artifact name does not match release version"),
    ("evil-wheel-suffix", "artifact name does not match release version"),
    ("platform-wheel-tag", "artifact name does not match release version"),
    ("python-two-wheel-tag", "artifact name does not match release version"),
    ("wheel-build-tag", "artifact name does not match release version"),
    ("malformed-wheel-tag", "artifact name does not match release version"),
    (
        "duplicate-wheel-metadata",
        "wheel must contain exactly one canonical package metadata record",
    ),
    (
        "conflicting-wheel-metadata",
        "wheel must contain exactly one canonical package metadata record",
    ),
    (
        "duplicate-sdist-metadata",
        "sdist must contain exactly one canonical package metadata record",
    ),
    (
        "conflicting-sdist-root",
        "sdist must contain exactly one canonical package metadata record",
    ),
)


def test_verify_manifest_rejects_malformed_json(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    write_adversarial_artifacts(dist, "canonical")
    manifest = tmp_path / "release-manifest.json"
    manifest.write_text("{", encoding="utf-8")

    result = _run(
        ROOT / "scripts/release_identity.py",
        "verify-manifest",
        "--manifest",
        str(manifest),
        "--dist",
        str(dist),
        "--source-commit",
        SOURCE_COMMIT,
    )

    assert result.returncode != 0
    assert "release manifest is not valid JSON" in result.stderr


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("size", 1, "size differs"),
        ("sha256", "0" * 64, "digest differs"),
    ),
)
def test_verify_manifest_rejects_stale_artifact_bytes(
    tmp_path: Path, field: str, value: int | str, error: str
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    write_adversarial_artifacts(dist, "canonical")
    manifest = tmp_path / "release-manifest.json"
    write_manifest(dist, manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["artifacts"][0][field] = value
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = _run(
        ROOT / "scripts/release_identity.py",
        "verify-manifest",
        "--manifest",
        str(manifest),
        "--dist",
        str(dist),
        "--source-commit",
        SOURCE_COMMIT,
    )

    assert result.returncode != 0
    assert error in result.stderr


@pytest.mark.parametrize(("case", "error"), CASES)
def test_verify_manifest_rejects_noncanonical_artifact_identity(
    tmp_path: Path, case: str, error: str
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    write_adversarial_artifacts(dist, case)
    manifest = tmp_path / "release-manifest.json"
    write_manifest(dist, manifest)

    result = _run(
        ROOT / "scripts/release_identity.py",
        "verify-manifest",
        "--manifest",
        str(manifest),
        "--dist",
        str(dist),
        "--source-commit",
        SOURCE_COMMIT,
    )

    assert result.returncode != 0
    assert "release identity check failed:" in result.stderr
    assert error in result.stderr


@pytest.mark.parametrize(("case", "error"), CASES)
def test_stage_release_upload_rejects_noncanonical_artifact_identity(
    tmp_path: Path, case: str, error: str
) -> None:
    with _pypi_server(404, b"") as package_index_url:
        arguments, output = _publish_fixture(tmp_path, package_index_url)
        dist = Path(arguments[arguments.index("--dist") + 1])
        for artifact in dist.iterdir():
            artifact.unlink()
        write_adversarial_artifacts(dist, case)
        manifest = Path(arguments[arguments.index("--release-manifest") + 1])
        write_manifest(dist, manifest)
        wheelhouse_manifest = Path(
            arguments[arguments.index("--wheelhouse-manifest") + 1]
        )
        policy = Path(arguments[arguments.index("--release-policy") + 1])
        receipt = tmp_path / "adversarial-receipt.json"
        create_gate_receipt(
            GateReceiptBinding(
                source_commit=SOURCE_COMMIT,
                release_manifest=manifest,
                wheelhouse_manifest=wheelhouse_manifest,
                qualify_run_id=17,
                plan=read_release_policy(policy).approved_plan_sha256,
                release_policy=policy,
                approvals=("APPROVE", "APPROVE", "APPROVE", "APPROVE"),
                user_approval="okay",
            ),
            receipt,
        )
        arguments[arguments.index("--receipt-json") + 1] = receipt.read_text(
            encoding="utf-8"
        ).strip()

        result = _run(STAGER, *arguments)

    assert result.returncode != 0
    assert "release upload staging failed:" in result.stderr
    assert error in result.stderr
    assert list(output.iterdir()) == []
