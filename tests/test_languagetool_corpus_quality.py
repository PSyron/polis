from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from polis import AnalysisOptions
from polis.rules import (
    LanguageToolRuleConfig,
    LocalLanguageToolRule,
    LoopbackLanguageToolHttpTransport,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.json"
SNAPSHOT = (
    ROOT / "tests" / "fixtures" / "languagetool" / "allowlisted_pl_68_snapshot.json"
)


def _load(path: Path) -> dict[str, Any]:
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _predictions(snapshot: dict[str, Any]) -> dict[str, set[tuple[int, int, str]]]:
    raw: Any = snapshot["findings_by_case"]
    assert isinstance(raw, dict)
    return {
        case_id: {tuple(finding) for finding in findings}
        for case_id, findings in raw.items()
    }


def test_recorded_allowlist_meets_corpus_quality_gate() -> None:
    corpus = _load(CORPUS)
    snapshot = _load(SNAPSHOT)
    predictions = _predictions(snapshot)
    cases: Any = corpus["cases"]
    assert isinstance(cases, list)

    digest = hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    assert snapshot["tool"] == "LanguageTool"
    assert snapshot["version"] == "6.8"
    assert snapshot["corpus_sha256"] == digest

    all_ids = {case["id"] for case in cases}
    zero_ids = set(snapshot["zero_finding_case_ids"])
    assert set(predictions).isdisjoint(zero_ids)
    assert set(predictions) | zero_ids == all_ids

    gold: dict[str, set[tuple[int, int, str]]] = {}
    negative_ids: set[str] = set()
    for case in cases:
        case_id = case["id"]
        if case["verification"] == "negative":
            negative_ids.add(case_id)
        gold[case_id] = {
            (finding["start"], finding["end"], finding["suggestion"])
            for finding in case["expected_findings"]
            if finding["category"] == "punctuation"
        }

    true_positives = sum(
        len(predictions.get(case_id, set()) & expected)
        for case_id, expected in gold.items()
    )
    predicted_total = sum(len(items) for items in predictions.values())
    gold_total = sum(len(items) for items in gold.values())
    false_positives = predicted_total - true_positives
    false_negatives = gold_total - true_positives

    assert (true_positives, false_positives, false_negatives) == (18, 0, 6)
    assert true_positives / predicted_total == 1.0
    assert true_positives / gold_total == 0.75
    assert 2 * true_positives / (
        2 * true_positives + false_positives + false_negatives
    ) == pytest.approx(0.8571428571)
    assert all(case_id not in predictions for case_id in negative_ids)


@pytest.mark.slow
def test_real_local_languagetool_matches_reviewed_snapshot() -> None:
    base_url = os.environ.get("POLIS_LANGUAGETOOL_URL")
    if base_url is None:
        pytest.skip("set POLIS_LANGUAGETOOL_URL for the local 6.8 integration test")
    corpus = _load(CORPUS)
    snapshot = _load(SNAPSHOT)
    expected = _predictions(snapshot)
    config = LanguageToolRuleConfig(base_url=base_url, timeout_seconds=30.0)
    rule = LocalLanguageToolRule(
        config=config,
        transport=LoopbackLanguageToolHttpTransport(config),
    )

    actual: dict[str, set[tuple[int, int, str]]] = {}
    for case in corpus["cases"]:
        findings = rule.find(case["input"], options=AnalysisOptions())
        if findings:
            actual[case["id"]] = {
                (finding.start, finding.end, finding.suggestion or "")
                for finding in findings
            }

    assert actual == expected
