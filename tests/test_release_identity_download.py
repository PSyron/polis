from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts.release_identity import ReleaseIdentity, create_manifest
from tests.release_identity_helpers import (
    ROOT,
    _HttpReply,
    _wire_server,
    _write_metadata_artifacts,
)


def test_download_pypi_cli_writes_only_the_verified_manifest_files(
    tmp_path: Path,
) -> None:
    version = "0.2.0"
    source_commit = "a" * 40
    source = tmp_path / "source"
    source.mkdir()
    wheel, sdist = _write_metadata_artifacts(source, version)
    artifacts = (wheel, sdist)
    manifest = tmp_path / "release-manifest.json"
    output = tmp_path / "downloaded"
    output.mkdir()

    routes: dict[str, list[_HttpReply]] = {}
    with _wire_server(routes) as server:
        urls = [
            {
                "filename": artifact.name,
                "url": f"{server.base_url}/files/{artifact.name}",
                "size": artifact.stat().st_size,
                "digests": {
                    "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()
                },
            }
            for artifact in artifacts
        ]
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "version": version,
                    "tag": f"v{version}",
                    "source_commit": source_commit,
                    "artifacts": [
                        {
                            "filename": artifact.name,
                            "size": artifact.stat().st_size,
                            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                        }
                        for artifact in artifacts
                    ],
                }
            ),
            encoding="utf-8",
        )
        routes.update(
            {
                "/pypi/polis-nlp/json": [
                    _HttpReply(200, json.dumps({"urls": urls}).encode())
                ],
                **{
                    f"/files/{artifact.name}": [_HttpReply(200, artifact.read_bytes())]
                    for artifact in artifacts
                },
            }
        )
        server_requests = server.requests
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/release_identity.py"),
                "download-pypi",
                "--package-index-url",
                f"{server.base_url}/pypi/polis-nlp/json",
                "--version",
                version,
                "--manifest",
                str(manifest),
                "--source-commit",
                source_commit,
                "--output",
                str(output),
                "--max-attempts",
                "2",
                "--retry-seconds",
                "0",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        f"downloaded=2 verified=2 version={version} source_commit={source_commit}\n"
    )
    assert {path.name for path in output.iterdir()} == {item.name for item in artifacts}
    assert server_requests == [
        "/pypi/polis-nlp/json",
        f"/files/{wheel.name}",
        f"/files/{sdist.name}",
    ]


def test_download_pypi_retries_a_transient_project_index_failure(
    tmp_path: Path,
) -> None:
    version = "0.2.0"
    source_commit = "a" * 40
    source = tmp_path / "source"
    source.mkdir()
    wheel, sdist = _write_metadata_artifacts(source, version)
    manifest = create_manifest(
        ReleaseIdentity.create(version=version, source_commit=source_commit), source
    )
    manifest_path = tmp_path / "release-manifest.json"
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    output = tmp_path / "downloaded"
    output.mkdir()
    routes: dict[str, list[_HttpReply]] = {}

    with _wire_server(routes) as server:
        urls = [
            {
                "filename": artifact.name,
                "url": f"{server.base_url}/files/{artifact.name}",
                "size": artifact.stat().st_size,
                "digests": {
                    "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()
                },
            }
            for artifact in (wheel, sdist)
        ]
        routes.update(
            {
                "/pypi/polis-nlp/json": [
                    _HttpReply(503, b""),
                    _HttpReply(200, json.dumps({"urls": urls}).encode()),
                ],
                **{
                    f"/files/{artifact.name}": [_HttpReply(200, artifact.read_bytes())]
                    for artifact in (wheel, sdist)
                },
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/release_identity.py"),
                "download-pypi",
                "--package-index-url",
                f"{server.base_url}/pypi/polis-nlp/json",
                "--version",
                version,
                "--manifest",
                str(manifest_path),
                "--source-commit",
                source_commit,
                "--output",
                str(output),
                "--max-attempts",
                "2",
                "--retry-seconds",
                "0",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    assert server.requests.count("/pypi/polis-nlp/json") == 2
