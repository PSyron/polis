from __future__ import annotations

from tests.test_quality_dataset import _raw_documents, _rebind_manifest

from polis.evaluation.quality_dataset import (
    load_quality_dataset,
    validate_quality_dataset,
)


def test_dataset_accepts_an_additional_reviewed_pair_for_existing_phenomenon() -> None:
    # Given
    raw, manifest = _raw_documents()
    raw["cases"].extend(
        [
            {
                "id": "quality_inflection_additional_error",
                "kind": "error",
                "phenomenon": "inflection",
                "pair_id": "pair_inflection_additional",
                "features": ["unicode"],
                "text": "Nie widzę samochód.",
                "expected_findings": [
                    {
                        "category": "inflection",
                        "start": 10,
                        "end": 18,
                        "original": "samochód",
                        "suggestion": "samochodu",
                        "rationale": (
                            "Po zaprzeczonym czasowniku „widzieć” w tej "
                            "zamkniętej konstrukcji potrzebny jest dopełniacz."
                        ),
                    }
                ],
                "rationale": None,
            },
            {
                "id": "quality_inflection_additional_correct",
                "kind": "correct",
                "phenomenon": "inflection",
                "pair_id": "pair_inflection_additional",
                "features": ["unicode"],
                "text": "Nie widzę samochodu.",
                "expected_findings": [],
                "rationale": None,
            },
        ]
    )
    manifest["review"]["reviewed_case_ids"] = [case["id"] for case in raw["cases"]]
    _rebind_manifest(raw, manifest)

    # When
    dataset = validate_quality_dataset(raw, manifest)

    # Then
    assert len(dataset.cases) == len(load_quality_dataset().cases) + 2
