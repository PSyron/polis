from __future__ import annotations

from pathlib import Path

from polis.evaluation.holdout_json import fail, object_value, string_value
from polis.evaluation.holdout_models import (
    HoldoutAdmissionError,
    HoldoutPaths,
    JsonValue,
)

CANONICAL_CONFIG_PATH = Path("experiments/a-b-one-shot/config.json")
CANONICAL_EXPERIMENT_ROOT = CANONICAL_CONFIG_PATH.parent
_PATH_NAMES = (
    "dataset",
    "merge_verification",
    "run_authorization",
    "run_authorization_signature",
    "marker",
    "raw_report",
    "normalized_report",
    "result_manifest",
)
EXPECTED_PATHS = HoldoutPaths(
    Path(".omo/sealed/a-b-one-shot-v1/cases.json"),
    Path(".omo/sealed/a-b-one-shot-v1/merge-verification.json"),
    Path(".omo/sealed/a-b-one-shot-v1/run-authorization.json"),
    Path(".omo/sealed/a-b-one-shot-v1/run-authorization.sig"),
    Path("holdout.started"),
    Path("report.json"),
    Path("normalized-report.json"),
    Path("result.manifest.json"),
)


def parse_holdout_paths(value: JsonValue) -> HoldoutPaths:
    raw = object_value(value, set(_PATH_NAMES), "paths")
    paths = HoldoutPaths(
        *(Path(string_value(raw[name], f"path {name}")) for name in _PATH_NAMES)
    )
    values = (
        paths.dataset,
        paths.merge_verification,
        paths.run_authorization,
        paths.run_authorization_signature,
        paths.marker,
        paths.raw_report,
        paths.normalized_report,
        paths.result_manifest,
    )
    if any(path.is_absolute() or ".." in path.parts for path in values):
        fail("holdout paths must be safe relative paths")
    if paths != EXPECTED_PATHS:
        fail("holdout paths must match the preregistration")
    return paths


def require_canonical_config(
    config_path: Path, *, repository_root: Path | None = None
) -> Path:
    root = repository_root or Path(__file__).resolve().parents[3]
    if Path.cwd().resolve() != root.resolve():
        raise HoldoutAdmissionError("command must run from the repository root")
    if config_path != CANONICAL_CONFIG_PATH or config_path.is_absolute():
        raise HoldoutAdmissionError(
            f"config path must be exactly {CANONICAL_CONFIG_PATH}"
        )
    current = root
    for component in config_path.parts:
        current /= component
        if current.is_symlink():
            raise HoldoutAdmissionError("canonical config path cannot contain symlinks")
    return config_path
