from __future__ import annotations

from importlib import import_module
from importlib.metadata import metadata, version

import pytest

from polis import (
    AnalysisOptions,
    AnalysisResult,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
    analysis_result_from_json,
    analysis_result_to_json,
)


@pytest.mark.parametrize(
    "module_name",
    [
        "polis",
        "polis.analysis",
        "polis.cli",
        "polis.core",
        "polis.correction",
        "polis.evaluation",
        "polis.llm",
        "polis.rules",
        "polis.segmentation",
    ],
)
def test_focused_package_modules_are_importable(module_name: str) -> None:
    assert import_module(module_name) is not None


def test_distribution_version_is_declared() -> None:
    assert version("polis-nlp") == "0.1.0"


def test_distribution_uses_unambiguous_project_name() -> None:
    assert metadata("polis-nlp")["Name"] == "polis-nlp"


def test_distribution_metadata_declares_mit_license() -> None:
    distribution_metadata = metadata("polis-nlp")

    assert distribution_metadata["License-Expression"] == "MIT"
    assert distribution_metadata.get_all("License-File") == ["LICENSE"]


def test_public_analysis_model_exports_are_intentional() -> None:
    assert all(
        exported is not None
        for exported in (
            AnalysisOptions,
            AnalysisResult,
            Category,
            Confidence,
            Finding,
            Severity,
            Source,
            SourceKind,
            analysis_result_from_json,
            analysis_result_to_json,
        )
    )
