from __future__ import annotations

import hashlib
from pathlib import Path

from tests.calibration_test_helpers import canonical_bytes, synthetic_config

from polis.evaluation.calibration_contract import parse_calibration_config
from polis.evaluation.calibration_paths import (
    CANONICAL_CALIBRATION_CONFIG,
    require_canonical_calibration_config,
)
from polis.evaluation.calibration_sources import SOURCE_ROWS, SOURCE_SNAPSHOT_SHA256

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / CANONICAL_CALIBRATION_CONFIG


def test_canonical_calibration_config_is_materialized_and_contract_bound() -> None:
    assert CONFIG_PATH.is_file()
    raw = CONFIG_PATH.read_bytes()
    assert raw == canonical_bytes(synthetic_config())
    assert hashlib.sha256(raw).hexdigest() == (
        "8375538fe94c6dfc777d95a68f70e9d8eaae05d039b34e5f406bce63c5d32d93"
    )
    config = parse_calibration_config(raw)
    assert config.experiment_id == "polis-a-b-qualification-v2-v1"
    assert config.dataset_id == "polis-a-b-calibration-v2-v1"
    assert config.source_rows == SOURCE_ROWS
    assert len(config.source_rows) == 20
    assert config.paths.dataset == Path(".omo/sealed/a-b-calibration-v2-v1/cases.json")
    assert config.paths.manifest == Path(
        "experiments/a-b-qualification-v2/calibration.dataset.manifest.json"
    )
    assert require_canonical_calibration_config(CANONICAL_CALIBRATION_CONFIG) == (
        CANONICAL_CALIBRATION_CONFIG
    )
    # Frozen qualification cohort digest remains the immutable 20-row identity.
    assert SOURCE_SNAPSHOT_SHA256 == (
        "92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92"
    )
