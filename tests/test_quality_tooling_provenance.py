from __future__ import annotations

import base64
import csv
import hashlib
import io
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from polis.evaluation.distribution_binding import validate_interpreter_wheel
from polis.evaluation.quality_report_models import QualityReportError
from polis.evaluation.source_binding import (
    validate_source_repository,
    validate_wheel_source_binding,
)

ROOT = Path(__file__).resolve().parents[1]


def _wheel_member_digest(content: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(
        hashlib.sha256(content).digest()
    ).decode("ascii").rstrip("=")


def _make_unrelated_wheel(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    target = "polis/__init__.py"
    members[target] += b"\n# unrelated wheel bytes\n"
    record = next(name for name in members if name.endswith(".dist-info/RECORD"))
    rows = list(csv.reader(io.StringIO(members[record].decode("utf-8"))))
    rewritten: list[list[str]] = []
    for name, _digest, _size in rows:
        if name == record:
            rewritten.append([name, "", ""])
        else:
            content = members[name]
            rewritten.append([name, _wheel_member_digest(content), str(len(content))])
    members[record] = ("\n".join(",".join(row) for row in rewritten) + "\n").encode(
        "utf-8"
    )
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_fresh_venv_binds_exact_wheel_and_rejects_unrelated_wheel(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--wheel",
            "--outdir",
            str(dist),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    wheel = next(dist.glob("*.whl"))
    environment = tmp_path / "venv"
    created = subprocess.run(
        ["uv", "venv", "--seed", str(environment)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert created.returncode == 0, created.stderr
    interpreter = environment / "bin" / "python"
    install = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(interpreter),
            "--no-deps",
            "--refresh",
            str(wheel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    validate_interpreter_wheel(str(interpreter), wheel, digest)
    validate_wheel_source_binding(wheel, ROOT)

    unrelated = tmp_path / wheel.name
    _make_unrelated_wheel(wheel, unrelated)
    with pytest.raises(QualityReportError, match="not bound|bytes"):
        validate_interpreter_wheel(
            str(interpreter),
            unrelated,
            hashlib.sha256(unrelated.read_bytes()).hexdigest(),
        )


def test_source_binding_requires_exact_clean_head_and_rejects_head_parent(
    tmp_path: Path,
) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    parent = subprocess.run(
        ["git", "rev-parse", "HEAD^"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    worktree = tmp_path / "clean-worktree"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree), head],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        validate_source_repository(head, worktree)
        with pytest.raises(QualityReportError, match="exact HEAD"):
            validate_source_repository(parent, worktree)
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
