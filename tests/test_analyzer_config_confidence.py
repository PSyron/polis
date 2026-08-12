from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from polis import AnalyzerConfig, ConfigurationError

_MESSAGE = "'analysis.minimum_confidence' must be a finite number between 0.0 and 1.0"


def _write_config(path: Path, value: str) -> Path:
    path.write_text(
        f"[analysis]\nminimum_confidence = {value}\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "value",
    ("nan", "inf", "-inf", "true", "-0.01", "1.01", '"0.5"', "[]"),
)
def test_invalid_toml_confidence_fails_during_configuration_loading(
    tmp_path: Path,
    value: str,
) -> None:
    # Given
    path = _write_config(tmp_path / "polis.toml", value)

    # When / Then
    with pytest.raises(ConfigurationError, match=_MESSAGE) as raised:
        AnalyzerConfig.from_toml(path)

    assert raised.value.code == "configuration.invalid"
    assert raised.value.retryable is False
    assert raised.value.context == {
        "operation": "configuration.load",
        "path": str(path),
    }


@pytest.mark.parametrize("value", (0.0, 1.0, 0.5))
def test_finite_toml_confidence_is_normalized_during_loading(
    tmp_path: Path,
    value: float,
) -> None:
    # Given
    path = _write_config(tmp_path / "polis.toml", str(value))

    # When
    config = AnalyzerConfig.from_toml(path)

    # Then
    assert config.minimum_confidence == value


@pytest.mark.parametrize(
    "value",
    (float("nan"), float("inf"), float("-inf"), True, -0.01, 1.01, "0.5"),
)
def test_invalid_direct_confidence_fails_during_configuration_construction(
    value: float | str | bool,
) -> None:
    with pytest.raises(ConfigurationError, match=_MESSAGE) as raised:
        AnalyzerConfig(**{"minimum_confidence": value})

    assert raised.value.code == "configuration.invalid"
    assert raised.value.retryable is False
    assert raised.value.context == {"operation": "configuration.construct"}


@pytest.mark.parametrize("value", ("nan", "inf", "-inf", "true", "-0.01", "1.01"))
def test_cli_rejects_invalid_configured_confidence_without_traceback(
    tmp_path: Path,
    value: str,
) -> None:
    # Given
    path = _write_config(tmp_path / "polis.toml", value)

    # When
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "polis.cli",
            "--config",
            str(path),
            "analyze",
            "--json",
            "Zeby",
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )

    # Then
    assert result.returncode == 2
    assert result.stdout == ""
    assert _MESSAGE in result.stderr
    assert "Traceback" not in result.stderr
