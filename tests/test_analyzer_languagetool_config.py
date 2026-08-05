from __future__ import annotations

from pathlib import Path

import pytest

from polis import Analyzer, AnalyzerConfig, ConfigurationError


def _config_file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "polis.toml"
    path.write_text(body, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("section", "contents"),
    (
        ("backend", ""),
        ("language_tool", "legacy_option = true\n"),
        ("contextual_inflection", ""),
        ("vendored_language_tool", "legacy_option = true\n"),
    ),
)
def test_legacy_toml_section_is_rejected_by_the_v1_contract(
    tmp_path: Path,
    section: str,
    contents: str,
) -> None:
    path = _config_file(tmp_path, f"[{section}]\n{contents}")

    with pytest.raises(ConfigurationError) as raised:
        AnalyzerConfig.from_toml(path)

    error = raised.value
    assert error.code == "configuration.unsupported_section"
    assert error.retryable is False
    assert section in str(error)
    assert "is not supported in Polis v1" in str(error)
    assert error.context["path"] == str(path)
    assert error.context["section"] == section
    assert error.context["operation"]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("use_local_heuristic_backend", True),
        ("language_tool_url", "http://127.0.0.1:8081"),
        ("language_tool_timeout_seconds", 0.5),
        ("contextual_inflection_stdio_path", "/bin/false"),
        ("contextual_inflection_timeout_seconds", 0.5),
        ("vendored_language_tool_stdio_path", "/bin/false"),
        ("vendored_language_tool_timeout_seconds", 0.5),
    ),
)
def test_removed_analyzer_config_field_is_not_accepted(
    field: str,
    value: object,
) -> None:
    with pytest.raises(TypeError):
        AnalyzerConfig(**{field: value})


@pytest.mark.parametrize(
    "argument",
    (
        "specialist_engine",
        "language_tool_transport",
        "contextual_inflection_transport",
    ),
)
def test_analyzer_no_longer_accepts_injected_optional_routes(argument: str) -> None:
    with pytest.raises(TypeError):
        Analyzer(AnalyzerConfig(), **{argument: object()})


def test_default_analyzer_owns_no_process_and_lifecycle_is_a_no_op() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    assert analyzer.language_tool_process_start_count == 0
    analyzer.close()
    analyzer.close()

    assert analyzer.analyze("To jest test.").issues == ()
    with analyzer as entered:
        assert entered is analyzer

    assert analyzer.analyze("To jest test.").issues == ()
