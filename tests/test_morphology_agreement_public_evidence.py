from __future__ import annotations

from polis import Analyzer, AnalyzerConfig

_SOURCE = "rule:agreement.nominal_group_ta_nowy_ksiazka"

_POSITIVES = (
    ("Ta czerwony książka.", ("czerwony", "czerwona", 3, 11)),
    ("Ta stary książka.", ("stary", "stara", 3, 8)),
    ("Czerwony książka.", ("Czerwony", "Czerwona", 0, 8)),
    ("Ta czerwonego książka.", ("czerwonego", "czerwona", 3, 13)),
    ("Ta mały książka.", ("mały", "mała", 3, 7)),
    ("Ta duży książka.", ("duży", "duża", 3, 7)),
    ("Ta wysoki książka.", ("wysoki", "wysoka", 3, 9)),
    ("Stary książka.", ("Stary", "Stara", 0, 5)),
)

_HARD_NEGATIVES = (
    "Ta czerwona książka.",
    "Ta stara książka.",
    "Czerwona książka.",
    "Duże okno.",
    "Nowy samochód.",
    "Czerwony samochód.",
    "Ta czerwony Warszawa.",
    "Ta czerwony Kraków.",
    "Napisano „Ta czerwony książka”.",
    "Stała `Ta czerwony książka`.",
    "Ta czerwony książka,",
    "Ta czerwony książka i Ten nowy samochód.",
    "Ta czerwony i książka.",
    "Ta czerwony książki.",
    "To duży okno.",
    "Ten nowa samochód.",
)


def test_public_agreement_evidence_has_exact_positive_delta() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    observed: list[tuple[str, str, str, int, int]] = []
    for text, expected in _POSITIVES:
        findings = tuple(
            finding
            for finding in analyzer.analyze(text).issues
            if str(finding.source) == _SOURCE
        )
        assert len(findings) == 1
        finding = findings[0]
        assert text[finding.start : finding.end] == finding.original
        assert (
            finding.original,
            finding.suggestion,
            finding.original,
            finding.start,
            finding.end,
        ) == (
            expected[0],
            expected[1],
            text[finding.start : finding.end],
            expected[2],
            expected[3],
        )
        observed.append(
            (
                text,
                finding.original,
                finding.suggestion,
                finding.start,
                finding.end,
            )
        )

    assert len(observed) == 8


def test_public_agreement_evidence_has_zero_hard_negative_false_alarms() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    false_alarms = {
        text: tuple(
            finding
            for finding in analyzer.analyze(text).issues
            if str(finding.source) == _SOURCE
        )
        for text in _HARD_NEGATIVES
    }

    assert len(_HARD_NEGATIVES) == 16
    assert all(not findings for findings in false_alarms.values())
