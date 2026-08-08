from __future__ import annotations

import math
import re
from typing import NoReturn

from polis.evaluation.holdout_json import (
    normalized_report_bytes as _normalized_report_bytes,
)
from polis.evaluation.holdout_models import (
    HoldoutPerformance as Performance,
)
from polis.evaluation.holdout_models import (
    HoldoutQuality as Quality,
)
from polis.evaluation.holdout_models import (
    HoldoutReportError,
    JsonObject,
    JsonValue,
    RawReport,
)
from polis.evaluation.holdout_report_sources import parse_source_outcomes

normalized_report_bytes = _normalized_report_bytes

_TOP = {
    "schema_id",
    "schema_version",
    "experiment_id",
    "identities",
    "quality",
    "performance",
    "environment",
    "per_source",
    "verdict",
}
_IDENTITIES = {
    "config_sha256",
    "dataset_sha256",
    "source_sha256",
    "wheel_sha256",
    "sdist_sha256",
    "lock_sha256",
}
_QUALITY = {
    "precision",
    "recall",
    "f1",
    "exact_span_accuracy",
    "exact_correction_accuracy",
    "correct_sentence_false_alarm_rate",
}
_PERFORMANCE = {"latency_ns", "throughput", "peak_rss_bytes"}
_LATENCY = {"min", "mean", "p50", "p95", "max"}
_THROUGHPUT = {"cases_per_second", "code_points_per_second"}
_ENVIRONMENT = {
    "os",
    "release",
    "machine",
    "python",
    "package",
    "morfeusz_dictionary",
    "morfeusz_notice_sha256",
}
_VERDICTS = {"pass", "fail_threshold", "insufficient_evidence", "invalid"}
_SHA256 = re.compile(r"[0-9a-f]{64}")
_RELEASE = re.compile(r"[0-9A-Za-z][0-9A-Za-z._+\-]{0,63}")
_VERSION = re.compile(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?")


def _fail(message: str) -> NoReturn:
    raise HoldoutReportError(message)


def _object(value: JsonValue, fields: set[str], name: str) -> JsonObject:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"{name} has invalid fields")
    return value


def _number(value: JsonValue, name: str) -> float:
    if type(value) not in (int, float):
        _fail(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        _fail(f"{name} must be finite")
    return number


def _count(value: JsonValue, name: str) -> int:
    if type(value) is not int or value < 0:
        _fail(f"{name} must be a non-negative integer")
    return value


def _string(value: JsonValue, name: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{name} must be a non-empty string")
    return value


def parse_raw_report(raw: JsonObject) -> RawReport:
    if set(raw) != _TOP:
        _fail("raw report has invalid fields or private case content")
    if (
        raw["schema_id"] != "polis.a-b-one-shot.raw-report"
        or raw["schema_version"] != 1
    ):
        _fail("unsupported raw report schema")
    if raw["experiment_id"] != "polis-a-b-one-shot-v1":
        _fail("experiment_id is invalid")
    identities = _object(raw["identities"], _IDENTITIES, "identities")
    for key, value in identities.items():
        if _SHA256.fullmatch(_string(value, key)) is None:
            _fail(f"{key} must be a sha256 digest")
    quality_raw = _object(raw["quality"], _QUALITY, "quality")
    quality = Quality(*(_number(quality_raw[key], key) for key in _QUALITY_ORDER))
    performance_raw = _object(raw["performance"], _PERFORMANCE, "performance")
    latency = _object(performance_raw["latency_ns"], _LATENCY, "latency")
    throughput = _object(performance_raw["throughput"], _THROUGHPUT, "throughput")
    for key, value in latency.items():
        _count(value, key)
    for key, value in throughput.items():
        _number(value, key)
    performance = Performance(
        latency, throughput, _count(performance_raw["peak_rss_bytes"], "peak_rss_bytes")
    )
    environment = _object(raw["environment"], _ENVIRONMENT, "environment")
    if environment["os"] not in {"Darwin", "Linux"}:
        _fail("os is invalid")
    if environment["machine"] not in {"arm64", "x86_64"}:
        _fail("machine is invalid")
    release = _string(environment["release"], "release")
    if _RELEASE.fullmatch(release) is None:
        _fail("release is invalid")
    for key in ("python", "package"):
        if _VERSION.fullmatch(_string(environment[key], key)) is None:
            _fail(f"{key} version is invalid")
    if environment["morfeusz_dictionary"] != "pl.sgjp":
        _fail("morfeusz_dictionary is invalid")
    if (
        _SHA256.fullmatch(
            _string(environment["morfeusz_notice_sha256"], "morfeusz notice digest")
        )
        is None
    ):
        _fail("morfeusz notice digest is invalid")
    outcomes = parse_source_outcomes(raw["per_source"])
    verdict = _string(raw["verdict"], "verdict")
    if verdict not in _VERDICTS:
        _fail("report verdict is invalid")
    return RawReport(
        "polis.a-b-one-shot.raw-report",
        1,
        "polis-a-b-one-shot-v1",
        identities,
        quality,
        performance,
        environment,
        tuple(outcomes),
        verdict,
    )


_QUALITY_ORDER = (
    "precision",
    "recall",
    "f1",
    "exact_span_accuracy",
    "exact_correction_accuracy",
    "correct_sentence_false_alarm_rate",
)
