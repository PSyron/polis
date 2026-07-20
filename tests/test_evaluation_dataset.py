from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from polis.core import Category
from polis.evaluation.dataset import DATASET_PATH, load_dataset, validate_dataset

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTATION = ROOT / "docs" / "evaluation-dataset.md"


def _raw_dataset() -> dict[str, Any]:
    raw = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast(dict[str, Any], raw)


def test_committed_dataset_is_versioned_and_strictly_valid() -> None:
    dataset = load_dataset()

    assert dataset.schema_version == 1
    assert dataset.id == "polis_pl_initial_v1"
    assert dataset.cases
    actual_categories = {
        finding.category for case in dataset.cases for finding in case.findings
    }
    assert actual_categories == {category.value for category in Category}


def test_every_finding_maps_to_its_exact_unicode_fragment() -> None:
    dataset = load_dataset()

    for case in dataset.cases:
        for finding in case.findings:
            assert case.text[finding.start : finding.end] == finding.original


def test_every_incorrect_case_yields_its_intended_grammatical_sentence() -> None:
    expected_corrections = {
        "agreement_pronoun_neuter": "To zdanie jest poprawne.",
        "agreement_plural_subject_verb": "Oni są gotowi.",
        "inflection_negated_accusative": "Nie widzę samochodu.",
        "syntax_destination_preposition": "Pojechałem do Warszawy.",
        "syntax_missing_list_space": "1. Punkt pierwszy.",
        "spelling_na_pewno": "To jest na pewno ważne.",
        "punctuation_conditional_comma": "Jeśli pada, zostaję w domu.",
        "punctuation_duplicate_comma": "Cześć, Anno.",
        "style_repeated_intensifier": "Bardzo lubię tę książkę.",
    }
    incorrect_cases = {
        case.id: case for case in load_dataset().cases if case.outcome == "incorrect"
    }

    assert set(incorrect_cases) == set(expected_corrections)
    for case_id, expected in expected_corrections.items():
        case = incorrect_cases[case_id]
        corrected = case.text
        for finding in sorted(case.findings, key=lambda item: item.start, reverse=True):
            corrected = (
                corrected[: finding.start]
                + finding.suggestion
                + corrected[finding.end :]
            )
        assert corrected == expected


def test_correct_cases_are_explicit_no_finding_negatives() -> None:
    dataset = load_dataset()

    correct_cases = [case for case in dataset.cases if case.outcome == "correct"]
    assert len(correct_cases) >= 4
    assert all(case.findings == () for case in correct_cases)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda dataset: dataset["cases"].append(copy.deepcopy(dataset["cases"][0])),
            "duplicate case id",
        ),
        (
            lambda dataset: dataset["cases"][0].pop("provenance"),
            "case must contain exactly",
        ),
        (
            lambda dataset: dataset["cases"][0]["provenance"].update(
                {"license": "MIT"}
            ),
            "CC0-1.0",
        ),
        (
            lambda dataset: dataset["cases"][0].update({"unexpected": True}),
            "unknown fields",
        ),
        (
            lambda dataset: dataset["cases"][0]["expected_findings"][0].update(
                {"category": "unknown"}
            ),
            "unknown category",
        ),
        (
            lambda dataset: dataset["cases"][0]["expected_findings"][0].update(
                {"start": -1}
            ),
            "non-negative integer",
        ),
        (
            lambda dataset: dataset["cases"][0]["expected_findings"][0].update(
                {"original": "nie ten fragment"}
            ),
            "does not match text range",
        ),
        (
            lambda dataset: dataset["cases"][0]["expected_findings"][0].update(
                {"suggestion": dataset["cases"][0]["expected_findings"][0]["original"]}
            ),
            "must differ from original",
        ),
        (
            lambda dataset: dataset["cases"][-1].update(
                {"expected_findings": [{"category": "spelling"}]}
            ),
            "correct case must explicitly contain no expected findings",
        ),
    ],
)
def test_validator_rejects_adversarial_dataset_data(mutate: Any, message: str) -> None:
    raw = _raw_dataset()
    mutate(raw)

    with pytest.raises(ValueError, match=message):
        validate_dataset(raw)


def test_validator_rejects_non_list_expected_findings_for_correct_case() -> None:
    raw = _raw_dataset()
    raw["cases"][-1]["expected_findings"] = None

    with pytest.raises(
        ValueError, match="correct case must explicitly contain no expected findings"
    ):
        validate_dataset(raw)


def test_validator_rejects_insertion_inside_replacement_span() -> None:
    raw = _raw_dataset()
    raw["cases"][0]["expected_findings"].append(
        {
            "category": "punctuation",
            "start": 1,
            "end": 1,
            "original": "",
            "suggestion": ",",
            "rationale": "Adversarial insertion inside a replacement.",
        }
    )

    with pytest.raises(ValueError, match="colliding expected findings"):
        validate_dataset(raw)


def test_validator_rejects_duplicate_insertions_at_one_offset() -> None:
    raw = _raw_dataset()
    raw["cases"][0]["expected_findings"] = [
        {
            "category": "punctuation",
            "start": 2,
            "end": 2,
            "original": "",
            "suggestion": ",",
            "rationale": "First adversarial insertion.",
        },
        {
            "category": "style",
            "start": 2,
            "end": 2,
            "original": "",
            "suggestion": "!",
            "rationale": "Second adversarial insertion at the same offset.",
        },
    ]

    with pytest.raises(ValueError, match="duplicate insertions"):
        validate_dataset(raw)


@pytest.mark.parametrize("insertion_offset", [2, 3])
def test_validator_allows_end_boundary_and_separated_insertions(
    insertion_offset: int,
) -> None:
    raw = _raw_dataset()
    raw["cases"][0]["expected_findings"].append(
        {
            "category": "punctuation",
            "start": insertion_offset,
            "end": insertion_offset,
            "original": "",
            "suggestion": ",",
            "rationale": "A deterministic non-colliding insertion.",
        }
    )

    validated = validate_dataset(raw)

    assert len(validated.cases[0].findings) == 2


def test_dataset_asset_is_distributed_with_the_package() -> None:
    assert DATASET_PATH == Path(DATASET_PATH)
    assert DATASET_PATH.is_file()


def test_dataset_documentation_states_stewardship_requirements() -> None:
    documentation = DOCUMENTATION.read_text(encoding="utf-8")

    for required_text in (
        "CC0-1.0",
        "human-reviewed",
        "private",
        "model-generated",
        "anonym",
        "experiments/nlp_dependencies",
    ):
        assert required_text in documentation
