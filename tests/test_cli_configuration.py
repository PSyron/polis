from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "polis.cli", *args],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def _write_analysis_config(path: Path) -> None:
    path.write_text(
        """[analysis]
categories = ["spelling"]
minimum_confidence = 0.99
""",
        encoding="utf-8",
    )


def test_cli_uses_configured_analysis_defaults_when_flags_are_omitted(
    tmp_path: Path,
) -> None:
    # Given
    config = tmp_path / "polis.toml"
    _write_analysis_config(config)

    # When
    result = _run_cli(["--config", str(config), "analyze", "Zeby", "--json"])

    # Then
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["options"] == {
        "categories": ["spelling"],
        "minimum_confidence": 0.99,
    }
    assert payload["issues"] == []


def test_cli_category_flag_overrides_only_configured_categories(
    tmp_path: Path,
) -> None:
    # Given
    config = tmp_path / "polis.toml"
    _write_analysis_config(config)

    # When
    result = _run_cli(
        [
            "--config",
            str(config),
            "analyze",
            "Zeby",
            "--category",
            "punctuation",
            "--json",
        ]
    )

    # Then
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["options"] == {
        "categories": ["punctuation"],
        "minimum_confidence": 0.99,
    }
    assert payload["issues"] == []


def test_cli_confidence_flag_overrides_only_configured_confidence(
    tmp_path: Path,
) -> None:
    # Given
    config = tmp_path / "polis.toml"
    _write_analysis_config(config)

    # When
    result = _run_cli(
        [
            "--config",
            str(config),
            "analyze",
            "Zeby",
            "--minimum-confidence",
            "0.5",
            "--json",
        ]
    )

    # Then
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["options"] == {
        "categories": ["spelling"],
        "minimum_confidence": 0.5,
    }
    assert len(payload["issues"]) == 1


def test_cli_category_and_confidence_flags_override_both_configured_values(
    tmp_path: Path,
) -> None:
    # Given
    config = tmp_path / "polis.toml"
    _write_analysis_config(config)

    # When
    result = _run_cli(
        [
            "--config",
            str(config),
            "analyze",
            "Witaj,świecie.",
            "--category",
            "punctuation",
            "--minimum-confidence",
            "0.5",
            "--json",
        ]
    )

    # Then
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["options"] == {
        "categories": ["punctuation"],
        "minimum_confidence": 0.5,
    }
    assert len(payload["issues"]) == 1


def test_cli_without_config_or_flags_keeps_built_in_analysis_defaults() -> None:
    # Given / When
    result = _run_cli(["analyze", "Zeby", "--json"])

    # Then
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["options"] == {
        "categories": None,
        "minimum_confidence": 0.0,
    }
