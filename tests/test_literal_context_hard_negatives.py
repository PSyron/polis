"""Hard-negative corpus for literal-rule context abstention (#338 F0.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions, Category

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "rules"
    / "literal_context_hard_negatives.json"
)


def _load_fixture() -> dict[str, Any]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_literal_context_hard_negative_fixture_contract() -> None:
    payload = _load_fixture()

    assert payload["schema_id"] == "polis.literal-context-hard-negatives"
    assert payload["schema_version"] == 1
    assert payload["id"] == "polis_literal_context_hard_negatives_v1"
    assert payload["license"] == "CC0-1.0"

    cases = payload["cases"]
    assert isinstance(cases, list)
    assert len(cases) >= 3

    measured = [case for case in cases if case["measured_defect"] is True]
    assert {case["id"] for case in measured} == {
        "literal_hn_url_wogole",
        "literal_hn_email_wogole",
        "literal_hn_quoted_historical_wogole",
    }
    for case in cases:
        assert case["input"] == case["expected_output"]
        assert case["protected_phenomenon"]
        assert "hard_negative" in case["tags"]


def test_red_green_evidence_records_measured_false_positives() -> None:
    """Recorded RED spans match the three measured defects from #338."""
    payload = _load_fixture()
    evidence = cast(dict[str, Any], payload["red_green_evidence"])

    assert evidence["issue"] == 338
    assert evidence["slice"] == "F0.2"
    assert evidence["measured_case_ids"] == [
        "literal_hn_url_wogole",
        "literal_hn_email_wogole",
        "literal_hn_quoted_historical_wogole",
    ]

    red_findings = cast(list[dict[str, Any]], evidence["red_behavior"]["findings"])
    assert [
        (
            item["case_id"],
            item["source"],
            item["start"],
            item["end"],
            item["original"],
            item["suggestion"],
        )
        for item in red_findings
    ] == [
        (
            "literal_hn_url_wogole",
            "rule:spelling.wogole",
            20,
            26,
            "wogole",
            "w ogóle",
        ),
        (
            "literal_hn_email_wogole",
            "rule:spelling.wogole",
            16,
            22,
            "wogole",
            "w ogóle",
        ),
        (
            "literal_hn_quoted_historical_wogole",
            "rule:spelling.wogole",
            23,
            29,
            "wogole",
            "w ogóle",
        ),
    ]
    assert evidence["green_behavior"]["expected_findings"] == []


@pytest.mark.parametrize(
    "case_id",
    (
        "literal_hn_url_wogole",
        "literal_hn_email_wogole",
        "literal_hn_quoted_historical_wogole",
        "literal_hn_bare_domain_path_wogole",
        "literal_hn_query_param_wogole",
        "literal_hn_email_domain_label_wogole",
        "literal_hn_identifier_hyphen_wogole",
        "literal_hn_identifier_underscore_wogole",
        "literal_hn_url_zeby",
    ),
)
def test_hard_negative_cases_emit_zero_findings(case_id: str) -> None:
    payload = _load_fixture()
    cases_raw = payload["cases"]
    assert isinstance(cases_raw, list)
    cases = {str(case["id"]): case for case in cases_raw}
    case = cases[case_id]
    assert isinstance(case, dict)

    result = Analyzer(AnalyzerConfig()).analyze(
        str(case["input"]),
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    assert case["input"] == case["expected_output"]
    assert result.issues == ()


def test_measured_hard_negatives_green_after_f0_1_guard() -> None:
    """GREEN half of RED→GREEN: measured cases abstain on current runtime."""
    payload = _load_fixture()
    evidence = cast(dict[str, Any], payload["red_green_evidence"])
    measured_ids = set(cast(list[str], evidence["measured_case_ids"]))
    cases_raw = payload["cases"]
    assert isinstance(cases_raw, list)
    cases = [case for case in cases_raw if case["id"] in measured_ids]
    analyzer = Analyzer(AnalyzerConfig())

    for case in cases:
        assert isinstance(case, dict)
        result = analyzer.analyze(
            str(case["input"]),
            options=AnalysisOptions(categories={Category.SPELLING}),
        )
        assert result.issues == (), case["id"]
