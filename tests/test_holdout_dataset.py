from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from tests.holdout_test_helpers import SOURCE_IDENTITIES, JsonObject, JsonValue

from polis.evaluation.holdout_runner import load_holdout_dataset


class _CaseView(Protocol):
    id: str


class _LoadedDatasetView(Protocol):
    id: str
    cases: tuple[_CaseView, ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class _DatasetMetadata:
    sha256: str
    size_bytes: int
    case_count: int
    mode: str


@dataclass(frozen=True, slots=True)
class _SourceMetadata:
    source: str
    category: str


@dataclass(frozen=True, slots=True)
class _DatasetConfig:
    experiment_id: str
    dataset: _DatasetMetadata
    source_identities: tuple[_SourceMetadata, ...]


def test_schema_only_loader_accepts_canonical_synthetic_dataset(tmp_path: Path) -> None:
    cases: list[JsonValue] = []
    for index in range(52):
        source = SOURCE_IDENTITIES[index % len(SOURCE_IDENTITIES)]
        cases.append(
            {
                "id": f"abv1-{index + 1:03d}",
                "license": "CC0-1.0",
                "provenance": "project-authored-independent-review",
                "role": "correct",
                "targets": [source[0]],
                "taxonomy": {"features": [source[1]]},
                "text": "Syntetyczny przypadek.",
                "expected_findings": [],
            }
        )
    document: JsonObject = {
        "schema_id": "polis.a-b-one-shot.dataset",
        "schema_version": 1,
        "id": "polis-a-b-one-shot-v1",
        "language": "pl",
        "license": "CC0-1.0",
        "cases": cases,
    }
    content = (
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    dataset_path = tmp_path / "cases.json"
    dataset_path.write_bytes(content)
    dataset_path.chmod(0o600)
    config = _DatasetConfig(
        "polis-a-b-one-shot-v1",
        _DatasetMetadata(hashlib.sha256(content).hexdigest(), len(content), 52, "0600"),
        tuple(_SourceMetadata(item[0], item[1]) for item in SOURCE_IDENTITIES),
    )

    loaded: _LoadedDatasetView = load_holdout_dataset(dataset_path, config)

    assert loaded.id == "polis-a-b-one-shot-v1"
    assert len(loaded.cases) == 52
    assert loaded.sha256 == config.dataset.sha256
