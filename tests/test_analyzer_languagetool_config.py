from __future__ import annotations

import json
import os
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath

import pytest

from polis import Analyzer, AnalyzerConfig, ConfigurationError
from polis.rules.languagetool_stdio import LocalLanguageToolStdioSession

ROOT = Path(__file__).resolve().parents[1]
FAKE_STDIO_SERVER = ROOT / "tests" / "fixtures" / "fake_languagetool_stdio.py"


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


def _toml_string(value: str | os.PathLike[str]) -> str:
    return json.dumps(os.fspath(value), ensure_ascii=False)


def _replace_owned_session(
    monkeypatch: pytest.MonkeyPatch, session: LocalLanguageToolStdioSession
) -> None:
    def create_session(
        _executable: Path, *, timeout_seconds: float
    ) -> LocalLanguageToolStdioSession:
        assert timeout_seconds > 0
        return session

    monkeypatch.setattr(
        LocalLanguageToolStdioSession, "from_executable", create_session
    )


def test_analyzer_exposes_only_owned_language_tool_process_start_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = LocalLanguageToolStdioSession(("unused",), timeout_seconds=1.0)
    _replace_owned_session(monkeypatch, session)
    analyzer = Analyzer(
        AnalyzerConfig(
            vendored_language_tool_stdio_path=str(Path(sys.executable).resolve())
        )
    )

    assert analyzer.language_tool_process_start_count == 0
    session.process_start_count = 1
    assert analyzer.language_tool_process_start_count == 1


def test_toml_path_fixture_preserves_windows_backslashes() -> None:
    path = PureWindowsPath("C:/Users/Paweł/LanguageTool/run_stdio.cmd")

    parsed = tomllib.loads(f"stdio_path = {_toml_string(path)}\n")

    assert parsed["stdio_path"] == os.fspath(path)


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


def test_contextual_inflection_section_requires_absolute_executable(
    tmp_path: Path,
) -> None:
    runner = Path(sys.executable).resolve()
    config = AnalyzerConfig.from_toml(
        _config_file(
            tmp_path,
            "[contextual_inflection]\n"
            f"stdio_path = {_toml_string(runner)}\n"
            "timeout_seconds = 2.5\n",
        )
    )

    assert config.contextual_inflection_stdio_path == str(runner)
    assert config.contextual_inflection_timeout_seconds == 2.5

    with pytest.raises(ConfigurationError, match="stdio_path"):
        AnalyzerConfig.from_toml(_config_file(tmp_path, "[contextual_inflection]\n"))


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


def test_vendored_stdio_configuration_requires_absolute_executable(
    tmp_path: Path,
) -> None:
    runner = Path(sys.executable).resolve()

    config = AnalyzerConfig.from_toml(
        _config_file(
            tmp_path,
            "[vendored_language_tool]\n"
            f"stdio_path = {_toml_string(runner)}\n"
            "timeout_seconds = 2.0\n",
        )
    )

    assert config.vendored_language_tool_stdio_path == str(runner)
    assert config.vendored_language_tool_timeout_seconds == 2.0


@pytest.mark.parametrize(
    "body",
    (
        "[vendored_language_tool]\n",
        '[vendored_language_tool]\nstdio_path = "relative/run_stdio.sh"\n',
        "[vendored_language_tool]\nstdio_path = 7\n",
        '[vendored_language_tool]\nstdio_path = "/missing/run_stdio.sh"\n',
        '[vendored_language_tool]\nstdio_path = "/bin/sh"\ntimeout_seconds = 0\n',
    ),
)
def test_invalid_vendored_stdio_configuration_is_controlled(
    tmp_path: Path,
    body: str,
) -> None:
    with pytest.raises(ConfigurationError, match="vendored|stdio|configuration"):
        AnalyzerConfig.from_toml(_config_file(tmp_path, body))


def test_vendored_stdio_mode_rejects_competing_transports() -> None:
    runner = Path(sys.executable).resolve()

    with pytest.raises(ValueError, match="mutually exclusive"):
        AnalyzerConfig(
            language_tool_url="http://127.0.0.1:8081",
            vendored_language_tool_stdio_path=str(runner),
        )
    with pytest.raises(ValueError, match="mutually exclusive"):
        AnalyzerConfig(
            contextual_inflection_stdio_path=str(runner),
            vendored_language_tool_stdio_path=str(runner),
        )


def test_vendored_session_serves_automatic_and_reviewable_sentence_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = LocalLanguageToolStdioSession(
        (sys.executable, str(FAKE_STDIO_SERVER)), timeout_seconds=1.0
    )
    _replace_owned_session(monkeypatch, session)

    with Analyzer(
        AnalyzerConfig(
            vendored_language_tool_stdio_path=str(Path(sys.executable).resolve()),
            vendored_language_tool_timeout_seconds=1.0,
        )
    ) as analyzer:
        punctuation = analyzer.correct("Wiem że wróciła.")
        inflection = analyzer.correct("Rozmawiałem z Janem Nowak po przerwie.")

    assert punctuation.corrected_text == "Wiem, że wróciła."
    assert str(punctuation.applied_findings[0].source) == "rule:languagetool.pl"
    assert inflection.corrected_text == inflection.original_text
    inflection_finding = next(
        finding
        for finding in inflection.skipped_findings
        if str(finding.source) == "rule:languagetool.contextual_inflection"
    )
    assert inflection_finding.suggestion == "Nowakiem"
    assert inflection.apply_suggestions((inflection_finding.id,)) == (
        "Rozmawiałem z Janem Nowakiem po przerwie."
    )


class CallerOwnedSharedTransport(FakeHttpTransport):
    closed = False

    def synthesize_context(
        self,
        text: str,
        *,
        spans: tuple[tuple[int, int], ...],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        return {"operation": "synthesize_context", "language": "pl-PL", "results": []}

    def close(self) -> None:
        self.closed = True


def test_analyzer_does_not_close_injected_transports() -> None:
    transport = CallerOwnedSharedTransport(None)
    analyzer = Analyzer(
        AnalyzerConfig(),
        language_tool_transport=transport,
        contextual_inflection_transport=transport,
    )

    analyzer.close()

    assert transport.closed is False


def test_owned_vendored_analyzer_rejects_use_after_close() -> None:
    analyzer = Analyzer(
        AnalyzerConfig(
            vendored_language_tool_stdio_path=str(Path(sys.executable).resolve()),
        )
    )

    analyzer.close()

    with pytest.raises(RuntimeError, match="closed"):
        analyzer.analyze("To jest zdanie.")


def test_unavailable_vendored_process_preserves_builtin_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = LocalLanguageToolStdioSession(
        (sys.executable, "-c", "raise SystemExit(1)"), timeout_seconds=1.0
    )
    _replace_owned_session(monkeypatch, session)

    with Analyzer(
        AnalyzerConfig(
            vendored_language_tool_stdio_path=str(Path(sys.executable).resolve())
        )
    ) as analyzer:
        result = analyzer.analyze("Zeby wrócić.")

    assert any(str(finding.source) == "rule:spelling.zeby" for finding in result.issues)
