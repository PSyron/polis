from __future__ import annotations

from hashlib import sha256
from importlib import import_module
from importlib.metadata import metadata, version
from importlib.util import find_spec
from pathlib import Path

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
        "polis.rules",
        "polis.segmentation",
    ],
)
def test_focused_package_modules_are_importable(module_name: str) -> None:
    assert import_module(module_name) is not None


def test_distribution_version_is_declared() -> None:
    assert version("polis-nlp") == "0.2.0"


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


def test_distribution_retains_evaluation_namespace_helpers() -> None:
    evaluation = import_module("polis.evaluation")

    loaded = evaluation.load_dataset()
    validated = evaluation.validate_dataset(
        {
            "schema_version": 1,
            "id": "package_boundary",
            "provenance": {
                "source": "project-authored",
                "license": "CC0-1.0",
                "created": "2026-08-05",
                "review_status": "human-reviewed",
                "notes": "Package-boundary retention check.",
            },
            "cases": [
                {
                    "id": "unchanged",
                    "outcome": "correct",
                    "text": "To jest poprawne zdanie.",
                    "provenance": {
                        "source": "project-authored",
                        "license": "CC0-1.0",
                        "created": "2026-08-05",
                        "review_status": "human-reviewed",
                        "notes": "Package-boundary retention check.",
                    },
                    "expected_findings": [],
                }
            ],
        }
    )

    assert loaded.cases
    assert validated.id == "package_boundary"


@pytest.mark.parametrize(
    "module_name",
    (
        "polis.llm",
        "polis.analysis.hybrid",
        "polis.evaluation.finetuning_dataset",
    ),
)
def test_v1_package_boundary_has_no_orphaned_model_modules(module_name: str) -> None:
    assert find_spec(module_name) is None


def test_v1_package_boundary_has_no_finetuning_generator() -> None:
    generator_path = (
        Path(__file__).parents[1] / "scripts/generate_finetuning_dataset.py"
    )

    assert not generator_path.exists()


def test_v1_package_boundary_has_no_rule_catalog_module() -> None:
    assert find_spec("polis.rules.catalog") is None


@pytest.mark.parametrize(
    ("evidence_path", "expected_sha256"),
    (
        (
            "docs/architecture/decisions/0021-rule-catalog-ownership.md",
            "dc28d7256f81f019691487771b4d16942a3698c67f4de8bc22cdbda4bfab76a2",
        ),
        (
            "docs/architecture/rule-catalog-inventory.md",
            "b1037fb8033e4d33c9442ebc0d1a4b78ebf4526ee68c4a343dbbbcc07979835b",
        ),
        (
            "docs/architecture/rule-catalog-inventory.json",
            "1b144c18267bbca328ac20b37e27cf5fc5ffb269b5c45683edcb35fc7928e40a",
        ),
    ),
)
def test_v1_rule_catalog_evidence_is_byte_for_byte_preserved(
    evidence_path: str, expected_sha256: str
) -> None:
    evidence = Path(__file__).parents[1] / evidence_path

    assert evidence.is_file()
    assert sha256(evidence.read_bytes()).hexdigest() == expected_sha256


def test_readme_states_runtime_first_product_boundary() -> None:
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    required_phrases = (
        "offline",
        "LanguageTool",
        "Żaden przetestowany model lokalny nie został zakwalifikowany",
    )

    for phrase in required_phrases:
        assert phrase in readme
    assert "documentation-contract" not in readme
