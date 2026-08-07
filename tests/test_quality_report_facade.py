from __future__ import annotations

from types import FunctionType

import pytest

import polis.evaluation.quality_report as quality_report_module
import polis.evaluation.quality_report_baseline as quality_report_baseline
import polis.evaluation.quality_report_models as quality_report_models
import polis.evaluation.quality_report_proposal as quality_report_proposal


@pytest.mark.parametrize(
    ("facade", "owner"),
    (
        (
            quality_report_module.QualityReportError,
            quality_report_models.QualityReportError,
        ),
        (
            quality_report_module.baseline_file_sha256,
            quality_report_baseline.baseline_file_sha256,
        ),
        (
            quality_report_module.load_quality_report,
            quality_report_baseline.load_quality_report,
        ),
        (
            quality_report_module.load_threshold_proposal,
            quality_report_proposal.load_threshold_proposal,
        ),
        (
            quality_report_module.quality_report_json,
            quality_report_baseline.quality_report_json,
        ),
        (
            quality_report_module.validate_threshold_proposal,
            quality_report_proposal.validate_threshold_proposal,
        ),
        (
            quality_report_module.write_quality_report,
            quality_report_baseline.write_quality_report,
        ),
    ),
)
def test_quality_report_facade_preserves_object_identity(
    facade: type | FunctionType,
    owner: type | FunctionType,
) -> None:
    assert facade is owner
