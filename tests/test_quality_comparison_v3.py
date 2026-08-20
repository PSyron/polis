"""Closing Umbrella F verification artifacts and corrected v3 cases (#353)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from polis import Analyzer, AnalyzerConfig
from polis.evaluation.quality_dataset import QualityDatasetVersion, load_quality_dataset
from polis.evaluation.quality_report import (
    load_quality_comparison,
    load_quality_report,
    load_quality_result,
    load_threshold_proposal,
    validate_threshold_proposal,
)
from polis.evaluation.quality_report_models import ThresholdProposalV3

ROOT = Path(__file__).resolve().parents[1]
V3_DATASET_SHA = "8f6dec8379af6330f2fb8330421f6a6581f6c9e39ad98fe304322b4a9abb6276"
COMPARISON = ROOT / "docs/quality-comparison-v3.json"
RESULT_DEFAULT = ROOT / "docs/quality-result-v3-default.json"
RESULT_MORPHOLOGY = ROOT / "docs/quality-result-v3-morphology.json"
PROPOSAL = Path("docs/quality-threshold-proposal-v3.json")
BASELINE_DEFAULT = Path("docs/quality-baseline-v3-default.json")
BASELINE_MORPHOLOGY = Path("docs/quality-baseline-v3-morphology.json")
PROTECTED = {
    ROOT / "docs/quality-baseline-v2-default.json": (
        "c1d0c19d6b0a5f7dbec1c36df28917b908b3d0a78dba32285f45e990e64f8b95"
    ),
    ROOT / "docs/quality-baseline-v2-morphology.json": (
        "6ee2fea48983d8c29346a9e8eebf3859cfc1d6e12d9c48e05a3ef399af4415a7"
    ),
    ROOT / "docs/quality-threshold-proposal-v2.json": (
        "982a4c91809d71ccd90fc3575ea5ae812c92126e964515f2a5f183be95ed3875"
    ),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_protected_v2_and_wave0_artifacts_remain_byte_identical() -> None:
    for path, digest in PROTECTED.items():
        assert _sha(path) == digest
    assert (ROOT / "docs/quality-result-wave0-default.json").exists()
    assert (ROOT / "docs/quality-result-wave0-morphology.json").exists()
    assert (ROOT / "docs/quality-comparison-v2.json").exists()


def test_reclassified_unicode_casing_cases_are_meaningful_mixed_case() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V3)
    assert dataset.canonical_sha256 == V3_DATASET_SHA
    by_id = {case.id: case for case in dataset.cases}
    month = by_id["v3_month_weekday_lowercase_unicode_casing_offset"]
    adj = by_id["v3_proper_adjective_lowercase_unicode_casing_offset"]
    assert month.text == "ŻÓŁĆ: Spotkamy się w Poniedziałek."
    assert adj.text == "ŻÓŁĆ: Uczę się języka Polskiego."
    assert month.text != month.text.upper()
    assert adj.text != adj.text.upper()
    analyzer = Analyzer(AnalyzerConfig())
    for case, source in (
        (month, "rule:spelling.month_weekday_lowercase"),
        (adj, "rule:spelling.proper_adjective_lowercase"),
    ):
        hits = [
            item
            for item in analyzer.analyze(case.text).issues
            if str(item.source) == source
        ]
        assert hits
        finding = hits[0]
        expected = case.findings[0]
        assert (finding.start, finding.end, finding.original, finding.suggestion) == (
            expected.start,
            expected.end,
            expected.original,
            expected.suggestion,
        )


def test_v3_comparison_exists_and_records_quality_pass_performance_fail() -> None:
    comparison = load_quality_comparison(COMPARISON)
    proposal = load_threshold_proposal(PROPOSAL)
    assert isinstance(proposal, ThresholdProposalV3)
    assert comparison.dataset_sha256 == V3_DATASET_SHA
    assert comparison.aggregate_verdict == "fail"
    for profile_id in ("default", "morphology"):
        profile = comparison.profiles[profile_id]
        quality = {
            gate.gate: gate.passed
            for gate in profile.gates
            if gate.gate.startswith("quality.")
        }
        assert all(quality.values())
        assert any(
            gate.gate.startswith("performance.") and not gate.passed
            for gate in profile.gates
        )
        assert profile.verdict == "fail"
    # #355: morphology latency/throughput may pass while RSS remains red.
    morph = comparison.profiles["morphology"]
    morph_gates = {gate.gate: gate.passed for gate in morph.gates}
    assert morph_gates["performance.maximum_peak_rss_bytes"] is False
    default = comparison.profiles["default"]
    default_gates = {gate.gate: gate.passed for gate in default.gates}
    assert default_gates["performance.maximum_p95_latency_ns"] is False


def test_v3_results_parse_and_bind_to_proposal_dataset() -> None:
    default = load_quality_result(RESULT_DEFAULT)
    morphology = load_quality_result(RESULT_MORPHOLOGY)
    proposal = load_threshold_proposal(PROPOSAL)
    assert isinstance(proposal, ThresholdProposalV3)
    assert default.dataset_sha256 == proposal.dataset_sha256 == V3_DATASET_SHA
    assert morphology.dataset_sha256 == proposal.dataset_sha256
    assert default.quality_precision == 1.0
    assert morphology.quality_precision == 1.0
    assert default.quality_false_alarm_rate == 0.0
    assert morphology.quality_false_alarm_rate == 0.0
    assert default.counts.true_positives == 111
    assert morphology.counts.true_positives == 151


def test_v3_proposal_validates_against_remeasured_baselines() -> None:
    proposal = load_threshold_proposal(PROPOSAL)
    validate_threshold_proposal(
        proposal,
        baseline_path=BASELINE_DEFAULT,
        morphology_baseline_path=BASELINE_MORPHOLOGY,
    )
    default = load_quality_report(BASELINE_DEFAULT)
    morphology = load_quality_report(BASELINE_MORPHOLOGY)
    assert default.counts.true_positives == 111
    assert morphology.counts.true_positives == 151
    assert default.dataset_sha256 == V3_DATASET_SHA


def test_current_runtime_cohort_contains_the_new_review_only_source() -> None:
    assert len(Analyzer(AnalyzerConfig()).source_identity_snapshot) == 62
