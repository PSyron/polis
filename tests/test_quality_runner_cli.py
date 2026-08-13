from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from tests.quality_runner_helpers import _ARTIFACT_SHA256


def _module_command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "polis.evaluation.quality_runner", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def test_module_help_lists_only_supported_commands() -> None:
    result = _module_command("--help")

    assert result.returncode == 0
    assert "baseline" in result.stdout
    assert "validate-proposal" in result.stdout
    assert "analyze" not in result.stdout


def test_baseline_help_exposes_only_default_protocol_flags() -> None:
    result = _module_command("baseline", "--help")

    assert result.returncode == 0
    for flag in (
        "--warmup",
        "--repetitions",
        "--artifact-sha256",
        "--dataset-version",
        "--output",
        "--replace",
    ):
        assert flag in result.stdout
    for forbidden in (
        "--dataset",
        "--config",
        "--category",
        "--rule",
        "--threshold",
        "--minimum-confidence",
    ):
        assert f"{forbidden} " not in result.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ("--warmup", "-1"),
        ("--repetitions", "1"),
        ("--artifact-sha256", "a" * 63),
        ("--artifact-sha256", "A" * 64),
        ("--artifact-sha256", "g" * 64),
    ],
)
def test_baseline_rejects_invalid_protocol_values(
    arguments: tuple[str, str],
    tmp_path: Path,
) -> None:
    options = {
        "--warmup": "0",
        "--repetitions": "2",
        "--artifact-sha256": _ARTIFACT_SHA256,
    }
    options[arguments[0]] = arguments[1]
    output = tmp_path / "baseline.json"

    result = _module_command(
        "baseline",
        *(item for pair in options.items() for item in pair),
        "--output",
        str(output),
    )

    assert result.returncode == 2
    assert not output.exists()


def test_v2_baseline_requires_source_sha_and_profile(tmp_path: Path) -> None:
    output = tmp_path / "baseline.json"

    result = _module_command(
        "baseline",
        "--dataset-version",
        "v2",
        "--warmup",
        "0",
        "--repetitions",
        "2",
        "--artifact-sha256",
        _ARTIFACT_SHA256,
        "--output",
        str(output),
    )

    assert result.returncode == 2
    assert "--source-sha" in result.stderr
    assert "--profile" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    "flag",
    [
        "--dataset",
        "--config",
        "--category",
        "--rule",
        "--threshold",
        "--minimum-confidence",
    ],
)
def test_baseline_rejects_every_non_default_surface(
    flag: str,
    tmp_path: Path,
) -> None:
    output = tmp_path / "baseline.json"

    result = _module_command(
        "baseline",
        "--warmup",
        "0",
        "--repetitions",
        "2",
        "--artifact-sha256",
        _ARTIFACT_SHA256,
        "--output",
        str(output),
        flag,
        "forbidden",
    )

    assert result.returncode == 2
    assert f"unrecognized arguments: {flag} forbidden" in result.stderr
    assert not output.exists()
