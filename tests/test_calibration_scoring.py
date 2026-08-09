from __future__ import annotations

import importlib.util
from dataclasses import replace

import pytest
from tests.calibration_test_helpers import (
    canonical_bytes,
    synthetic_config,
    synthetic_dataset,
    synthetic_manifest,
)
from tests.denominator_test_constants import expected_counts, expected_verdict

from polis.core import Category, Confidence, Finding, Severity, Source
from polis.evaluation.calibration_contract import (
    parse_calibration_config,
    parse_calibration_manifest,
)
from polis.evaluation.calibration_dataset import load_calibration_dataset_bytes
from polis.evaluation.calibration_models import (
    CalibrationConfig,
    CalibrationDataset,
    KeyOutcome,
    KeyVerdict,
)
from polis.evaluation.calibration_sources import SOURCE_ROWS

if importlib.util.find_spec("polis.evaluation.calibration_scoring") is None:

    def test_planned_calibration_scoring_module_is_available() -> None:
        pytest.fail("planned calibration scoring module is absent")


else:
    from polis.evaluation.calibration_scoring import score_calibration

    type FindingsByCase = dict[str, tuple[Finding, ...]]

    def _inputs() -> tuple[CalibrationDataset, CalibrationConfig, FindingsByCase]:
        raw = canonical_bytes(synthetic_dataset())
        config = parse_calibration_config(canonical_bytes(synthetic_config()))
        manifest = parse_calibration_manifest(canonical_bytes(synthetic_manifest(raw)))
        dataset = load_calibration_dataset_bytes(raw, manifest, config)
        findings: FindingsByCase = {}
        for case in dataset.cases:
            if case.role == "error":
                expected = case.expected_findings[0]
                identity = next(
                    row for row in SOURCE_ROWS if row.source == expected.source
                )
                findings[case.id] = (
                    Finding.create(
                        category=Category(expected.category),
                        severity=Severity.ERROR,
                        message="Syntetyczne znalezisko.",
                        explanation="Syntetyczne wyjaśnienie.",
                        original=expected.original,
                        suggestion=expected.suggestion,
                        start=expected.start,
                        end=expected.end,
                        confidence=Confidence(identity.emitted_confidence),
                        source=Source.parse(expected.source),
                    ),
                )
        return dataset, config, findings

    def _only_changed(
        outcomes: tuple[KeyOutcome, ...], source: str, verdict: KeyVerdict
    ) -> None:
        assert (
            next(item for item in outcomes if item.identity.source == source).verdict
            == verdict
        )
        assert all(
            item.verdict == (expected_verdict(item.identity.source) or "candidate")
            for item in outcomes
            if item.identity.source != source
        )

    def test_finite_keys_are_structurally_insufficient_and_other_keys_candidate() -> (
        None
    ):
        dataset, config, findings = _inputs()

        outcomes = score_calibration(dataset, findings, config)

        assert len(outcomes) == 20
        assert all(
            item.verdict == (expected_verdict(item.identity.source) or "candidate")
            for item in outcomes
        )
        assert all(
            (item.counts.error_cases, item.counts.correct_cases)
            == expected_counts("calibration", item.identity.source)
            for item in outcomes
        )
        assert [item.observed_confidence for item in outcomes] == [
            row.emitted_confidence for row in SOURCE_ROWS
        ]
        assert [item.minimum_confidence for item in outcomes] == [
            None if expected_verdict(row.source) else row.emitted_confidence
            for row in SOURCE_ROWS
        ]

    def test_duplicate_exact_prediction_is_one_true_and_one_false_positive() -> None:
        dataset, config, findings = _inputs()
        source = SOURCE_ROWS[0].source
        case_id = next(key for key in findings if key.startswith("error-00-"))
        finding = findings[case_id][0]
        findings[case_id] = (finding, finding)

        outcomes = score_calibration(dataset, findings, config)
        changed = next(item for item in outcomes if item.identity.source == source)

        assert changed.counts.true_positive == 20
        assert changed.counts.false_positive == 1
        _only_changed(outcomes, source, "fail_threshold")

    def test_false_positive_changes_only_its_own_key() -> None:
        dataset, config, findings = _inputs()
        source = SOURCE_ROWS[0].source
        correct = next(
            case
            for case in dataset.cases
            if case.role == "correct" and case.primary_source_identity == source
        )
        template = next(
            values[0]
            for case_id, values in findings.items()
            if case_id.startswith("error-00-")
        )
        findings[correct.id] = (template,)

        _only_changed(
            score_calibration(dataset, findings, config), source, "fail_threshold"
        )

    def test_wrong_suggestion_changes_only_its_own_key() -> None:
        dataset, config, findings = _inputs()
        source = SOURCE_ROWS[0].source
        case_id = next(key for key in findings if key.startswith("error-00-"))
        finding = findings[case_id][0]
        findings[case_id] = (
            Finding.create(
                category=finding.category,
                severity=finding.severity,
                message=finding.message,
                explanation=finding.explanation,
                original=finding.original,
                suggestion="Inna poprawa",
                start=finding.start,
                end=finding.end,
                confidence=finding.confidence,
                source=finding.source,
            ),
        )

        _only_changed(
            score_calibration(dataset, findings, config), source, "fail_threshold"
        )

    def test_correction_accuracy_is_conditional_on_exact_span_matches() -> None:
        dataset, config, findings = _inputs()
        source = SOURCE_ROWS[0].source
        case_id = next(key for key in findings if key.startswith("error-00-"))
        finding = findings[case_id][0]
        findings[case_id] = (
            Finding.create(
                category=finding.category,
                severity=finding.severity,
                message=finding.message,
                explanation=finding.explanation,
                original="łąd",
                suggestion=finding.suggestion,
                start=1,
                end=4,
                confidence=finding.confidence,
                source=finding.source,
            ),
        )

        outcome = next(
            item
            for item in score_calibration(dataset, findings, config)
            if item.identity.source == source
        )

        assert outcome.metrics.exact_span_accuracy == 19 / 20
        assert outcome.metrics.exact_correction_accuracy == 1.0
        assert outcome.verdict == "fail_threshold"

    @pytest.mark.parametrize("mutation", ["missing", "multiple", "drift"])
    def test_confidence_evidence_is_fail_closed_and_local(mutation: str) -> None:
        dataset, config, findings = _inputs()
        source = SOURCE_ROWS[0].source
        keys = [key for key in findings if key.startswith("error-00-")]
        if mutation == "missing":
            for key in keys:
                del findings[key]
        elif mutation == "multiple":
            finding = findings[keys[0]][0]
            findings[keys[0]] = (replace(finding, confidence=Confidence(0.5)),)
        else:
            for key in keys:
                finding = findings[key][0]
                findings[key] = (replace(finding, confidence=Confidence(0.5)),)

        _only_changed(
            score_calibration(dataset, findings, config),
            source,
            "insufficient_evidence",
        )

    def test_cross_source_false_positive_is_charged_to_prediction_source() -> None:
        dataset, config, findings = _inputs()
        charged_source = SOURCE_ROWS[1].source
        foreign_case = next(
            case
            for case in dataset.cases
            if case.role == "correct"
            and case.primary_source_identity == SOURCE_ROWS[0].source
        )
        template = next(
            values[0]
            for case_id, values in findings.items()
            if case_id.startswith("error-01-")
        )
        findings[foreign_case.id] = (template,)

        _only_changed(
            score_calibration(dataset, findings, config),
            charged_source,
            "fail_threshold",
        )

    def test_undefined_precision_is_none_for_missing_provider() -> None:
        dataset, config, findings = _inputs()
        source = SOURCE_ROWS[0].source
        for key in [key for key in findings if key.startswith("error-00-")]:
            del findings[key]

        outcome = next(
            item
            for item in score_calibration(dataset, findings, config)
            if item.identity.source == source
        )

        assert outcome.verdict == "insufficient_evidence"
        assert outcome.metrics.precision is None
        assert outcome.metrics.recall == 0.0
