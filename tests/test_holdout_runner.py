from __future__ import annotations

import importlib
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest
from tests.holdout_config_fixture import synthetic_config
from tests.holdout_test_helpers import (
    CONFIG_SHA256,
    DATASET_SHA256,
    SOURCE_SHA256,
    AdmissionEvidence,
    JsonObject,
    approved_admission,
)

from polis import Finding


class _RunnerResultView(Protocol):
    raw_report_path: Path
    normalized_report_path: Path


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


@dataclass(frozen=True, slots=True)
class _Dependencies:
    observed_admission: AdmissionEvidence
    load_dataset: Callable[[Path], tuple[str, ...]]
    analyzer: Callable[[str], tuple[Finding, ...]]
    clock_ns: Callable[[], int]
    rss_probe: Callable[[], int]
    reserved_at: Callable[[], str]
    output_directory: Path


@runtime_checkable
class _RunnerApi(Protocol):
    HoldoutAdmissionError: type[Exception]
    HoldoutAlreadyConsumedError: type[Exception]

    def run_synthetic_holdout(
        self,
        config_document: JsonObject,
        dependencies: _Dependencies,
    ) -> _RunnerResultView: ...

    def run_from_config(
        self, config_path: Path, *, repository_root: Path | None = None
    ) -> int: ...

    def load_holdout_dataset(
        self, path: Path, config: _DatasetConfig
    ) -> _LoadedDatasetView: ...


def _runner() -> _RunnerApi:
    try:
        module = importlib.import_module("polis.evaluation.holdout_runner")
    except ModuleNotFoundError as error:
        raise AssertionError(
            "planned one-shot holdout runner implementation is absent"
        ) from error
    if not isinstance(module, _RunnerApi):
        raise AssertionError("planned one-shot holdout runner API is incomplete")
    return module


def _dependencies(
    tmp_path: Path,
    events: list[str],
    *,
    admission: AdmissionEvidence | None = None,
    fail_after_load: bool = False,
) -> _Dependencies:
    marker = tmp_path / "holdout.started"

    def load_dataset(_path: Path) -> tuple[str, ...]:
        marker_payload = json.loads(marker.read_text(encoding="utf-8"))
        assert marker_payload == {
            "experiment_id": "polis-a-b-one-shot-v1",
            "config_sha256": CONFIG_SHA256,
            "source_sha256": SOURCE_SHA256,
            "dataset_sha256": DATASET_SHA256,
            "reserved_at": "2026-08-08T20:30:00Z",
        }
        events.append("load")
        if fail_after_load:
            raise KeyboardInterrupt
        return ("synthetic-case",)

    def analyzer(_text: str) -> tuple[Finding, ...]:
        events.append("analyze")
        return ()

    return _Dependencies(
        observed_admission=admission or approved_admission(),
        load_dataset=load_dataset,
        analyzer=analyzer,
        clock_ns=iter(range(0, 1000, 10)).__next__,
        rss_probe=lambda: 123456,
        reserved_at=lambda: "2026-08-08T20:30:00Z",
        output_directory=tmp_path,
    )


def test_loader_entry_observes_durable_marker_after_successful_admission(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    result = _runner().run_synthetic_holdout(
        synthetic_config(), _dependencies(tmp_path, events)
    )

    assert events[0] == "load"
    assert events.count("load") == 1
    assert (tmp_path / "holdout.started").exists()
    assert result.raw_report_path == tmp_path / "report.json"
    assert result.normalized_report_path == tmp_path / "normalized-report.json"


@pytest.mark.parametrize(
    ("admission", "message"),
    [
        (replace(approved_admission(), config_sha256="0" * 64), "config_sha256"),
        (replace(approved_admission(), source_sha256="1" * 64), "source_sha256"),
        (replace(approved_admission(), dataset_sha256="2" * 64), "dataset_sha256"),
        (replace(approved_admission(), merge_commit=None), "evaluated_merge_commit"),
        (
            replace(approved_admission(), merge_commit="6" * 40),
            "evaluated_merge_commit",
        ),
        (
            replace(approved_admission(), verification_verified=None),
            "verification_verified",
        ),
        (
            replace(approved_admission(), verification_verified=False),
            "verification_verified",
        ),
        (
            replace(approved_admission(), verification_reason=None),
            "verification_reason",
        ),
        (
            replace(approved_admission(), verification_reason="unsigned"),
            "verification_reason",
        ),
        (
            replace(approved_admission(), verification_payload_sha256=None),
            "verification_payload_sha256",
        ),
        (
            replace(approved_admission(), verification_payload_sha256="8" * 64),
            "verification_payload_sha256",
        ),
    ],
)
def test_identity_or_signature_admission_failure_stops_before_marker_and_loader(
    admission: AdmissionEvidence, message: str, tmp_path: Path
) -> None:
    events: list[str] = []
    dependencies = _dependencies(tmp_path, events, admission=admission)

    with pytest.raises(_runner().HoldoutAdmissionError, match=message):
        _runner().run_synthetic_holdout(synthetic_config(), dependencies)

    assert events == []
    assert not (tmp_path / "holdout.started").exists()


def test_interruption_after_reservation_leaves_marker_and_denies_repeat(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    dependencies = _dependencies(tmp_path, events, fail_after_load=True)

    with pytest.raises(KeyboardInterrupt):
        _runner().run_synthetic_holdout(synthetic_config(), dependencies)

    marker = tmp_path / "holdout.started"
    assert marker.exists()
    with pytest.raises(_runner().HoldoutAlreadyConsumedError):
        _runner().run_synthetic_holdout(synthetic_config(), dependencies)
    assert events.count("load") == 1


def test_partial_report_is_never_repaired_or_used_to_allow_retry(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "holdout.started"
    marker.write_text("partial", encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text("partial", encoding="utf-8")
    before = (marker.read_bytes(), report.read_bytes())
    events: list[str] = []

    with pytest.raises(_runner().HoldoutAlreadyConsumedError):
        _runner().run_synthetic_holdout(
            synthetic_config(), _dependencies(tmp_path, events)
        )

    assert events == []
    assert (marker.read_bytes(), report.read_bytes()) == before


def test_runner_has_no_retry_or_replace_surface() -> None:
    parameters = set(inspect.signature(_runner().run_synthetic_holdout).parameters)

    assert parameters == {"config_document", "dependencies"}
