from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pytest

from polis import Analyzer, AnalyzerConfig

ROOT = Path(__file__).resolve().parents[1]
JSON_FIXTURE = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.json"
XML_FIXTURE = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.xml"


@dataclass(frozen=True, slots=True)
class E2EExpectedFinding:
    category: str
    start: int
    end: int
    original: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class E2ECase:
    case_id: str
    source: str
    expected: str
    tags: tuple[str, ...]
    verification: str
    tracking_issue: int | None
    expected_findings: tuple[E2EExpectedFinding, ...]


FindingProjection = tuple[str, int, int, str, str]


def _assert_exact_findings(
    case_id: str,
    actual_findings: tuple[FindingProjection, ...],
    expected_findings: tuple[FindingProjection, ...],
) -> None:
    assert len(actual_findings) == len(expected_findings), f"{case_id}.count"
    for index, (actual, expected) in enumerate(
        zip(actual_findings, expected_findings, strict=True)
    ):
        assert actual[0] == expected[0], f"{case_id}[{index}].category"
        assert actual[1] == expected[1], f"{case_id}[{index}].start"
        assert actual[2] == expected[2], f"{case_id}[{index}].end"
        assert actual[3] == expected[3], f"{case_id}[{index}].original"
        assert actual[4] == expected[4], f"{case_id}[{index}].suggestion"


def _mutate_actual_findings(
    actual_findings: tuple[FindingProjection, ...], mutation: str
) -> tuple[FindingProjection, ...]:
    assert actual_findings
    first = actual_findings[0]
    if mutation == "category":
        mutated_first: FindingProjection = (
            "mutated-category",
            first[1],
            first[2],
            first[3],
            first[4],
        )
        return (mutated_first, *actual_findings[1:])
    if mutation == "start":
        mutated_first = (first[0], first[1] + 1, first[2], first[3], first[4])
        return (mutated_first, *actual_findings[1:])
    if mutation == "end":
        mutated_first = (first[0], first[1], first[2] + 1, first[3], first[4])
        return (mutated_first, *actual_findings[1:])
    if mutation == "original":
        mutated_first = (first[0], first[1], first[2], first[3] + "!", first[4])
        return (mutated_first, *actual_findings[1:])
    if mutation == "suggestion":
        mutated_first = (first[0], first[1], first[2], first[3], first[4] + "!")
        return (mutated_first, *actual_findings[1:])
    if mutation == "drop":
        return actual_findings[:-1]
    if mutation == "duplicate":
        return (*actual_findings, actual_findings[-1])
    if mutation == "reorder":
        assert len(actual_findings) >= 2
        return (actual_findings[1], actual_findings[0], *actual_findings[2:])
    raise AssertionError(f"unknown finding mutation: {mutation}")


def _load_json_cases() -> dict[str, E2ECase]:
    raw = json.loads(JSON_FIXTURE.read_text(encoding="utf-8"))
    return {
        item["id"]: E2ECase(
            case_id=item["id"],
            source=item["input"],
            expected=item["expected_output"],
            tags=tuple(tag.strip() for tag in item["tags"]),
            verification=item["verification"],
            tracking_issue=item.get("tracking_issue"),
            expected_findings=tuple(
                E2EExpectedFinding(
                    finding["category"],
                    finding["start"],
                    finding["end"],
                    finding["original"],
                    finding["suggestion"],
                )
                for finding in item["expected_findings"]
            ),
        )
        for item in raw["cases"]
    }


def _load_xml_cases() -> dict[str, E2ECase]:
    root = ET.parse(XML_FIXTURE).getroot()
    cases = {}
    for case in root.findall("case"):
        case_id = case.get("id", "")
        source = (case.findtext("input") or "").strip()
        expected = (case.findtext("expected_output") or "").strip()
        tags_text = case.get("tags", "")
        tags = tuple(
            tag for tag in (tag.strip() for tag in tags_text.split(",")) if tag
        )
        tracking_issue_text = case.get("tracking_issue")
        expected_findings = case.find("expected_findings")
        assert expected_findings is not None
        cases[case_id] = E2ECase(
            case_id=case_id,
            source=source,
            expected=expected,
            tags=tags,
            verification=case.get("verification", ""),
            tracking_issue=(
                int(tracking_issue_text) if tracking_issue_text is not None else None
            ),
            expected_findings=tuple(
                E2EExpectedFinding(
                    finding.get("category", ""),
                    int(finding.get("start", "-1")),
                    int(finding.get("end", "-1")),
                    finding.get("original", ""),
                    finding.get("suggestion", ""),
                )
                for finding in expected_findings.findall("finding")
            ),
        )
    return cases


def _normalize_result(
    cases: dict[str, E2ECase],
) -> dict[
    str,
    tuple[
        str,
        str,
        tuple[str, ...],
        str,
        int | None,
        tuple[E2EExpectedFinding, ...],
    ],
]:
    return {
        key: (
            case.source,
            case.expected,
            tuple(case.tags),
            case.verification,
            case.tracking_issue,
            case.expected_findings,
        )
        for key, case in cases.items()
    }


def test_json_and_xml_corpora_cover_the_same_cases() -> None:
    json_cases = _load_json_cases()
    xml_cases = _load_xml_cases()

    assert set(json_cases) == set(xml_cases)
    assert _normalize_result(json_cases) == _normalize_result(xml_cases)


RULE_CASE_IDS = tuple(
    case_id
    for case_id, case in _load_json_cases().items()
    if case.verification == "rules"
)


@pytest.mark.parametrize("fixture", [_load_json_cases(), _load_xml_cases()])
@pytest.mark.parametrize("case_id", RULE_CASE_IDS)
def test_end_to_end_polish_correction_corpus_fixtures(
    fixture: dict[str, E2ECase],
    case_id: str,
) -> None:
    case = fixture[case_id]
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.analyze(case.source)
    corrected = result.apply(tuple(item.id for item in result.issues))

    actual_findings = tuple(
        (
            item.category.value,
            item.start,
            item.end,
            item.original,
            item.suggestion,
        )
        for item in result.issues
    )
    expected_findings = tuple(
        (
            finding.category,
            finding.start,
            finding.end,
            finding.original,
            finding.suggestion,
        )
        for finding in case.expected_findings
    )

    _assert_exact_findings(case.case_id, actual_findings, expected_findings)
    assert corrected == case.expected


@pytest.mark.parametrize(
    ("case_id", "mutation", "expected_field"),
    [
        ("spelling_zeby", "category", "category"),
        ("spelling_zeby", "start", "start"),
        ("spelling_zeby", "end", "end"),
        ("spelling_zeby", "original", "original"),
        ("spelling_zeby", "suggestion", "suggestion"),
        ("spelling_repeated_across_sentences", "drop", "count"),
        ("spelling_repeated_across_sentences", "duplicate", "count"),
        ("spelling_repeated_across_sentences", "reorder", "start"),
    ],
)
def test_exact_finding_assertion_rejects_controlled_mutations(
    case_id: str, mutation: str, expected_field: str
) -> None:
    case = _load_json_cases()[case_id]
    result = Analyzer(AnalyzerConfig()).analyze(case.source)
    actual_findings = tuple(
        (
            item.category.value,
            item.start,
            item.end,
            item.original,
            item.suggestion,
        )
        for item in result.issues
    )
    expected_findings = tuple(
        (
            finding.category,
            finding.start,
            finding.end,
            finding.original,
            finding.suggestion,
        )
        for finding in case.expected_findings
    )
    corrected = result.apply(tuple(item.id for item in result.issues))
    mutated_findings = _mutate_actual_findings(actual_findings, mutation)

    with pytest.raises(AssertionError, match=expected_field):
        _assert_exact_findings(case.case_id, mutated_findings, expected_findings)
    assert corrected == case.expected


@pytest.mark.parametrize("fixture", [_load_json_cases(), _load_xml_cases()])
def test_negative_cases_produce_no_findings(fixture: dict[str, E2ECase]) -> None:
    analyzer = Analyzer(AnalyzerConfig())

    for case in fixture.values():
        if case.verification == "negative":
            assert case.source == case.expected
            assert analyzer.analyze(case.source).issues == ()


def test_all_corpus_cases_have_explicit_gold_edits_that_reconstruct_output() -> None:
    raw = json.loads(JSON_FIXTURE.read_text(encoding="utf-8"))

    for case in raw["cases"]:
        assert isinstance(case.get("expected_findings"), list), case["id"]
        corrected = case["input"]
        for finding in sorted(
            case["expected_findings"], key=lambda item: item["start"], reverse=True
        ):
            corrected = (
                corrected[: finding["start"]]
                + finding["suggestion"]
                + corrected[finding["end"] :]
            )
        assert corrected == case["expected_output"], case["id"]


def test_corpus_preserves_name_inflection_and_valid_word_order_negatives() -> None:
    cases = _load_json_cases()
    negative_cases = [
        case for case in cases.values() if case.verification == "negative"
    ]

    assert {case.case_id for case in negative_cases} >= {
        "negative_female_name_instrumental",
        "negative_male_name_dative",
        "negative_marked_word_order",
    }


def test_review_only_finding_requires_explicit_apply() -> None:
    source = "On boi hałasu."
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.analyze(source)

    assert tuple(
        (
            item.category.value,
            item.start,
            item.end,
            item.original,
            item.suggestion,
        )
        for item in result.issues
    ) == (("syntax", 6, 6, "", " się"),)
    assert analyzer.correct(source).corrected_text == source
    assert (
        result.apply(tuple(item.id for item in result.issues)) == "On boi się hałasu."
    )
