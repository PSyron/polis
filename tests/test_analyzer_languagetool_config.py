from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from polis import Analyzer, AnalyzerConfig, ConfigurationError


class FakeHttpTransport:
    failure: Exception | None = None

    def __init__(self, _config: object) -> None:
        self.calls: list[str] = []

    def check(
        self, text: str, *, language: str, timeout_seconds: float
    ) -> Mapping[str, object]:
        self.calls.append(text)
        if self.failure is not None:
            raise self.failure
        matches: list[object] = []
        if text != "To jest test.":
            matches.append(
                {
                    "offset": 0,
                    "length": 7,
                    "replacements": [{"value": "Wiem, że"}],
                    "rule": {"id": "BRAK_PRZECINKA_ZE"},
                }
            )
        return {
            "software": {"name": "LanguageTool", "version": "6.8"},
            "matches": matches,
        }


def _config_file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "polis.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_omitted_section_disables_languagetool() -> None:
    config = AnalyzerConfig()

    assert config.language_tool_url is None


def test_toml_section_enables_explicit_loopback_configuration(tmp_path: Path) -> None:
    config = AnalyzerConfig.from_toml(
        _config_file(
            tmp_path,
            "[language_tool]\n"
            'base_url = "http://127.0.0.1:8081"\n'
            "timeout_seconds = 0.5\n",
        )
    )

    assert config.language_tool_url == "http://127.0.0.1:8081"
    assert config.language_tool_timeout_seconds == 0.5


def test_invalid_toml_endpoint_is_configuration_error(tmp_path: Path) -> None:
    path = _config_file(
        tmp_path, '[language_tool]\nbase_url = "https://example.test"\n'
    )

    with pytest.raises(ConfigurationError, match="LanguageTool"):
        AnalyzerConfig.from_toml(path)


def test_present_section_requires_base_url(tmp_path: Path) -> None:
    path = _config_file(tmp_path, "[language_tool]\ntimeout_seconds = 0.5\n")

    with pytest.raises(ConfigurationError, match="base_url"):
        AnalyzerConfig.from_toml(path)


def test_sidecar_failure_preserves_builtin_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeHttpTransport.failure = OSError("unavailable")
    monkeypatch.setattr(
        "polis.analyzer.LoopbackLanguageToolHttpTransport", FakeHttpTransport
    )
    analyzer = Analyzer(AnalyzerConfig(language_tool_url="http://127.0.0.1:8081"))

    result = analyzer.analyze("Zeby wrócić.")

    assert any(str(finding.source) == "rule:spelling.zeby" for finding in result.issues)


def test_qualified_language_tool_sentence_rule_is_automatically_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeHttpTransport.failure = None
    monkeypatch.setattr(
        "polis.analyzer.LoopbackLanguageToolHttpTransport", FakeHttpTransport
    )
    analyzer = Analyzer(AnalyzerConfig(language_tool_url="http://127.0.0.1:8081"))

    result = analyzer.correct("Wiem że wróciła.")

    assert result.corrected_text == "Wiem, że wróciła."
    assert len(result.applied_findings) == 1
    assert result.skipped_findings == ()
    assert str(result.applied_findings[0].source) == "rule:languagetool.pl"
