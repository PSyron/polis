from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import scripts.verify_prerelease_candidate as prerelease

ROOT = Path(__file__).resolve().parents[1]


def _clean_checkout(tmp_path: Path) -> tuple[Path, str]:
    checkout = tmp_path / "checkout"
    clone = subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(ROOT), str(checkout)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert clone.returncode == 0, clone.stderr
    shutil.copyfile(
        ROOT / "scripts/verify_prerelease_candidate.py",
        checkout / "scripts/verify_prerelease_candidate.py",
    )
    stage = subprocess.run(
        ["git", "add", "scripts/verify_prerelease_candidate.py"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    assert stage.returncode == 0, stage.stderr
    commit = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Polis test",
            "-c",
            "user.email=polis-test@example.invalid",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "test prerelease source state",
        ],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    assert commit.returncode == 0, commit.stderr
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    assert head.returncode == 0, head.stderr
    return checkout, head.stdout.strip()


def _prerelease_command(checkout: Path, source_commit: str, dist: Path) -> list[str]:
    return [
        sys.executable,
        str(checkout / "scripts/verify_prerelease_candidate.py"),
        "--source-commit",
        source_commit,
        "--dist",
        str(dist),
        "--manifest",
        str(dist / "release-manifest.json"),
        "--wheelhouse",
        str(checkout / "wheelhouse"),
        "--wheelhouse-manifest",
        str(checkout / "wheelhouse-manifest.json"),
    ]


def _fake_uv_environment(tmp_path: Path) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "uv-invocations.log"
    if os.name == "nt":
        executable = bin_dir / "uv.cmd"
        executable.write_text(
            "@echo off\r\necho %CD%>>%POLIS_FAKE_UV_LOG%\r\nexit /b 0\r\n",
            encoding="utf-8",
        )
    else:
        executable = bin_dir / "uv"
        executable.write_text(
            '#!/bin/sh\npwd >> "$POLIS_FAKE_UV_LOG"\n',
            encoding="utf-8",
        )
        executable.chmod(executable.stat().st_mode | 0o111)
    return (
        os.environ
        | {
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "POLIS_FAKE_UV_LOG": str(log),
        },
        log,
    )


def test_prerelease_candidate_uses_the_product_only_pytest_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dist = tmp_path / "dist"
    wheel = dist / "polis_nlp-0.2.0.dev0-py3-none-any.whl"
    sdist = dist / "polis_nlp-0.2.0.dev0.tar.gz"
    dist.mkdir()
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    calls: list[list[str]] = []

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify-prerelease",
            "--source-commit",
            "a" * 40,
            "--wheelhouse",
            str(tmp_path / "wheelhouse"),
            "--wheelhouse-manifest",
            str(tmp_path / "wheelhouse-manifest.json"),
        ],
    )
    monkeypatch.setattr(prerelease, "_require_source_state", lambda _commit: tmp_path)
    monkeypatch.setattr(prerelease, "_run", lambda cmd, cwd=None: calls.append(cmd))
    monkeypatch.setattr(prerelease, "_collect_artifacts", lambda _dist: (wheel, sdist))
    monkeypatch.setattr(prerelease, "_print_hashes", lambda _wheel, _sdist: None)

    prerelease.main()

    pytest_call = next(cmd for cmd in calls if "pytest" in cmd)
    marker_index = pytest_call.index("-m")
    assert pytest_call[marker_index + 1] == "not research and not slow"

    artifact_index = next(
        index
        for index, command in enumerate(calls)
        if "scripts/verify_distribution_artifacts.py" in command
    )
    install_index = next(
        index
        for index, command in enumerate(calls)
        if "scripts/verify_distribution_install.py" in command
    )
    manifest_index = next(
        index
        for index, command in enumerate(calls)
        if "scripts/release_identity.py" in command
    )
    assert artifact_index < install_index < manifest_index
    assert "--wheelhouse" in calls[install_index]
    assert "--wheelhouse-manifest" in calls[install_index]
    assert "--smoke-cwd" in calls[install_index]


def test_public_prerelease_verifier_requires_wheelhouse_inputs() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "scripts/verify_prerelease_candidate.py"),
            "--source-commit",
            "a" * 40,
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "--wheelhouse" in result.stderr
    assert "--wheelhouse-manifest" in result.stderr


def test_public_prerelease_verifier_accepts_current_head_from_clean_worktree(
    tmp_path: Path,
) -> None:
    checkout, head = _clean_checkout(tmp_path)
    dist = checkout / "dist"
    dist.mkdir()
    (dist / "polis_nlp-0.2.0.dev0-py3-none-any.whl").write_bytes(b"wheel")
    (dist / "polis_nlp-0.2.0.dev0.tar.gz").write_bytes(b"sdist")
    env, uv_log = _fake_uv_environment(tmp_path)

    result = subprocess.run(
        _prerelease_command(checkout, head, dist),
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert uv_log.read_text(encoding="utf-8").splitlines() == [str(checkout)] * 8


def test_public_prerelease_verifier_runs_children_from_preflighted_checkout(
    tmp_path: Path,
) -> None:
    checkout, head = _clean_checkout(tmp_path)
    external_cwd = tmp_path / "external-cwd"
    external_cwd.mkdir()
    dist = checkout / "dist"
    dist.mkdir()
    (dist / "polis_nlp-0.2.0.dev0-py3-none-any.whl").write_bytes(b"wheel")
    (dist / "polis_nlp-0.2.0.dev0.tar.gz").write_bytes(b"sdist")
    env, uv_log = _fake_uv_environment(tmp_path)

    result = subprocess.run(
        _prerelease_command(checkout, head, dist),
        cwd=external_cwd,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert uv_log.read_text(encoding="utf-8").splitlines() == [str(checkout)] * 8
    assert list(external_cwd.iterdir()) == []


def test_public_prerelease_verifier_rejects_stale_source_commit_before_build(
    tmp_path: Path,
) -> None:
    checkout, _ = _clean_checkout(tmp_path)
    dist = checkout / "candidate-dist"
    env, uv_log = _fake_uv_environment(tmp_path)

    result = subprocess.run(
        _prerelease_command(checkout, "0" * 40, dist),
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode != 0
    assert "source commit" in result.stderr.lower()
    assert not dist.exists()
    assert not uv_log.exists()


def test_public_prerelease_verifier_rejects_dirty_worktree_before_build(
    tmp_path: Path,
) -> None:
    checkout, head = _clean_checkout(tmp_path)
    readme = checkout / "README.md"
    original = readme.read_bytes()
    readme.write_bytes(original + b"\n")
    dist = checkout / "candidate-dist"
    env, uv_log = _fake_uv_environment(tmp_path)
    try:
        result = subprocess.run(
            _prerelease_command(checkout, head, dist),
            cwd=checkout,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
    finally:
        readme.write_bytes(original)

    clean = subprocess.run(
        ["git", "diff", "--quiet", "--", "README.md"],
        cwd=checkout,
        check=False,
    )
    assert clean.returncode == 0
    assert result.returncode != 0
    assert "worktree" in result.stderr.lower()
    assert not dist.exists()
    assert not uv_log.exists()
