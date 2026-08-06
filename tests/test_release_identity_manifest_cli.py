from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import scripts.release_identity as release_identity_module
from scripts.release_identity import (
    ReleaseIdentity,
    ReleaseManifest,
    create_manifest,
    main,
)
from tests.release_identity_helpers import ROOT, _write_metadata_artifacts


def test_manifest_cli_records_one_build_once_artifact_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        release_identity_module,
        "_require_source_commit",
        lambda *_args, **_kwargs: None,
    )
    version = "0.2.0.dev0"
    _write_metadata_artifacts(tmp_path, version)
    project = tmp_path / "pyproject.toml"
    project.write_text(f"[project]\nversion = '{version}'\n", encoding="utf-8")
    output = tmp_path / "release-manifest.json"

    assert (
        main(
            [
                "manifest",
                "--pyproject",
                str(project),
                "--source-commit",
                "b" * 40,
                "--dist",
                str(tmp_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    manifest = ReleaseManifest.from_json(output.read_text(encoding="utf-8"))
    assert str(manifest.identity.version) == version
    manifest.verify_artifacts(tmp_path)


def test_verify_manifest_cli_binds_sizes_hashes_and_metadata(tmp_path: Path) -> None:
    version = "0.2.0"
    wheel, sdist = _write_metadata_artifacts(tmp_path, version)
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    manifest = tmp_path / "release-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "version": version,
                "tag": f"v{version}",
                "source_commit": source_commit,
                "artifacts": [
                    {
                        "filename": wheel.name,
                        "size": wheel.stat().st_size,
                        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    },
                    {
                        "filename": sdist.name,
                        "size": sdist.stat().st_size,
                        "sha256": hashlib.sha256(sdist.read_bytes()).hexdigest(),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/release_identity.py"),
            "verify-manifest",
            "--manifest",
            str(manifest),
            "--dist",
            str(tmp_path),
            "--source-commit",
            source_commit,
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        f"verified=2 version={version} source_commit={source_commit}\n"
    )


@pytest.mark.parametrize("command", ["manifest", "verify-manifest"])
def test_manifest_cli_rejects_artifacts_with_an_unexpected_metadata_name(
    tmp_path: Path, command: str
) -> None:
    version = "0.2.0"
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    manifest = tmp_path / "release-manifest.json"
    project = tmp_path / "pyproject.toml"
    project.write_text(f"[project]\nversion = '{version}'\n", encoding="utf-8")
    if command == "manifest":
        _write_metadata_artifacts(tmp_path, version, package_name="evil-package")
        arguments = [
            "manifest",
            "--pyproject",
            str(project),
            "--repo",
            str(ROOT),
            "--source-commit",
            source_commit,
            "--dist",
            str(tmp_path),
            "--output",
            str(manifest),
        ]
    else:
        wheel, sdist = _write_metadata_artifacts(tmp_path, version)
        manifest.write_text(
            create_manifest(
                ReleaseIdentity.create(version=version, source_commit=source_commit),
                tmp_path,
            ).to_json(),
            encoding="utf-8",
        )
        _write_metadata_artifacts(tmp_path, version, package_name="evil-package")
        arguments = [
            "verify-manifest",
            "--manifest",
            str(manifest),
            "--dist",
            str(tmp_path),
            "--source-commit",
            source_commit,
        ]

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/release_identity.py"), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "metadata name" in result.stderr
