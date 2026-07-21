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
QUALITY_GATES = ROOT / "docs" / "llm-quality-gates.md"


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


def test_corpus_declares_current_and_planned_verification_modes() -> None:
    cases = _load_json_cases().values()

    assert {case.verification for case in cases} == {
        "rules",
        "llm_planned",
        "negative",
    }
    assert all(
        case.tracking_issue in {42, 43, 49}
        for case in cases
        if case.verification == "llm_planned"
    )


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
    analyzer = Analyzer(AnalyzerConfig(use_local_heuristic_backend=False))

    result = analyzer.analyze(case.source)
    corrected = result.apply(tuple(item.id for item in result.issues))

    assert corrected == case.expected


@pytest.mark.parametrize("fixture", [_load_json_cases(), _load_xml_cases()])
def test_negative_cases_produce_no_findings(fixture: dict[str, E2ECase]) -> None:
    analyzer = Analyzer(AnalyzerConfig(use_local_heuristic_backend=False))

    for case in fixture.values():
        if case.verification == "negative":
            assert case.source == case.expected
            assert analyzer.analyze(case.source).issues == ()


def test_planned_llm_cases_have_gold_output_category_and_tracking() -> None:
    planned_cases = [
        case
        for case in _load_json_cases().values()
        if case.verification == "llm_planned"
    ]

    assert planned_cases
    assert all(case.source != case.expected for case in planned_cases)
    assert all(case.tracking_issue in {42, 43, 49} for case in planned_cases)
    assert {"inflection", "syntax", "punctuation", "word_order"} <= {
        tag for case in planned_cases for tag in case.tags
    }


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


def test_llm_quality_corpus_has_category_coverage_and_hard_negatives() -> None:
    cases = _load_json_cases().values()
    planned_cases = [case for case in cases if case.verification == "llm_planned"]
    negative_cases = [case for case in cases if case.verification == "negative"]

    for category in ("inflection", "syntax", "punctuation"):
        assert sum(category in case.tags for case in planned_cases) >= 10

    assert len(negative_cases) >= 10
    assert sum("name" in case.tags for case in negative_cases) >= 5
    assert sum("word_order" in case.tags for case in negative_cases) >= 3


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


def test_llm_quality_gate_documentation_requires_all_safety_and_quality_gates() -> None:
    documentation = QUALITY_GATES.read_text(encoding="utf-8")

    for requirement in (
        "100%",
        "0",
        "precision",
        "recall",
        "F1",
        "0.90",
        "inflection",
        "syntax",
        "punctuation",
    ):
        assert requirement in documentation
