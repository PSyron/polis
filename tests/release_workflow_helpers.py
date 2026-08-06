from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import threading
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.release_identity import ArtifactDigest, ReleaseIdentity, ReleaseManifest
from scripts.release_identity_policy import (
    GateReceiptBinding,
    create_gate_receipt,
    read_release_policy,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/release.yml"
WORKFLOW_VALIDATOR = ROOT / "scripts/validate_release_workflow.py"
INPUT_VALIDATOR = ROOT / "scripts/validate_release_inputs.py"
ENVIRONMENT_VALIDATOR = ROOT / "scripts/validate_release_environment.py"
STAGER = ROOT / "scripts/stage_release_upload.py"
FIXTURES = ROOT / "tests/fixtures/release"
SOURCE_COMMIT = "a" * 40
BUILD_COMMAND = "uv run --locked --extra dev python -m build --no-isolation"
EXACT_BUILD_COMMAND = f'{BUILD_COMMAND} --outdir "${{{{ runner.temp }}}}/dist"'
QUALIFY_JOB_HEADER = "  qualify:\n    if: ${{ inputs.mode == 'qualify' }}"
UPLOAD_JOB_HEADER = (
    "  upload:\n    if: ${{ inputs.mode == 'publish' || inputs.mode == 'recover' }}"
)


@contextmanager
def _pypi_server(status: int, body: bytes) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: str) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/pypi/polis-nlp/json"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _run(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def _replace_occurrence(
    text: str, needle: str, replacement: str, occurrence: int
) -> str:
    start = 0
    for _ in range(occurrence + 1):
        index = text.find(needle, start)
        assert index >= 0
        start = index + len(needle)
    return text[:index] + replacement + text[index + len(needle) :]


def _publish_fixture(
    tmp_path: Path, package_index_url: str = "http://127.0.0.1:9/unreachable"
) -> tuple[list[str], Path]:
    dist = tmp_path / "dist"
    dist.mkdir()
    metadata = b"Metadata-Version: 2.4\nName: polis-nlp\nVersion: 0.2.0\n"
    wheel = dist / "polis_nlp-0.2.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("polis_nlp-0.2.0.dist-info/METADATA", metadata)
    sdist = dist / "polis_nlp-0.2.0.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        info = tarfile.TarInfo("polis_nlp-0.2.0/PKG-INFO")
        info.size = len(metadata)
        archive.addfile(info, io.BytesIO(metadata))
    manifest = tmp_path / "release-manifest.json"
    artifacts = tuple(
        ArtifactDigest(
            path.name,
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(dist.iterdir())
    )
    manifest.write_text(
        ReleaseManifest(
            ReleaseIdentity.create(version="0.2.0", source_commit=SOURCE_COMMIT),
            artifacts,
        ).to_json(),
        encoding="utf-8",
    )
    wheelhouse_manifest = tmp_path / "wheelhouse-manifest.json"
    wheelhouse_manifest.write_text('{"wheelhouse":"bound"}\n', encoding="utf-8")
    policy = ROOT / "docs/project/release-policy.json"
    receipt = tmp_path / "receipt.json"
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
    output = tmp_path / "publish"
    output.mkdir()
    arguments = [
        "--mode",
        "publish",
        "--source-commit",
        SOURCE_COMMIT,
        "--artifact-run-id",
        "17",
        "--run-metadata",
        str(FIXTURES / "run-valid.json"),
        "--receipt-json",
        receipt.read_text(encoding="utf-8").strip(),
        "--release-manifest",
        str(manifest),
        "--wheelhouse-manifest",
        str(wheelhouse_manifest),
        "--release-policy",
        str(policy),
        "--plan",
        read_release_policy(policy).approved_plan_sha256,
        "--dist",
        str(dist),
        "--output",
        str(output),
        "--package-index-url",
        package_index_url,
    ]
    return arguments, output


def _pypi_release_payload(
    arguments: list[str], existing_filenames: tuple[str, ...]
) -> bytes:
    manifest_path = Path(arguments[arguments.index("--release-manifest") + 1])
    manifest = ReleaseManifest.from_json(manifest_path.read_text(encoding="utf-8"))
    files = [
        {
            "filename": artifact.filename,
            "size": artifact.size,
            "digests": {"sha256": artifact.sha256},
        }
        for artifact in manifest.artifacts
        if artifact.filename in existing_filenames
    ]
    return json.dumps({"releases": {"0.2.0": files}}).encode()
