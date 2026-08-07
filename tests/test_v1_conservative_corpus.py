from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from polis import Analyzer, AnalyzerConfig, CorrectionConflictError, Finding

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "v1" / "conservative_corrections.json"

FROZEN_V1_RULE_SOURCES = frozenset(
    {
        "rule:agreement.copula",
        "rule:spelling.zeby",
        "rule:spelling.wlasnie",
        "rule:spelling.jestes",
        "rule:syntax.comma_space",
        "rule:syntax.sentence_space",
        "rule:syntax.list_space",
        "rule:syntax.quote_space",
        "rule:syntax.missing_reflexive",
        "rule:syntax.missing_correlative",
    }
)


def _load_cases() -> list[dict[str, Any]]:
    assert FIXTURE.is_file(), "missing editable conservative v1 fixture"

    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
    assert raw["review_status"] == "maintainer-reviewed"
    assert isinstance(raw["cases"], list)

    return raw["cases"]


def _issue_view(issue: Finding) -> dict[str, object]:
    return {
        "category": issue.category.value,
        "start": issue.start,
        "end": issue.end,
        "replacement": issue.suggestion,
        "source": str(issue.source),
    }


def _validate_cases(cases: list[dict[str, Any]]) -> None:
    assert cases
    case_ids: list[str] = []
    for case in cases:
        assert set(case) >= {
            "id",
            "kind",
            "input",
            "expected_issues",
        }
        assert isinstance(case["id"], str) and case["id"].startswith("v1-")
        case_ids.append(case["id"])
        assert case["kind"] in {"error", "correct", "abstain"}
        assert isinstance(case["input"], str) and case["input"]
        assert isinstance(case["expected_issues"], list)

        if case["kind"] == "error":
            assert isinstance(case.get("rule_source"), str)
            assert isinstance(case.get("category"), str)
            assert case["expected_issues"]
            if case.get("application"):
                assert isinstance(case.get("expected_output"), str)
            for issue in case["expected_issues"]:
                assert set(issue) == {
                    "category",
                    "start",
                    "end",
                    "replacement",
                    "source",
                }
                assert isinstance(issue["start"], int)
                assert isinstance(issue["end"], int)
                assert 0 <= issue["start"] <= issue["end"] <= len(case["input"])
                assert isinstance(issue["replacement"], str)
        else:
            assert case["expected_issues"] == []

        if case["kind"] == "abstain":
            assert isinstance(case.get("reason"), str) and case["reason"].strip()

    assert len(case_ids) == len(set(case_ids)), "duplicate case id"


def test_fixture_schema_requires_explicit_conservative_cases() -> None:
    _validate_cases(_load_cases())


def test_fixture_schema_rejects_duplicate_case_ids() -> None:
    duplicate_cases = [
        {
            "id": "v1-001",
            "kind": "correct",
            "input": "To jest poprawne zdanie.",
            "expected_issues": [],
        },
        {
            "id": "v1-001",
            "kind": "correct",
            "input": "To również jest poprawne zdanie.",
            "expected_issues": [],
        },
    ]

    with pytest.raises(AssertionError, match="duplicate case id"):
        _validate_cases(duplicate_cases)


def test_fixture_covers_every_frozen_v1_rule_with_error_and_close_negative() -> None:
    cases = _load_cases()

    error_sources = {case["rule_source"] for case in cases if case["kind"] == "error"}
    correct_sources = {
        case["rule_source"] for case in cases if case["kind"] == "correct"
    }

    assert FROZEN_V1_RULE_SOURCES <= error_sources
    assert FROZEN_V1_RULE_SOURCES <= correct_sources


def test_fixture_captures_exact_runtime_findings_and_safe_application() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    for case in _load_cases():
        result = analyzer.analyze(case["input"])
        actual = [_issue_view(issue) for issue in result.issues]

        assert actual == case["expected_issues"], case["id"]
        if case.get("application"):
            assert (
                result.apply(tuple(issue.id for issue in result.issues))
                == case["expected_output"]
            )
        if case.get("overlap"):
            with pytest.raises(CorrectionConflictError):
                result.apply(tuple(issue.id for issue in result.issues))


def test_fixture_contains_required_conservative_abstentions() -> None:
    abstentions = {
        case["input"]: case for case in _load_cases() if case["kind"] == "abstain"
    }

    assert "Gdy wrócisz, zadzwoń do mnie wczoraj." in abstentions
    assert "Ten raport wczoraj przygotowała Anna." in abstentions
    assert "Jan powiedział Ani, że przyjdzie jutro." in abstentions
    assert all(case["expected_issues"] == [] for case in abstentions.values())
    assert (
        "tense/aspect" in abstentions["Gdy wrócisz, zadzwoń do mnie wczoraj."]["reason"]
    )
    assert "style" in abstentions["Ten raport wczoraj przygotowała Anna."]["reason"]
    assert "intent" in abstentions["Jan powiedział Ani, że przyjdzie jutro."]["reason"]
