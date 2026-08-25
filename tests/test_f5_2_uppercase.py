"""F5.2 regressions for the three closed uppercase branches."""

from __future__ import annotations

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import Finding
from polis.correction.policy import is_automatic_correction_eligible

_CASES = (
    (
        "rule:agreement.te_neuter_noun",
        "ŻÓŁĆ: TE DZIECKO PRZYSZŁO.",
        "TE",
        "TO",
        6,
        8,
        "agreement-te-neuter-noun/2.0",
        "replace.pronoun_gender",
    ),
    (
        "rule:inflection.government_do_sklep",
        "ŻÓŁĆ: IDĘ DO SKLEP.",
        "SKLEP",
        "SKLEPU",
        13,
        18,
        "inflection-government-do-sklep/4.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
        "replace.governed_form",
    ),
    (
        "rule:syntax.comma_before_bo",
        "ŻÓŁĆ: NIE IDĘ BO PADA.",
        "",
        ",",
        13,
        13,
        "syntax-comma-before-bo/3.0",
        "insert.causal_clause_comma",
    ),
)


def _source_findings(text: str, source: str) -> tuple[Finding, ...]:
    return tuple(
        finding
        for finding in Analyzer(AnalyzerConfig()).analyze(text).issues
        if str(finding.source) == source
    )


@pytest.mark.parametrize(
    "source,text,original,suggestion,start,end,behavior_version,operation", _CASES
)
def test_f52_uppercase_canonical_branches_preserve_exact_contract(
    source: str,
    text: str,
    original: str,
    suggestion: str,
    start: int,
    end: int,
    behavior_version: str,
    operation: str,
) -> None:
    findings = _source_findings(text, source)

    assert len(findings) == 1
    finding = findings[0]
    assert (finding.original, finding.suggestion) == (original, suggestion)
    assert (finding.start, finding.end) == (start, end)
    assert text[finding.start : finding.end] == original

    analyzer = Analyzer(AnalyzerConfig())
    behavior = analyzer._registry.source_behavior(finding.source)
    assert behavior is not None
    assert behavior.operation == operation
    assert behavior.behavior_version == behavior_version
    assert not is_automatic_correction_eligible(finding, behavior)
    correction = analyzer.correct(text)
    assert correction.corrected_text == text
    assert correction.applied_findings == ()
    assert correction.skipped_findings == findings
    assert analyzer.analyze(text).apply((finding.id,)) != text


@pytest.mark.parametrize(
    ("source", "text", "expected"),
    (
        (
            "rule:agreement.te_neuter_noun",
            "Te dziecko przyszło.",
            ((0, 2, "Te", "To"),),
        ),
        (
            "rule:agreement.te_neuter_noun",
            "te dziecko przyszło.",
            ((0, 2, "te", "to"),),
        ),
        (
            "rule:agreement.te_neuter_noun",
            "TE dziecko przyszło.",
            ((0, 2, "TE", "TO"),),
        ),
        (
            "rule:inflection.government_do_sklep",
            "Idę do sklep.",
            ((7, 12, "sklep", "sklepu"),),
        ),
        (
            "rule:inflection.government_do_sklep",
            "idę do sklep.",
            ((7, 12, "sklep", "sklepu"),),
        ),
        (
            "rule:inflection.government_do_sklep",
            "IDĘ do SKLEP.",
            ((7, 12, "SKLEP", "SKLEPU"),),
        ),
        (
            "rule:inflection.government_do_sklep",
            "Idę do Sklep.",
            (),
        ),
        (
            "rule:syntax.comma_before_bo",
            "Nie idę bo pada.",
            ((7, 7, "", ","),),
        ),
        (
            "rule:syntax.comma_before_bo",
            "nie idę bo pada.",
            ((7, 7, "", ","),),
        ),
        (
            "rule:syntax.comma_before_bo",
            "NIE IDĘ bo pada.",
            ((7, 7, "", ","),),
        ),
    ),
)
def test_f52_preserves_lowercase_and_existing_mixed_outputs(
    source: str, text: str, expected: tuple[tuple[int, int, str, str], ...]
) -> None:
    observed = tuple(
        (finding.start, finding.end, finding.original, finding.suggestion)
        for finding in _source_findings(text, source)
    )
    assert observed == expected


@pytest.mark.parametrize(
    ("source", "text"),
    (
        # F5.2's legacy mixed-case and boundary abstentions remain closed.
        ("rule:agreement.te_neuter_noun", "Te DZIECKO przyszło."),
        ("rule:agreement.te_neuter_noun", "TE Dziecko przyszło."),
        ("rule:agreement.te_neuter_noun", "TE ZDANIE przyszło."),
        ("rule:agreement.te_neuter_noun", "TE DOM przyszło."),
        ("rule:agreement.te_neuter_noun", "TE DZIECKO, CHODŹ TU."),
        ("rule:inflection.government_do_sklep", "Idę DO SKLEP."),
        ("rule:inflection.government_do_sklep", "IDĘ Do SKLEP."),
        ("rule:inflection.government_do_sklep", "IDĘ DO sklep."),
        ("rule:inflection.government_do_sklep", "IDĘ DO SKLEPU."),
        ("rule:inflection.government_do_sklep", "IDĘ DO MARKET."),
        ("rule:inflection.government_do_sklep", "IDĘ DO SKLEP, TERAZ."),
        ("rule:syntax.comma_before_bo", "NIE IDĘ bo PADA."),
        ("rule:syntax.comma_before_bo", "NIE IDĘ BO pada."),
        ("rule:syntax.comma_before_bo", "NIE IDĘ BO PADA"),
        ("rule:syntax.comma_before_bo", "NIE IDĘ BO PADA!"),
    ),
)
def test_f52_hard_negatives_remain_abstentions(source: str, text: str) -> None:
    assert _source_findings(text, source) == ()


def test_f52_canonical_sources_remain_review_only_without_policy_entries() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for source, text, *_rest in _CASES:
        finding = _source_findings(text, source)[0]
        behavior = analyzer._registry.source_behavior(finding.source)
        assert behavior is not None
        assert not is_automatic_correction_eligible(finding, behavior)
        assert analyzer.correct(text).applied_findings == ()
