from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest
from tests.holdout_test_helpers import (
    CONFIG_SHA256,
    DATASET_SHA256,
    SOURCE_SHA256,
    JsonObject,
)


class _ConsumptionCapability(Protocol):
    @property
    def marker_path(self) -> Path: ...


class _DurabilityFilesystem(Protocol):
    def open_exclusive(self, path: Path, content: bytes) -> int: ...

    def open_directory(self, path: Path) -> int: ...

    def fsync(self, descriptor: int) -> None: ...

    def close(self, descriptor: int) -> None: ...


@runtime_checkable
class _ReservationApi(Protocol):
    HoldoutAlreadyConsumedError: type[Exception]

    def reserve_consumption(
        self,
        marker: Path,
        identity: JsonObject,
        *,
        reserved_at: str,
        filesystem: _DurabilityFilesystem | None = None,
    ) -> _ConsumptionCapability: ...

    def load_reserved_dataset(
        self,
        capability: _ConsumptionCapability,
        loader: Callable[[], str],
    ) -> str: ...

    def reserve_and_load(
        self,
        marker: Path,
        identity: JsonObject,
        *,
        reserved_at: str,
        loader: Callable[[], str],
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class _RecordingFilesystem:
    events: list[tuple[str, int | Path]] = field(default_factory=list)

    def open_exclusive(self, path: Path, _content: bytes) -> int:
        self.events.append(("open_file", path))
        return 101

    def open_directory(self, path: Path) -> int:
        self.events.append(("open_directory", path))
        return 202

    def fsync(self, descriptor: int) -> None:
        self.events.append(("fsync", descriptor))

    def close(self, descriptor: int) -> None:
        self.events.append(("close", descriptor))


@dataclass(frozen=True, slots=True)
class _ForgedCapability:
    marker_path: Path
    consumed: bool = False


def _reservation() -> _ReservationApi:
    try:
        module = importlib.import_module("polis.evaluation.holdout_reservation")
    except ModuleNotFoundError as error:
        raise AssertionError(
            "planned durable holdout reservation implementation is absent"
        ) from error
    if not isinstance(module, _ReservationApi):
        raise AssertionError("planned durable reservation API is incomplete")
    return module


def _identity() -> JsonObject:
    return {
        "experiment_id": "polis-a-b-one-shot-v1",
        "config_sha256": CONFIG_SHA256,
        "source_sha256": SOURCE_SHA256,
        "dataset_sha256": DATASET_SHA256,
    }


def test_reservation_exclusively_creates_privacy_safe_marker_before_loader(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "holdout.started"
    capability = _reservation().reserve_consumption(
        marker, _identity(), reserved_at="2026-08-08T20:30:00Z"
    )
    observed_at_load = marker.exists()
    loaded = _reservation().load_reserved_dataset(capability, lambda: "synthetic")

    assert observed_at_load is True
    assert loaded == "synthetic"
    assert json.loads(marker.read_text(encoding="utf-8")) == {
        **_identity(),
        "reserved_at": "2026-08-08T20:30:00Z",
    }


def test_existing_marker_permanently_denies_repeat_without_calling_loader(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "holdout.started"
    marker.write_text("partial", encoding="utf-8")
    loader_calls = 0

    def loader() -> str:
        nonlocal loader_calls
        loader_calls += 1
        return "synthetic"

    with pytest.raises(
        _reservation().HoldoutAlreadyConsumedError, match="already consumed"
    ):
        _reservation().reserve_and_load(
            marker, _identity(), reserved_at="2026-08-08T20:30:00Z", loader=loader
        )

    assert loader_calls == 0
    assert marker.read_text(encoding="utf-8") == "partial"


def test_one_capability_allows_exactly_one_dataset_load(tmp_path: Path) -> None:
    capability = _reservation().reserve_consumption(
        tmp_path / "holdout.started", _identity(), reserved_at="2026-08-08T20:30:00Z"
    )
    assert (
        _reservation().load_reserved_dataset(capability, lambda: "synthetic")
        == "synthetic"
    )

    with pytest.raises(
        _reservation().HoldoutAlreadyConsumedError, match="capability.*consumed"
    ):
        _reservation().load_reserved_dataset(capability, lambda: "second")


def test_partial_marker_and_identity_mismatch_are_never_repaired(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "holdout.started"
    marker.write_text('{"experiment_id":"wrong"}', encoding="utf-8")
    before = marker.read_bytes()

    with pytest.raises(_reservation().HoldoutAlreadyConsumedError):
        _reservation().reserve_consumption(
            marker, _identity(), reserved_at="2026-08-08T20:30:00Z"
        )

    assert marker.read_bytes() == before


def test_file_and_parent_directory_descriptors_are_each_fsynced(tmp_path: Path) -> None:
    marker = tmp_path / "holdout.started"
    filesystem = _RecordingFilesystem()

    _reservation().reserve_consumption(
        marker,
        _identity(),
        reserved_at="2026-08-08T20:30:00Z",
        filesystem=filesystem,
    )

    assert ("open_file", marker) in filesystem.events
    assert ("open_directory", tmp_path) in filesystem.events
    assert [value for action, value in filesystem.events if action == "fsync"] == [
        101,
        202,
    ]
    assert [value for action, value in filesystem.events if action == "close"] == [
        101,
        202,
    ]


def test_manual_marker_and_forged_capability_cannot_enter_loader(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "holdout.started"
    marker.write_text("synthetic marker", encoding="utf-8")
    loader_calls = 0

    def loader() -> str:
        nonlocal loader_calls
        loader_calls += 1
        return "forbidden"

    with pytest.raises(
        _reservation().HoldoutAlreadyConsumedError, match="capability.*invalid"
    ):
        _reservation().load_reserved_dataset(_ForgedCapability(marker), loader)

    assert loader_calls == 0
