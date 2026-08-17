"""Dispatch-performance headroom regressions for #355."""

from __future__ import annotations

import json
from pathlib import Path

from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions
from polis.evaluation.quality_dataset import QualityDatasetVersion, load_quality_dataset
from polis.rules._morfeusz import _load_qualified_morfeusz
from polis.rules.government import (
    _GOVERNED_FORM_CACHE,
    _SLUCHAC_FORM,
    InflectionGovernmentSluchacRadioRule,
    _governed_form_replacement,
)
from polis.rules.spelling import (
    SpellingConajmniejRule,
    SpellingWkoncuRule,
    SpellingWogoleRule,
    _closed_literal_empty_buckets,
    _closed_literal_lookup,
    _closed_literal_pattern,
    collect_closed_literal_findings,
)
from polis.segmentation import is_single_sentence, segment_sentences

PROPOSAL = Path("docs/quality-threshold-proposal-v3.json")
# Absolute performance caps must remain the #339 F1.3 / wave0 values.
_FROZEN_PERFORMANCE = {
    "default": {
        "maximum_p95_latency_ns": 39167,
        "minimum_throughput_cases_per_second": 33979.186566343364,
        "maximum_peak_rss_bytes": 30572544,
    },
    "morphology": {
        "maximum_p95_latency_ns": 197625,
        "minimum_throughput_cases_per_second": 18262.21596348732,
        "maximum_peak_rss_bytes": 74366976,
    },
}


def test_v3_proposal_performance_caps_remain_wave0_values() -> None:
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    for profile, expected in _FROZEN_PERFORMANCE.items():
        comparison = proposal["profiles"][profile]["performance_comparison"]
        for key, value in expected.items():
            assert comparison[key] == value


def test_wave4_government_pattern_first_skips_absent_surfaces() -> None:
    provider = _load_qualified_morfeusz()
    if provider is None:
        return
    before = len(_GOVERNED_FORM_CACHE)
    rule = InflectionGovernmentSluchacRadioRule(provider)
    assert rule.find("Brak zamkniętej powierzchni.", options=AnalysisOptions()) == ()
    # Absent surface must not grow the morphology qualification cache.
    assert len(_GOVERNED_FORM_CACHE) == before


def test_governed_form_replacement_caches_closed_form() -> None:
    provider = _load_qualified_morfeusz()
    if provider is None:
        return
    _GOVERNED_FORM_CACHE.clear()
    first = _governed_form_replacement(provider, _SLUCHAC_FORM)
    size_after_first = len(_GOVERNED_FORM_CACHE)
    second = _governed_form_replacement(provider, _SLUCHAC_FORM)
    assert first == second == "radia"
    assert len(_GOVERNED_FORM_CACHE) == size_after_first == 1


def test_closed_literal_surface_lookup_is_cached_per_rule_tuple() -> None:
    rules = (SpellingWogoleRule(), SpellingConajmniejRule())
    _closed_literal_lookup.cache_clear()
    first = _closed_literal_lookup(rules)
    second = _closed_literal_lookup(rules)
    assert first is second
    assert _closed_literal_lookup.cache_info().hits == 1


def test_closed_literal_pattern_is_cached_and_case_explicit() -> None:
    rules = (SpellingWogoleRule(), SpellingWkoncuRule(), SpellingConajmniejRule())
    _closed_literal_pattern.cache_clear()

    first = _closed_literal_pattern(rules)
    second = _closed_literal_pattern(rules)

    assert first is second
    assert first.findall("wogole WOGole wKoncu conajmniej CONAJMNIEJ") == [
        "wogole",
        "WOGole",
        "wKoncu",
        "conajmniej",
        "CONAJMNIEJ",
    ]
    assert first.search("ſogole") is None


def test_closed_literal_collector_uses_immutable_cached_empty_mapping() -> None:
    rules = (SpellingWogoleRule(), SpellingConajmniejRule())
    _closed_literal_empty_buckets.cache_clear()
    template = _closed_literal_empty_buckets(rules)

    empty_result = collect_closed_literal_findings("Poprawny tekst.", rules)
    result = collect_closed_literal_findings("Wogole błąd.", rules)

    assert empty_result is template
    assert not hasattr(template, "clear")
    assert result is not template
    assert tuple(result) == tuple(rule.source for rule in rules)
    assert result[rules[0].source]
    assert result[rules[1].source] == ()


def test_single_sentence_fast_probe_matches_segmenter_on_v3() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V3)
    for case in dataset.cases:
        assert is_single_sentence(case.text) is (len(segment_sentences(case.text)) == 1)


def test_quality_floors_remain_green_after_dispatch_optimization() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V3)
    analyzer = Analyzer(AnalyzerConfig())
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    for case in dataset.cases:
        issues = analyzer.analyze(case.text).issues
        expected = {
            (finding.start, finding.end, finding.original, finding.suggestion)
            for finding in case.findings
        }
        observed = {
            (item.start, item.end, item.original, item.suggestion) for item in issues
        }
        if case.findings:
            true_positives += len(expected & observed)
            false_negatives += len(expected - observed)
            false_positives += len(observed - expected)
        else:
            false_positives += len(observed)
    precision = true_positives / (true_positives + false_positives)
    assert precision == 1.0
    assert false_positives == 0
