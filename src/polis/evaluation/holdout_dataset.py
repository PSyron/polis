from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from polis.evaluation.holdout_dataset_cases import HoldoutCaseError, parse_case
from polis.evaluation.holdout_models import (
    HoldoutConfig,
    HoldoutDataset,
    JsonObject,
    JsonValue,
)


class HoldoutDatasetError(RuntimeError):
    pass


def _object(value: JsonValue, fields: set[str], label: str) -> JsonObject:
    if not isinstance(value, dict) or set(value) != fields:
        raise HoldoutDatasetError(f"{label} must contain exactly the required fields")
    return value


def load_holdout_dataset(path: Path, config: HoldoutConfig) -> HoldoutDataset:
    try:
        with path.open("rb") as source:
            metadata = os.fstat(source.fileno())
            raw_bytes = source.read()
        mode = f"{stat.S_IMODE(metadata.st_mode):04o}"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HoldoutDatasetError("sealed dataset is unavailable or invalid") from error
    return load_holdout_dataset_bytes(raw_bytes, mode, config)


def load_holdout_dataset_bytes(
    raw_bytes: bytes, mode: str, config: HoldoutConfig
) -> HoldoutDataset:
    try:
        raw_value = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HoldoutDatasetError("sealed dataset is unavailable or invalid") from error
    if len(raw_bytes) != config.dataset.size_bytes or mode != config.dataset.mode:
        raise HoldoutDatasetError("sealed dataset size or mode is invalid")
    raw = _object(
        raw_value,
        {"schema_id", "schema_version", "id", "language", "license", "cases"},
        "holdout dataset",
    )
    try:
        canonical = (
            json.dumps(
                raw,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode()
    except ValueError as error:
        raise HoldoutDatasetError("sealed dataset contains non-finite data") from error
    if raw_bytes != canonical:
        raise HoldoutDatasetError("sealed dataset bytes are not canonical")
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if digest != config.dataset.sha256:
        raise HoldoutDatasetError("sealed dataset_sha256 mismatch")
    if (
        raw["schema_id"],
        raw["schema_version"],
        raw["id"],
        raw["language"],
        raw["license"],
    ) != ("polis.a-b-one-shot.dataset", 1, config.experiment_id, "pl", "CC0-1.0"):
        raise HoldoutDatasetError("sealed dataset root identity is invalid")
    source_categories = {
        item.source: item.category for item in config.source_identities
    }
    values = raw["cases"]
    if not isinstance(values, list) or len(values) != config.dataset.case_count:
        raise HoldoutDatasetError("sealed dataset case count is invalid")
    seen_ids: set[str] = set()
    try:
        cases = tuple(
            parse_case(value, source_categories=source_categories, seen_ids=seen_ids)
            for value in values
        )
    except HoldoutCaseError as error:
        raise HoldoutDatasetError(str(error)) from error
    covered = {target for case in cases for target in case.targets}
    if covered != set(source_categories):
        raise HoldoutDatasetError("sealed dataset does not cover all sources")
    return HoldoutDataset(config.experiment_id, cases, digest)
