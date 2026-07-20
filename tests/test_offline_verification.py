"""Offline verification checks for supported Polis workflows."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from polis import AnalysisOptions, Analyzer, AnalyzerConfig


def _block_network(*_args: object, **_kwargs: object) -> object:
    raise OSError("network blocked in offline verification")


def test_analyzer_runs_with_blocked_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "create_connection", _block_network)
    analyzer = Analyzer(AnalyzerConfig(use_local_heuristic_backend=False))
    result = analyzer.analyze("Witaj,świecie.", options=AnalysisOptions())

    assert isinstance(result.text, str)
    assert isinstance(result.issues, tuple)


def test_analyzer_with_mock_backend_runs_with_config_and_blocked_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(socket, "create_connection", _block_network)

    config_path = tmp_path / "polis.toml"
    config_path.write_text(
        """
[analysis]
categories = ["spelling", "punctuation"]

[backend]
use_mock = true
""",
        encoding="utf-8",
    )

    analyzer = Analyzer.from_config(config_path)
    result = analyzer.analyze("Witaj,świecie.")
    assert isinstance(result.text, str)
    assert result.options.minimum_confidence.value == 0.0
