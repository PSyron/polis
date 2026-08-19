"""Exact clean-source binding for reproducible evaluation artifacts."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from polis.evaluation.quality_report_models import QualityReportError


def validate_source_repository(source_sha: str, repository: Path | None = None) -> None:
    """Require ``source_sha`` to be the clean tracked HEAD of ``repository``."""

    repository_path = (repository or Path.cwd()).resolve()
    try:
        root = subprocess.run(
            ["git", "-C", str(repository_path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        resolved = subprocess.run(
            ["git", "-C", root, "rev-parse", "--verify", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            [
                "git",
                "-C",
                root,
                "status",
                "--porcelain=v1",
                "--untracked-files=no",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise QualityReportError(
            "v4 source SHA cannot be bound to the requested repository/worktree"
        ) from error
    if resolved != source_sha:
        raise QualityReportError(
            "v4 source SHA must match the exact HEAD of the repository/worktree"
        )
    if status:
        raise QualityReportError(
            "v4 source repository/worktree must have a clean tracked tree"
        )


def validate_wheel_source_binding(wheel: Path, repository: Path | None = None) -> None:
    """Require every shipped source member in ``wheel`` to match ``repository``."""

    root = (repository or Path.cwd()).resolve()
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise QualityReportError("v4 wheel archive contains duplicate members")
            source_members = [
                name
                for name in names
                if not name.endswith("/") and ".dist-info/" not in name
            ]
            for name in source_members:
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts:
                    raise QualityReportError("v4 wheel source member path is malformed")
                if name.startswith("polis/"):
                    source_path = root / "src" / Path(*path.parts)
                elif name.startswith("docs/"):
                    source_path = root / Path(*path.parts)
                else:
                    raise QualityReportError(
                        f"v4 wheel source member is outside repository sources: {name}"
                    )
                if (
                    not source_path.is_file()
                    or archive.read(name) != source_path.read_bytes()
                ):
                    raise QualityReportError(
                        f"v4 wheel source member does not match repository HEAD: {name}"
                    )
    except (OSError, zipfile.BadZipFile) as error:
        raise QualityReportError(
            "v4 wheel source binding archive is invalid"
        ) from error


__all__ = ["validate_source_repository", "validate_wheel_source_binding"]
