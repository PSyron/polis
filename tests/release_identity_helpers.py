from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import threading
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.release_identity import ReleaseIdentity, read_release_policy

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class _HttpReply:
    status: int
    body: bytes
    delay_seconds: float = 0.0


@dataclass(frozen=True)
class _WireServer:
    base_url: str
    requests: list[str]


@contextmanager
def _wire_server(routes: dict[str, list[_HttpReply]]) -> Iterator[_WireServer]:
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            requests.append(self.path)
            replies = routes.get(self.path, [])
            reply = replies.pop(0) if replies else _HttpReply(404, b"")
            if reply.delay_seconds:
                threading.Event().wait(reply.delay_seconds)
            self.send_response(reply.status)
            self.send_header("Content-Length", str(len(reply.body)))
            self.end_headers()
            self.wfile.write(reply.body)

        def log_message(self, _format: str, *_args: str) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _WireServer(f"http://127.0.0.1:{server.server_port}", requests)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _candidate_command(
    *,
    server: _WireServer,
    remote: Path,
    state: str,
    version: str = "0.2.0",
    repo: Path = ROOT,
) -> list[str]:
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    return [
        sys.executable,
        str(ROOT / "scripts/release_identity.py"),
        "candidate",
        "--version",
        version,
        "--source-commit",
        source_commit,
        "--state",
        state,
        "--repo",
        str(repo),
        "--remote",
        str(remote),
        "--github-repo",
        "PSyron/polis",
        "--package-index-url",
        f"{server.base_url}/pypi/polis-nlp/json",
    ]


def _candidate_absent_checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    cloned = subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(ROOT), str(checkout)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cloned.returncode == 0, cloned.stderr
    removed = subprocess.run(
        ["git", "tag", "--delete", "v0.2.0"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    assert removed.returncode == 0, removed.stderr
    tags = subprocess.check_output(["git", "tag", "--list"], cwd=checkout, text=True)
    assert "v0.1.0" in tags.splitlines()
    assert "v0.2.0" not in tags.splitlines()
    return checkout


def _empty_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    created = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    return remote


def _cli_environment(server: _WireServer) -> dict[str, str]:
    return os.environ | {"POLIS_RELEASE_GITHUB_API_URL": server.base_url}


def test_candidate_cli_accepts_only_derived_publication_inputs() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/release_identity.py"),
            "candidate",
            "--help",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--state" in result.stdout
    assert "--latest-published" not in result.stdout


def _identity(version: str = "0.2.0rc1") -> ReleaseIdentity:
    return ReleaseIdentity.create(version=version, source_commit="a" * 40)


def _write_artifacts(dist: Path, version: str) -> tuple[Path, Path]:
    wheel = dist / f"polis_nlp-{version}-py3-none-any.whl"
    sdist = dist / f"polis_nlp-{version}.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    return wheel, sdist


def _write_metadata_artifacts(
    dist: Path, version: str, *, package_name: str = "polis-nlp"
) -> tuple[Path, Path]:
    wheel, sdist = _write_artifacts(dist, version)
    metadata = (
        f"Metadata-Version: 2.4\nName: {package_name}\nVersion: {version}\n"
    ).encode()
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"polis_nlp-{version}.dist-info/METADATA", metadata)
    with tarfile.open(sdist, "w:gz") as archive:
        info = tarfile.TarInfo(f"polis_nlp-{version}/PKG-INFO")
        info.size = len(metadata)
        archive.addfile(info, io.BytesIO(metadata))
    return wheel, sdist


def _receipt_binding_args(tmp_path: Path) -> tuple[Path, list[str]]:
    release_manifest = tmp_path / "release-manifest.json"
    wheelhouse_manifest = tmp_path / "wheelhouse-manifest.json"
    policy = tmp_path / "release-policy.json"
    receipt = tmp_path / "release-gate-receipt.json"
    release_manifest.write_text('{"release":"one"}\n', encoding="utf-8")
    wheelhouse_manifest.write_text('{"wheelhouse":"one"}\n', encoding="utf-8")
    policy.write_text(
        (ROOT / "docs/project/release-policy.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return receipt, [
        "--source-commit",
        "a" * 40,
        "--release-manifest",
        str(release_manifest),
        "--wheelhouse-manifest",
        str(wheelhouse_manifest),
        "--qualify-run-id",
        "17",
        "--plan",
        read_release_policy(policy).approved_plan_sha256,
        "--release-policy",
        str(policy),
        "--p1",
        "APPROVE",
        "--p2",
        "APPROVE",
        "--p3",
        "APPROVE",
        "--p4",
        "APPROVE",
        "--user-approval",
        "okay",
    ]
