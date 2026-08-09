from __future__ import annotations

import importlib.util
from dataclasses import replace

import pytest
from tests.calibration_runner_test_helpers import (
    RecordingAnalyzer,
    SyntheticAnalyzerError,
    synthetic_run_inputs,
)

from polis.evaluation.calibration_models import CalibrationContractError
from polis.evaluation.calibration_sources import SOURCE_ROWS

if importlib.util.find_spec("polis.evaluation.calibration_runner") is None:

    def test_planned_calibration_runner_module_is_available() -> None:
        pytest.fail("planned calibration runner module is absent")


else:
    from polis.evaluation.calibration_models import CalibrationIntegrityError
    from polis.evaluation.calibration_runner import _run_admitted_calibration

    def test_one_warmup_and_five_measured_repetitions_are_deterministic() -> None:
        config, manifest, dataset, findings = synthetic_run_inputs()
        analyzer = RecordingAnalyzer(findings)

        result = _run_admitted_calibration(config, manifest, dataset, analyzer)

        texts = [case.text for case in dataset.cases]
        assert len(analyzer.calls) == 6438
        assert analyzer.calls[:1073] == texts
        assert all(
            analyzer.calls[start : start + 1073] == texts
            for start in range(1073, 6438, 1073)
        )
        assert len(result.repetition_hashes) == 5
        assert len(set(result.repetition_hashes)) == 1
        assert len(result.outcomes) == 20

    def test_fifth_repetition_drift_fails_without_a_result() -> None:
        config, manifest, dataset, findings = synthetic_run_inputs()
        analyzer = RecordingAnalyzer(findings, drift_call=5366)

        with pytest.raises(
            CalibrationIntegrityError,
            match="calibration findings changed between measured repetitions",
        ):
            _run_admitted_calibration(config, manifest, dataset, analyzer)

        assert len(analyzer.calls) == 6438

    @pytest.mark.parametrize("boundary", ["manifest", "source", "denominator"])
    def test_invalid_inputs_fail_before_analyzer(boundary: str) -> None:
        config, manifest, dataset, findings = synthetic_run_inputs()
        if boundary == "manifest":
            manifest = replace(manifest, dataset_sha256="b" * 64)
        elif boundary == "source":
            config = replace(config, source_rows=tuple(reversed(SOURCE_ROWS)))
        else:
            dataset = replace(dataset, cases=dataset.cases[1:])
        analyzer = RecordingAnalyzer(findings)

        with pytest.raises(CalibrationContractError):
            _run_admitted_calibration(config, manifest, dataset, analyzer)

        assert analyzer.calls == []

    def test_analyzer_exception_aborts_the_global_run() -> None:
        config, manifest, dataset, findings = synthetic_run_inputs()
        analyzer = RecordingAnalyzer(findings, failure_call=1201)

        with pytest.raises(SyntheticAnalyzerError):
            _run_admitted_calibration(config, manifest, dataset, analyzer)

        assert len(analyzer.calls) == 1201
