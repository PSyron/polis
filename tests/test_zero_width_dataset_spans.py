from __future__ import annotations

from typing import Literal, Protocol, assert_never

import pytest
from tests.calibration_test_helpers import (
    canonical_bytes,
    synthetic_config,
    synthetic_manifest,
)
from tests.independent_dataset_test_helpers import dataset_document, dataset_manifest

from polis.evaluation.calibration_contract import (
    parse_calibration_config,
    parse_calibration_manifest,
)
from polis.evaluation.calibration_dataset import load_calibration_dataset_bytes
from polis.evaluation.calibration_manifest import parse_frozen_dataset_manifest
from polis.evaluation.calibration_models import (
    CalibrationContractError,
    JsonObject,
)
from polis.evaluation.holdout_v2_dataset import load_holdout_v2_dataset_bytes

type DatasetKind = Literal["calibration", "holdout"]
type InvalidSpan = Literal["nonempty-zero", "empty-positive", "out-of-bounds"]


class _FindingView(Protocol):
    start: int
    end: int
    original: str
    suggestion: str


class _CaseView(Protocol):
    expected_findings: tuple[_FindingView, ...]


class _DatasetView(Protocol):
    cases: tuple[_CaseView, ...]


def _load(kind: DatasetKind, document: JsonObject) -> _DatasetView:
    raw = canonical_bytes(document)
    match kind:
        case "calibration":
            manifest = parse_calibration_manifest(
                canonical_bytes(synthetic_manifest(raw))
            )
            config = parse_calibration_config(canonical_bytes(synthetic_config()))
            calibration_dataset: _DatasetView = load_calibration_dataset_bytes(
                raw, manifest, config
            )
            return calibration_dataset
        case "holdout":
            manifest = parse_frozen_dataset_manifest(
                canonical_bytes(dataset_manifest("holdout", raw)), "holdout"
            )
            holdout_dataset: _DatasetView = load_holdout_v2_dataset_bytes(raw, manifest)
            return holdout_dataset
        case unreachable:
            assert_never(unreachable)


def _first_finding(document: JsonObject) -> JsonObject:
    cases = document["cases"]
    assert isinstance(cases, list) and isinstance(cases[0], dict)
    findings = cases[0]["expected_findings"]
    assert isinstance(findings, list) and isinstance(findings[0], dict)
    return findings[0]


@pytest.mark.parametrize("kind", ["calibration", "holdout"])
def test_loader_preserves_ordinary_replacement_span(kind: DatasetKind) -> None:
    document = dataset_document(kind)

    dataset = _load(kind, document)

    finding = dataset.cases[0].expected_findings[0]
    assert (finding.start, finding.end, finding.original, finding.suggestion) == (
        0,
        5,
        "Żółty",
        "Zielony",
    )


@pytest.mark.parametrize("kind", ["calibration", "holdout"])
def test_loader_accepts_zero_width_insertion_with_empty_original(
    kind: DatasetKind,
) -> None:
    document = dataset_document(kind)
    finding = _first_finding(document)
    finding["start"] = 5
    finding["end"] = 5
    finding["original"] = ""
    finding["suggestion"] = " nowy"

    dataset = _load(kind, document)

    parsed = dataset.cases[0].expected_findings[0]
    assert (parsed.start, parsed.end, parsed.original, parsed.suggestion) == (
        5,
        5,
        "",
        " nowy",
    )


@pytest.mark.parametrize("kind", ["calibration", "holdout"])
def test_loader_accepts_deletion_with_empty_suggestion(kind: DatasetKind) -> None:
    document = dataset_document(kind)
    finding = _first_finding(document)
    finding["suggestion"] = ""

    dataset = _load(kind, document)

    parsed = dataset.cases[0].expected_findings[0]
    assert (parsed.start, parsed.end, parsed.original, parsed.suggestion) == (
        0,
        5,
        "Żółty",
        "",
    )


@pytest.mark.parametrize("kind", ["calibration", "holdout"])
def test_loader_rejects_empty_insertion_suggestion_noop(kind: DatasetKind) -> None:
    document = dataset_document(kind)
    finding = _first_finding(document)
    finding["start"] = 5
    finding["end"] = 5
    finding["original"] = ""
    finding["suggestion"] = ""

    with pytest.raises(CalibrationContractError):
        _load(kind, document)


@pytest.mark.parametrize("kind", ["calibration", "holdout"])
@pytest.mark.parametrize(
    "invalid_span", ["nonempty-zero", "empty-positive", "out-of-bounds"]
)
def test_loader_rejects_malformed_insertion_and_replacement_spans(
    kind: DatasetKind,
    invalid_span: InvalidSpan,
) -> None:
    document = dataset_document(kind)
    finding = _first_finding(document)
    match invalid_span:
        case "nonempty-zero":
            finding["start"] = 0
            finding["end"] = 0
            finding["original"] = "Ż"
        case "empty-positive":
            finding["start"] = 0
            finding["end"] = 1
            finding["original"] = ""
        case "out-of-bounds":
            finding["start"] = 10_000
            finding["end"] = 10_000
            finding["original"] = ""
        case unreachable:
            assert_never(unreachable)

    with pytest.raises(CalibrationContractError):
        _load(kind, document)
