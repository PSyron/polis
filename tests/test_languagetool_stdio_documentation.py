from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "experiments" / "languagetool_stdio_session" / "report.json"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_vendored_stdio_public_documentation_covers_operation_and_removal() -> None:
    documentation = "\n".join(
        _read(path)
        for path in (
            "README.md",
            "examples/polis.toml",
            "docs/customization.md",
            "docs/offline-operation.md",
            "docs/public-api.md",
            "docs/privacy.md",
            "docs/limitations.md",
        )
    )

    for required_text in (
        "[vendored_language_tool]",
        "stdio_path",
        "Analyzer.close()",
        "sentence-only",
        "source-policy `1.1`",
        "jeden trwały proces",
        "nie pobiera ani nie aktualizuje artefaktów Java",
        "Usunięcie `[vendored_language_tool]` wyłącza współdzielony proces",
    ):
        assert required_text in documentation


def test_polish_offline_document_names_uv_lock_files_precisely() -> None:
    offline_documentation = _read("docs/offline-operation.md")

    assert "plików lock `uv`" in offline_documentation


def test_polish_offline_document_has_no_english_sentence_only_gloss() -> None:
    offline_documentation = _read("docs/offline-operation.md")

    assert "działającą wyłącznie dla zdań" in offline_documentation
    assert "(sentence-only)" not in offline_documentation


def test_runtime_guides_preserve_formal_source_policy_contract_name() -> None:
    for relative_path in ("docs/public-api.md", "docs/rules.md"):
        guide = _read(relative_path)

        assert "source-policy `1.1`" in guide
        assert "source-policy `1.2`" in guide


def test_vendored_stdio_performance_documentation_matches_measured_report() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    summary = report["summary"]
    performance = _read("docs/performance-baseline.md")

    assert f"{summary['cold_first_request_ms']:.2f} ms" in performance
    assert f"{summary['warm_p95_ms']:.2f} ms" in performance
    assert f"{summary['combined_rss_bytes']:,} bytes" in performance
    assert f"{summary['cases_per_second']:.2f}" in performance
    assert "69" in performance
    assert "zero network sockets" in performance


def test_vendored_stdio_roadmap_and_changelog_record_issue_77_boundary() -> None:
    roadmap = _read("docs/project/ROADMAP.md")
    changelog = _read("CHANGELOG.md")

    assert "#77" in roadmap
    assert "#76" in roadmap
    assert "#77" in changelog
    assert "sentence-only" in changelog
