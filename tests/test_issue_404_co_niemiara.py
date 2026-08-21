from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from polis import Analyzer, AnalyzerConfig, Severity

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "tests/fixtures/v1/provider_independent_spelling_qualification.json"
SOURCE = "rule:spelling.co_niemiara"
BEHAVIOR_VERSION = "spelling-co-niemiara/1.0"
OPERATION = "replace.closed_literal_spacing"


def _pi01_cases() -> tuple[dict[str, Any], ...]:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    candidate = next(
        item for item in evidence["candidates"] if item["id"] == "PI-TYPO-01"
    )
    return tuple((*candidate["positive_cases"], *candidate["hard_negative_cases"]))


def _source_findings(text: str) -> tuple[Any, ...]:
    return tuple(
        finding
        for finding in Analyzer(AnalyzerConfig()).analyze(text).issues
        if str(finding.source) == SOURCE
    )


@pytest.mark.parametrize("case", _pi01_cases(), ids=lambda case: case["id"])
def test_pi01_matches_the_approved_evidence_contract(case: dict[str, Any]) -> None:
    findings = _source_findings(case["text"])
    expected = tuple(
        (
            item["category"],
            item["original"],
            item["suggestion"],
            item["start"],
            item["end"],
        )
        for finding in case["expected_findings"]
        for item in (finding,)
    )

    assert (
        tuple(
            (
                finding.category.value,
                finding.original,
                finding.suggestion,
                finding.start,
                finding.end,
            )
            for finding in findings
        )
        == expected
    )


def test_pi01_binds_review_only_behavior_and_explicit_apply() -> None:
    text = "Mamy problemów coniemiara."
    analyzer = Analyzer(AnalyzerConfig())
    result = analyzer.analyze(text)
    findings = _source_findings(text)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.category.value == "spelling"
    assert finding.severity is Severity.SUGGESTION
    assert text[finding.start : finding.end] == finding.original

    behavior = analyzer._registry.source_behavior(finding.source)
    assert behavior is not None
    assert behavior.operation == OPERATION
    assert behavior.behavior_version == BEHAVIOR_VERSION

    assert analyzer.correct(text).corrected_text == text
    assert analyzer.correct(text).skipped_findings == findings
    assert result.apply((finding.id,)) == "Mamy problemów co niemiara."


@pytest.mark.parametrize("text", ("CoNiemiara", "coNiemiara", "CONiemiara"))
def test_pi01_abstains_on_incoherent_casing(text: str) -> None:
    assert _source_findings(f"To jest {text}.") == ()


@pytest.mark.parametrize(
    "text",
    (
        "Coniemiara problemów przybyło.",
        "Zdanie. Coniemiara problemów przybyło.",
    ),
)
def test_pi01_preserves_sentence_initial_title_case(text: str) -> None:
    findings = _source_findings(text)
    assert len(findings) == 1
    finding = findings[0]
    assert text[finding.start : finding.end] == finding.original
    assert finding.suggestion == "Co niemiara"


def test_pi01_preserves_sentence_initial_title_case_after_crlf() -> None:
    text = "Pierwsze zdanie.\r\nConiemiara problemów przybyło."
    findings = _source_findings(text)
    assert len(findings) == 1
    finding = findings[0]
    assert (finding.start, finding.end) == (18, 28)
    assert finding.suggestion == "Co niemiara"


@pytest.mark.parametrize(
    "text",
    (
        "Napis 'coniemiara' jest omawianym przykładem.",
        "Napis ‘coniemiara’ jest omawianym przykładem.",
        "Napis ‹coniemiara› jest omawianym przykładem.",
        "Napis <coniemiara> jest omawianym przykładem.",
        "Napis „coniemiara.” jest omawianym przykładem.",
        "Napis „coniemiara,” jest omawianym przykładem.",
        "Napis: „coniemiara jest błędne”.",
        "W zdaniu napisano: „coniemiara jest błędne”.",
        "Napis — „coniemiara jest błędne”.",
        'Napis, "Mamy coniemiara problemów."',
        'Napis - "Mamy coniemiara problemów."',
        'Napisy: "Mamy coniemiara problemów."',
        "Forma, „Mamy coniemiara problemów.”",
        'Powiedział: „Napis "coniemiara".”',
        "Napis: „tekst “cytat” coniemiara”.",
        "Napis: „tekst «cytat” coniemiara”.",
    ),
)
def test_pi01_abstains_on_wrapped_metalinguistic_mentions(text: str) -> None:
    assert _source_findings(text) == ()


@pytest.mark.parametrize(
    "text",
    (
        'Powiedział: "Coniemiara".',
        "Powiedział: „Coniemiara.”",
        "Powiedziała: ‘Coniemiara!’",
        "Powiedział: «Coniemiara?»",
        "Powiedział do Jana: „Mamy problemów coniemiara”.",
    ),
)
def test_pi01_analyzes_one_word_dialogue(text: str) -> None:
    findings = _source_findings(text)
    assert len(findings) == 1
    assert text[findings[0].start : findings[0].end] == findings[0].original


@pytest.mark.parametrize(
    "text",
    (
        "Powiedział: „Mamy problemów coniemiara.",
        'Powiedział: "Mamy problemów coniemiara.',
        'Powiedział: „Mamy problemów coniemiara".',
        'Napis: „ Powiedział: "coniemiara"”.',
        'Kod: " Powiedział: „coniemiara”"',
        'Powiedział: "On powiedział "coniemiara"."',
        "Kod coniemiara|foo pozostaje kodem.",
        "Kod coniemiara^foo pozostaje kodem.",
        "Kod: coniemiara → x.",
        "Kod: x & coniemiara.",
        "Kod: x ? coniemiara : y.",
        "Kod: x ~ coniemiara.",
        "x = coniemiara",
        "Marka Coniemiara pozostaje nazwą produktu.",
        "Marka CONIEMIARA pozostaje nazwą produktu.",
        "Marka coniemiara pozostaje nazwą produktu.",
        "Napis coniemiara pozostaje przykładem.",
        "coniemiara™ pozostaje nazwą produktu.",
        "coniemiara☃ pozostaje symbolem.",
        'Powiedział: „Mamy problemów coniemiara”".',
    ),
)
def test_pi01_abstains_on_malformed_or_nested_non_prose_context(text: str) -> None:
    assert _source_findings(text) == ()


def test_pi01_preserves_existing_literal_wrapper_behavior() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    quoted_zeby = analyzer.analyze("Zeby 'zeby' było widoczne.").issues
    assert any(str(finding.source) == "rule:spelling.zeby" for finding in quoted_zeby)

    quoted_napewno = analyzer.analyze("‹napewno› pozostaje przykładem.").issues
    assert any(
        str(finding.source) == "rule:spelling.napewno" for finding in quoted_napewno
    )


@pytest.mark.parametrize(
    "suffix",
    ("\u0000", "\ud800", "\ufffe", "\u0301", "\u200d", "\ufe0f", "\u203f", "\u00b7"),
)
def test_pi01_abstains_on_unicode_token_extensions(suffix: str) -> None:
    assert _source_findings(f"Mamy problemów coniemiara{suffix}.") == ()


@pytest.mark.parametrize(
    "text",
    (
        r"Path docs\coniemiara\index.",
        r"Path \\server\share\coniemiara.",
        "Shell ${coniemiara}.",
        "Code coniemiara().",
        "Code obj[coniemiara].",
        "Token foo.coniemiara pozostaje identyfikatorem.",
        "Kod: `coniemiara + x`.",
        'Kod "prefix coniemiara suffix".',
        "Marka „Coniemiara produktowa”.",
    ),
)
def test_pi01_abstains_on_code_and_path_hosts(text: str) -> None:
    assert _source_findings(text) == ()
