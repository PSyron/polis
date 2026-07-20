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
class E2ECase:
    case_id: str
    source: str
    expected: str
    tags: tuple[str, ...]


def _load_json_cases() -> dict[str, E2ECase]:
    raw = json.loads(JSON_FIXTURE.read_text(encoding="utf-8"))
    return {
        item["id"]: E2ECase(
            case_id=item["id"],
            source=item["input"],
            expected=item["expected_output"],
            tags=tuple(tag.strip() for tag in item["tags"]),
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
        cases[case_id] = E2ECase(
            case_id=case_id,
            source=source,
            expected=expected,
            tags=tags,
        )
    return cases


def _normalize_result(
    cases: dict[str, E2ECase],
) -> dict[str, tuple[str, str, tuple[str, ...]]]:
    return {
        key: (case.source, case.expected, tuple(case.tags))
        for key, case in cases.items()
    }


def test_json_and_xml_corpora_cover_the_same_cases() -> None:
    json_cases = _load_json_cases()
    xml_cases = _load_xml_cases()

    assert set(json_cases) == set(xml_cases)
    assert _normalize_result(json_cases) == _normalize_result(xml_cases)


@pytest.mark.parametrize("fixture", [_load_json_cases(), _load_xml_cases()])
@pytest.mark.parametrize(
    "case_id",
    [
        "spelling_zeby",
        "spelling_wlasnie",
        "spelling_jestes",
        "agreement_ty_imie",
        "agreement_oni_plural",
        "syntax_list_spacing",
        "punctuation_comma_spacing",
        "name_case_forms_reference",
        "name_plural_reference",
    ],
)
def test_end_to_end_polish_correction_corpus_fixtures(
    fixture: dict[str, E2ECase],
    case_id: str,
) -> None:
    case = fixture[case_id]
    analyzer = Analyzer(AnalyzerConfig(use_local_heuristic_backend=False))

    result = analyzer.analyze(case.source)
    corrected = result.apply(tuple(item.id for item in result.issues))

    assert corrected == case.expected


def test_corpus_contains_name_and_inflection_variants() -> None:
    json_cases = _load_json_cases()
    name_cases = [case for case in json_cases.values() if "name" in case.tags]

    assert any("spelling" in case.tags for case in name_cases)
    assert any(
        "person_inflection" in case.tags or "number" in case.tags for case in name_cases
    )
    assert {case.case_id for case in name_cases} >= {
        "spelling_jestes",
        "agreement_ty_imie",
    }
