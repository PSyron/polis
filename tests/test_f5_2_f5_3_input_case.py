from __future__ import annotations

import pytest

from polis import Analyzer, AnalyzerConfig


@pytest.mark.parametrize(
    ("source", "text", "expected"),
    (
        (
            "rule:agreement.te_neuter_noun",
            "ŻÓŁĆ: TE DZIECKO PRZYSZŁO.",
            (6, 8, "TE", "TO"),
        ),
        (
            "rule:inflection.government_do_sklep",
            "ŻÓŁĆ: IDĘ DO SKLEP.",
            (13, 18, "SKLEP", "SKLEPU"),
        ),
        (
            "rule:syntax.comma_before_bo",
            "ŻÓŁĆ: NIE IDĘ BO PADA.",
            (13, 13, "", ","),
        ),
    ),
)
def test_all_uppercase_templates_emit_exact_document_offsets(
    source: str, text: str, expected: tuple[int, int, str, str]
) -> None:
    # Given: one qualified all-uppercase closed template under a Unicode prefix.
    analyzer = Analyzer(AnalyzerConfig())

    # When: the public Analyzer evaluates the original document.
    findings = tuple(
        finding
        for finding in analyzer.analyze(text).issues
        if str(finding.source) == source
    )

    # Then: the one review finding uses the exact original-document span.
    assert len(findings) == 1
    finding = findings[0]
    assert (
        finding.start,
        finding.end,
        finding.original,
        finding.suggestion,
    ) == expected
    assert text[finding.start : finding.end] == finding.original


@pytest.mark.parametrize(
    ("source", "text"),
    (
        ("rule:agreement.te_neuter_noun", "Te DZIECKO PRZYSZŁO."),
        ("rule:agreement.te_neuter_noun", "TE MIASTO JEST DUŻE."),
        ("rule:inflection.government_do_sklep", "Idę DO SKLEP."),
        ("rule:inflection.government_do_sklep", "IDĘ DO MAGAZYN."),
        ("rule:syntax.comma_before_bo", "Nie idę BO PADA."),
        ("rule:syntax.comma_before_bo", "NIE IDĘ bo PADA."),
        ("rule:syntax.comma_before_bo", "NIE IDĘ ALE PADA."),
    ),
)
def test_uppercase_branches_preserve_closed_template_abstentions(
    source: str, text: str
) -> None:
    # Given: mixed casing or a lexeme outside the closed template.
    analyzer = Analyzer(AnalyzerConfig())

    # When: the public Analyzer evaluates the text.
    findings = tuple(
        finding
        for finding in analyzer.analyze(text).issues
        if str(finding.source) == source
    )

    # Then: the source remains fail-closed.
    assert findings == ()
