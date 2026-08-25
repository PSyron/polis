"""F5.1 regressions for sentence-local templates and document offsets."""

from __future__ import annotations

import re

import pytest

import polis.segmentation as segmentation
from polis import Analyzer, AnalyzerConfig
from polis.core import Finding
from polis.correction.policy import is_automatic_correction_eligible
from polis.rules import InflectionNegatedWidziecRule

_SOURCES = (
    "rule:inflection.negated_miec_czas",
    "rule:inflection.negated_widziec",
    "rule:inflection.numeral_five_genitive_plural",
    "rule:syntax.comma_before_ze_reporting",
    "rule:syntax.comma_before_zeby_purpose",
    "rule:syntax.comma_before_bo",
)


def test_sentence_match_helpers_skip_segmentation_when_pattern_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_segmented(text: str) -> tuple[object, ...]:
        raise AssertionError(f"unexpected segmentation for {text!r}")

    monkeypatch.setattr(segmentation, "_sentence_segments_cached", fail_if_segmented)
    pattern = re.compile("Nie mam czas")

    assert tuple(segmentation._iter_sentence_matches("Poprawny tekst.", pattern)) == ()
    assert (
        tuple(segmentation._iter_sentence_template_matches("Poprawny tekst.", pattern))
        == ()
    )


def test_sentence_match_helpers_reject_zero_width_patterns() -> None:
    with pytest.raises(ValueError, match="must consume text"):
        tuple(segmentation._iter_sentence_matches("a", re.compile(r"(?=a)")))


def _findings(text: str, source: str) -> tuple[Finding, ...]:
    return tuple(
        finding
        for finding in Analyzer(AnalyzerConfig()).analyze(text).issues
        if str(finding.source) == source
    )


@pytest.mark.parametrize(
    ("source", "text", "original", "suggestion"),
    (
        (
            "rule:inflection.negated_miec_czas",
            "Żółć: Nie mam czas.",
            "czas",
            "czasu",
        ),
        (
            "rule:inflection.negated_widziec",
            "Żółć: Nie widzę samochód.",
            "samochód",
            "samochodu",
        ),
        (
            "rule:inflection.numeral_five_genitive_plural",
            "Żółć: Pięć książki leży.",
            "książki",
            "książek",
        ),
        (
            "rule:syntax.comma_before_ze_reporting",
            "Żółć: Wiem że Ania wróciła.",
            "",
            ",",
        ),
        (
            "rule:syntax.comma_before_zeby_purpose",
            "Żółć: Chcę żebyś wrócił.",
            "",
            ",",
        ),
        (
            "rule:syntax.comma_before_bo",
            "Żółć: Nie idę bo pada.",
            "",
            ",",
        ),
    ),
)
def test_unicode_prefix_offsets_are_document_relative(
    source: str, text: str, original: str, suggestion: str
) -> None:
    findings = _findings(text, source)

    assert len(findings) == 1
    finding = findings[0]
    assert (finding.original, finding.suggestion) == (original, suggestion)
    assert text[finding.start : finding.end] == original
    assert finding.start >= len("Żółć: ")


@pytest.mark.parametrize(
    ("source", "text"),
    (
        ("rule:inflection.negated_miec_czas", "Nie mam czas. Potem wrócę."),
        ("rule:inflection.negated_widziec", "Nie widzę samochód. Potem wrócę."),
        (
            "rule:inflection.numeral_five_genitive_plural",
            "Pięć książki leży na stole. Potem wrócę.",
        ),
        (
            "rule:syntax.comma_before_ze_reporting",
            "Wiem że Ania wróciła. Potem dzwonię.",
        ),
        (
            "rule:syntax.comma_before_zeby_purpose",
            "Chcę żebyś wrócił. Potem porozmawiamy.",
        ),
        ("rule:syntax.comma_before_bo", "Nie idę bo pada. Potem wracam."),
    ),
)
def test_appended_sentence_keeps_the_template_match(source: str, text: str) -> None:
    findings = _findings(text, source)

    assert len(findings) == 1
    assert text[findings[0].start : findings[0].end] == findings[0].original


@pytest.mark.parametrize(
    ("source", "text", "expected_offsets"),
    (
        (
            "rule:inflection.negated_miec_czas",
            "Nie mam czas i znów nie mam czas.",
            ((8, 12), (28, 32)),
        ),
        (
            "rule:inflection.negated_widziec",
            "Nie widzę samochód i znów nie widzę samochód.",
            ((10, 18), (36, 44)),
        ),
        (
            "rule:inflection.numeral_five_genitive_plural",
            "Pięć książki leży i pięć książki czeka.",
            ((5, 12), (25, 32)),
        ),
        (
            "rule:syntax.comma_before_ze_reporting",
            "Wiem że Ania wróciła i wiem że Ola wróciła.",
            ((4, 4), (27, 27)),
        ),
        (
            "rule:syntax.comma_before_zeby_purpose",
            "Chcę żebyś wrócił i chcę żebyś usiadł.",
            ((4, 4), (24, 24)),
        ),
        (
            "rule:syntax.comma_before_bo",
            "Nie idę bo pada i nie wracam bo pada.",
            ((7, 7), (28, 28)),
        ),
    ),
)
def test_repeated_templates_keep_order_and_original_slices(
    source: str, text: str, expected_offsets: tuple[tuple[int, int], ...]
) -> None:
    findings = _findings(text, source)

    assert tuple((finding.start, finding.end) for finding in findings) == (
        expected_offsets
    )
    assert all(
        text[finding.start : finding.end] == finding.original for finding in findings
    )


@pytest.mark.parametrize(
    ("source", "text"),
    (
        (
            "rule:inflection.negated_miec_czas",
            "Nie mam czas i znów nie mam czas bez kropki",
        ),
        (
            "rule:inflection.negated_widziec",
            "Nie widzę samochód i znów nie widzę samochód bez kropki",
        ),
        (
            "rule:inflection.negated_miec_czas",
            "Nie mam czas; dygresja i nie mam czas.",
        ),
        (
            "rule:inflection.negated_widziec",
            "Nie widzę samochód; dygresja i nie widzę samochód.",
        ),
    ),
)
def test_negated_template_sequences_abstain_when_not_closed(
    source: str, text: str
) -> None:
    assert _findings(text, source) == ()


@pytest.mark.parametrize(
    ("source", "text", "expected"),
    (
        (
            "rule:agreement.copula_ja",
            "Ja jest gotowy.",
            ((3, 7, "jest", "jestem"),),
        ),
        (
            "rule:inflection.government_sluchac_radio",
            "Słucham radio.",
            ((8, 13, "radio", "radia"),),
        ),
        (
            "rule:inflection.negated_lubic_kawe",
            "Nie lubię kawę.",
            ((10, 14, "kawę", "kawy"),),
        ),
        (
            "rule:agreement.te_zdanie",
            "Te zdanie jest poprawne.",
            ((0, 9, "Te zdanie", "To zdanie"),),
        ),
    ),
)
def test_already_clean_sources_keep_existing_payloads(
    source: str, text: str, expected: tuple[tuple[int, int, str, str], ...]
) -> None:
    observed = tuple(
        (finding.start, finding.end, finding.original, finding.suggestion)
        for finding in Analyzer(AnalyzerConfig()).analyze(text).issues
        if str(finding.source) == source
    )

    assert observed == expected


def test_negated_widziec_behavior_version_bump_remains_review_only() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    rule = InflectionNegatedWidziecRule()
    finding = _findings("Nie widzę samochód. Potem wrócę.", str(rule.source))[0]
    behavior = analyzer._registry.source_behavior(finding.source)

    assert rule.behavior_version == "inflection-negated-widziec/3.0"
    assert behavior is not None
    assert behavior.behavior_version == rule.behavior_version
    assert not is_automatic_correction_eligible(finding, behavior)
    assert analyzer.correct("Nie widzę samochód. Potem wrócę.").applied_findings == ()


@pytest.mark.parametrize("source", _SOURCES)
def test_existing_abstentions_are_preserved(source: str) -> None:
    text_by_source = {
        "rule:inflection.negated_miec_czas": "Nie mam czasu. Potem wrócę.",
        "rule:inflection.negated_widziec": "Nie widzę samochodu. Potem wrócę.",
        "rule:inflection.numeral_five_genitive_plural": "Pięć książek leży.",
        "rule:syntax.comma_before_ze_reporting": (
            "Wiem, że Ania wróciła. Potem dzwonię."
        ),
        "rule:syntax.comma_before_zeby_purpose": "Chcę, żebyś wrócił. Potem wrócę.",
        "rule:syntax.comma_before_bo": "Nie idę, bo pada. Potem wracam.",
    }

    assert _findings(text_by_source[source], source) == ()
