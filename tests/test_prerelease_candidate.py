from __future__ import annotations

import sys
from pathlib import Path

import pytest
import scripts.verify_prerelease_candidate as prerelease


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

    monkeypatch.setattr(sys, "argv", ["verify-prerelease", "--source-commit", "a" * 40])
    monkeypatch.setattr(prerelease, "_run", lambda cmd, cwd=None: calls.append(cmd))
    monkeypatch.setattr(prerelease, "_collect_artifacts", lambda _dist: (wheel, sdist))
    monkeypatch.setattr(prerelease, "_print_hashes", lambda _wheel, _sdist: None)

    prerelease.main()

    pytest_call = next(cmd for cmd in calls if "pytest" in cmd)
    marker_index = pytest_call.index("-m")
    assert pytest_call[marker_index + 1] == "not research and not slow and not model"
