"""Canonical serialization and parsing of measured quality baselines."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Final

from polis.evaluation.quality_dataset import (
    QualityDatasetVersion,
    as_evaluation_dataset,
    load_quality_dataset,
    quality_dataset_paths,
)
from polis.evaluation.quality_protocol import (
    InstallationProfile,
    MorphologyProviderIdentity,
    QualityProtocolResult,
    ResourceMetrics,
    RunIdentity,
    RunProfile,
)
from polis.evaluation.quality_report_models import (
    JsonObject,
    JsonValue,
    QualityReport,
    QualityReportError,
)
from polis.evaluation.quality_report_validation import (
    _exact,
    _integer,
    _load_json_object,
    _nested,
    _parse_counts,
    _parse_latency,
    _parse_throughput,
    _quality_ratio,
    _require_object,
    _sha,
    _string,
    _string_tuple,
    _validated_sha,
    validate_quality_protocol_measurements,
    validate_quality_report_measurements,
)

_REPORT_SCHEMA_ID: Final = "polis.quality-baseline"
_ANALYZER: Final = "Analyzer(AnalyzerConfig())"
_SOURCE_SHA: Final = re.compile(r"[0-9a-f]{40}")


def quality_report_json(result: QualityProtocolResult) -> str:
    """Serialize a protocol result as canonical UTF-8-compatible JSON text."""

    return _quality_report_json(result, result_schema=False)


def quality_result_json(result: QualityProtocolResult) -> str:
    """Serialize a post-change result using the repository-only result schema."""

    return _quality_report_json(result, result_schema=True)


def _quality_report_json(result: QualityProtocolResult, *, result_schema: bool) -> str:
    if result.run_identity.analyzer != _ANALYZER:
        raise QualityReportError("quality report analyzer must use the default runtime")
    if result.run_identity.dataset_schema_version == 4:
        if result.run_identity.source_snapshot is None:
            raise QualityReportError("quality v4 source snapshot is required")
        if result.v4_diagnostics is None:
            raise QualityReportError("quality v4 diagnostics are required")
        if result.run_identity.artifact_sha256 == "0" * 64:
            raise QualityReportError(
                "quality v4 artifact hash must not be a placeholder"
            )
    validate_quality_protocol_measurements(result)
    if (
        result.dataset_id != result.baseline.dataset_id
        or result.dataset_sha256 != result.baseline.dataset_hash
        or result.run_identity.dataset_schema_version
        != result.baseline.dataset_schema_version
    ):
        raise QualityReportError("active dataset identity mismatch")
    payload = _report_payload(result, result_schema=result_schema)
    _validate_active_dataset_identity(payload["dataset"])
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_quality_report(
    result: QualityProtocolResult,
    path: Path,
    *,
    replace: bool = False,
) -> None:
    """Write a canonical baseline, refusing to replace evidence by default."""

    _write_quality_artifact(result, path, replace=replace, result_schema=False)


def write_quality_result(
    result: QualityProtocolResult,
    path: Path,
    *,
    replace: bool = False,
) -> None:
    """Write a canonical repository-only post-change result."""

    _write_quality_artifact(result, path, replace=replace, result_schema=True)


def _write_quality_artifact(
    result: QualityProtocolResult,
    path: Path,
    *,
    replace: bool,
    result_schema: bool,
) -> None:
    mode = "w" if replace else "x"
    with path.open(mode, encoding="utf-8", newline="\n") as stream:
        stream.write(_quality_report_json(result, result_schema=result_schema))


def load_quality_report(path: Path) -> QualityReport:
    """Parse a baseline report and reject every unknown or malformed field."""

    root = _load_json_object(path, "quality report")
    schema_version = _integer(root, "schema_version", "quality report")
    if schema_version not in {1, 2, 3, 4}:
        raise QualityReportError("quality report schema_version must be 1, 2, 3, or 4")
    root_fields: set[str] = set(
        "schema_id schema_version analyzer artifact dataset "
        "quality performance environment reproducibility".split()
    )
    if schema_version in {2, 3, 4}:
        root_fields.update({"source", "profile"})
    if schema_version == 4:
        root_fields.update({"diagnostics", "source_snapshot"})
    _exact(
        root,
        root_fields,
        "quality report",
    )
    if _string(root, "schema_id", "quality report") != _REPORT_SCHEMA_ID:
        raise QualityReportError("quality report schema_id mismatch")
    analyzer = _string(root, "analyzer", "quality report")
    if analyzer != _ANALYZER:
        raise QualityReportError("quality report analyzer must use the default runtime")
    artifact = _nested(root, "artifact", {"sha256"})
    dataset = _nested(
        root,
        "dataset",
        set("id schema_id schema_version sha256 cases source manifest".split()),
    )
    dataset_schema_version = _integer(dataset, "schema_version", "dataset")
    if dataset_schema_version != schema_version:
        raise QualityReportError("quality report and dataset schema version mismatch")
    manifest = _nested(
        dataset, "manifest", set("schema_id schema_version sha256".split())
    )
    quality = _nested(
        root,
        "quality",
        set(
            "precision recall f1 span_accuracy correction_accuracy "
            "false_alarm_rate counts".split()
        ),
    )
    performance = _nested(
        root, "performance", set("latency_ns throughput peak_rss_bytes".split())
    )
    environment = _nested(
        root,
        "environment",
        set(
            "package_version python_version platform_system platform_release "
            "platform_machine".split()
        ),
    )
    reproducibility = _nested(
        root,
        "reproducibility",
        set(
            "warmup_repetitions measured_repetitions stable_repetitions "
            "repetition_hashes".split()
        ),
    )
    hashes = _string_tuple(reproducibility, "repetition_hashes")
    measured = _integer(reproducibility, "measured_repetitions", "reproducibility")
    stable = _integer(reproducibility, "stable_repetitions", "reproducibility")
    counts = _parse_counts(quality)
    source_sha, profile = _parse_v2_identity(root, schema_version)
    source_snapshot = _parse_source_snapshot(root, schema_version)
    diagnostics = root.get("diagnostics")
    if schema_version == 4:
        if not isinstance(diagnostics, dict):
            raise QualityReportError("quality v4 report diagnostics must be an object")
        _validate_v4_diagnostics(
            diagnostics,
            dataset_cases=_integer(dataset, "cases", "dataset"),
            source_snapshot=source_snapshot,
        )
    report = QualityReport(
        run_identity=RunIdentity(
            analyzer=analyzer,
            artifact_sha256=_sha(artifact, "sha256", "artifact"),
            package_version=_string(environment, "package_version", "environment"),
            python_version=_string(environment, "python_version", "environment"),
            platform_system=_string(environment, "platform_system", "environment"),
            platform_release=_string(environment, "platform_release", "environment"),
            platform_machine=_string(environment, "platform_machine", "environment"),
            dataset_schema_id=_string(dataset, "schema_id", "dataset"),
            dataset_schema_version=dataset_schema_version,
            manifest_schema_id=_string(manifest, "schema_id", "manifest"),
            manifest_schema_version=_integer(manifest, "schema_version", "manifest"),
            manifest_sha256=_sha(manifest, "sha256", "manifest"),
            source_sha=source_sha,
            profile=profile,
            source_snapshot=source_snapshot,
        ),
        dataset_id=_string(dataset, "id", "dataset"),
        dataset_sha256=_sha(dataset, "sha256", "dataset"),
        dataset_cases=_integer(dataset, "cases", "dataset"),
        dataset_source=_string(dataset, "source", "dataset"),
        counts=counts,
        quality_precision=_quality_ratio(
            quality, "precision", counts.exact_edit_precision
        ),
        quality_recall=_quality_ratio(quality, "recall", counts.exact_edit_recall),
        quality_f1=_quality_ratio(quality, "f1", counts.exact_edit_f1),
        quality_span_accuracy=_quality_ratio(
            quality, "span_accuracy", counts.span_accuracy
        ),
        quality_correction_accuracy=_quality_ratio(
            quality, "correction_accuracy", counts.correction_accuracy
        ),
        quality_false_alarm_rate=_quality_ratio(
            quality, "false_alarm_rate", counts.correct_sentence_false_alarm_rate
        ),
        warmup_repetitions=_integer(
            reproducibility, "warmup_repetitions", "reproducibility"
        ),
        measured_repetitions=measured,
        repetition_hashes=tuple(
            _validated_sha(value, "repetition hash") for value in hashes
        ),
        latency=_parse_latency(performance),
        throughput=_parse_throughput(performance),
        resources=ResourceMetrics(
            peak_rss_bytes=_integer(performance, "peak_rss_bytes", "performance")
        ),
        diagnostics=diagnostics if schema_version == 4 else None,
        source_snapshot=source_snapshot,
    )
    validate_quality_report_measurements(report, stable)
    _validate_active_dataset_identity(dataset)
    return report


def baseline_file_sha256(path: Path) -> str:
    """Hash exact report bytes without newline or Unicode normalization."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_active_dataset_identity(value: JsonValue) -> None:
    dataset = _require_object(value, "dataset")
    manifest = _require_object(dataset["manifest"], "manifest")
    schema_version = _integer(dataset, "schema_version", "dataset")
    try:
        version = QualityDatasetVersion(f"v{schema_version}")
    except ValueError:
        raise QualityReportError("active dataset identity mismatch") from None
    _, manifest_path = quality_dataset_paths(version)
    active = load_quality_dataset(version=version)
    evaluated = as_evaluation_dataset(active)
    expected_dataset: JsonObject = {
        "id": active.id,
        "schema_id": active.schema_id,
        "schema_version": active.schema_version,
        "sha256": active.canonical_sha256,
        "cases": len(active.cases),
        "source": evaluated.source,
    }
    expected_manifest: JsonObject = {
        "schema_id": "polis.quality-development-manifest",
        "schema_version": schema_version,
        "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    if any(dataset.get(key) != item for key, item in expected_dataset.items()) or any(
        manifest.get(key) != item for key, item in expected_manifest.items()
    ):
        raise QualityReportError("active dataset identity mismatch")


def _report_payload(
    result: QualityProtocolResult, *, result_schema: bool = False
) -> JsonObject:
    identity = result.run_identity
    counts = result.baseline.aggregate
    uses_profile = identity.dataset_schema_version in {2, 3, 4}
    has_profile_identity = (
        identity.source_sha is not None and identity.profile is not None
    )
    if uses_profile != has_profile_identity:
        raise QualityReportError(
            "v2/v3 quality report requires source and profile identity"
        )
    payload: JsonObject = {
        "schema_id": "polis.quality-result" if result_schema else _REPORT_SCHEMA_ID,
        "schema_version": 1
        if result_schema
        else (identity.dataset_schema_version if uses_profile else 1),
        "analyzer": identity.analyzer,
        "artifact": {"sha256": identity.artifact_sha256},
        "dataset": {
            "id": result.dataset_id,
            "schema_id": identity.dataset_schema_id,
            "schema_version": identity.dataset_schema_version,
            "sha256": result.dataset_sha256,
            "cases": result.baseline.dataset_cases,
            "source": result.baseline.dataset_source,
            "manifest": {
                "schema_id": identity.manifest_schema_id,
                "schema_version": identity.manifest_schema_version,
                "sha256": identity.manifest_sha256,
            },
        },
        "quality": {
            "precision": counts.exact_edit_precision,
            "recall": counts.exact_edit_recall,
            "f1": counts.exact_edit_f1,
            "span_accuracy": counts.span_accuracy,
            "correction_accuracy": counts.correction_accuracy,
            "false_alarm_rate": counts.correct_sentence_false_alarm_rate,
            "counts": asdict(counts),
        },
        "performance": {
            "latency_ns": {
                key.removesuffix("_ns"): value
                for key, value in asdict(result.latency).items()
            },
            "throughput": asdict(result.throughput),
            "peak_rss_bytes": result.resources.peak_rss_bytes,
        },
        "environment": {
            "package_version": identity.package_version,
            "python_version": identity.python_version,
            "platform_system": identity.platform_system,
            "platform_release": identity.platform_release,
            "platform_machine": identity.platform_machine,
        },
        "reproducibility": {
            "warmup_repetitions": result.warmup_repetitions,
            "measured_repetitions": result.measured_repetitions,
            "stable_repetitions": len(result.repetition_hashes),
            "repetition_hashes": list(result.repetition_hashes),
        },
    }
    if identity.dataset_schema_version == 4:
        if result_schema:
            # Result artifacts are explicitly marked at the root while retaining
            # the same v4 dataset and diagnostic contract.
            pass
        diagnostics = result.v4_diagnostics
        if diagnostics is None:
            raise QualityReportError("quality v4 report requires diagnostics")
        payload["diagnostics"] = diagnostics
        payload["source_snapshot"] = list(identity.source_snapshot or ())
    if uses_profile:
        assert identity.source_sha is not None
        assert identity.profile is not None
        if _SOURCE_SHA.fullmatch(identity.source_sha) is None:
            raise QualityReportError(
                "quality report source git_sha must be a commit SHA"
            )
        payload["source"] = {"git_sha": identity.source_sha}
        payload["profile"] = _profile_payload(identity.profile)
    return payload


def _parse_source_snapshot(
    root: JsonObject, schema_version: int
) -> tuple[dict[str, str], ...] | None:
    if schema_version != 4:
        return None
    raw = root.get("source_snapshot")
    if not isinstance(raw, list) or len(raw) != 59:
        raise QualityReportError("quality v4 source snapshot must contain 59 entries")
    result: list[dict[str, str]] = []
    for item in raw:
        if (
            not isinstance(item, dict)
            or set(item) != {"source", "operation", "behavior_version"}
            or not all(isinstance(value, str) for value in item.values())
        ):
            raise QualityReportError("quality v4 source snapshot entry is malformed")
        result.append({key: str(item[key]) for key in item})
    if len({item["source"] for item in result}) != 59:
        raise QualityReportError("quality v4 source snapshot has duplicate sources")
    return tuple(result)


def _validate_v4_diagnostics(
    diagnostics: dict[str, object],
    *,
    dataset_cases: int,
    source_snapshot: tuple[dict[str, str], ...] | None,
) -> None:
    required = {
        "aggregate",
        "category",
        "shape_strata",
        "category_cases",
        "stratum_cases",
        "source",
        "controls",
    }
    if set(diagnostics) != required:
        raise QualityReportError("quality v4 diagnostics fields mismatch")
    categories = {"agreement", "inflection", "punctuation", "spelling", "syntax"}
    category = diagnostics["category"]
    if not isinstance(category, dict) or set(category) != categories:
        raise QualityReportError("quality v4 diagnostics category coverage mismatch")
    shapes = diagnostics["shape_strata"]
    if not isinstance(shapes, dict) or set(shapes) != categories:
        raise QualityReportError("quality v4 diagnostics category stratum mismatch")
    required_shapes = {
        "simple-local",
        "sentence-internal",
        "multi-sentence",
        "repeated-occurrence",
        "unicode-and-case",
        "quotation-or-literal",
        "conflict-or-abstention",
    }
    for name, values in shapes.items():
        if not isinstance(values, dict) or set(values) != required_shapes:
            raise QualityReportError(
                f"quality v4 missing required shape stratum: {name}"
            )
    source = diagnostics["source"]
    if not isinstance(source, list) or len(source) != 59:
        raise QualityReportError(
            "quality v4 diagnostics source rows must contain 59 entries"
        )
    if any(
        not isinstance(row, dict)
        or set(row)
        != {
            "source",
            "category",
            "status",
            "operation",
            "behavior_version",
            "profile",
            "predicted_count",
            "expected_count",
            "exact_match_count",
            "false_positive_count",
            "false_negative_count",
            "case_ids",
        }
        for row in source
    ):
        raise QualityReportError("quality v4 diagnostics source row is malformed")
    if len({row["source"] for row in source if isinstance(row, dict)}) != 59:
        raise QualityReportError("quality v4 diagnostics source rows are not unique")
    if source_snapshot is None or [
        row["source"] for row in source if isinstance(row, dict)
    ] != [item["source"] for item in source_snapshot]:
        raise QualityReportError("quality v4 diagnostics source order mismatch")
    for row in source:
        if not isinstance(row, dict):
            raise QualityReportError("quality v4 diagnostics source row is malformed")
        if row["status"] not in {"measured", "abstained", "control", "unmeasured"}:
            raise QualityReportError("quality v4 diagnostics source status is invalid")
        if not isinstance(row["category"], str) or not row["category"]:
            raise QualityReportError(
                "quality v4 diagnostics source category is invalid"
            )
        if not isinstance(row["profile"], str) or not row["profile"]:
            raise QualityReportError("quality v4 diagnostics source profile is invalid")
        if not isinstance(row["case_ids"], list) or not all(
            isinstance(case_id, str) and case_id for case_id in row["case_ids"]
        ):
            raise QualityReportError(
                "quality v4 diagnostics source case_ids are invalid"
            )
        for field in (
            "predicted_count",
            "expected_count",
            "exact_match_count",
            "false_positive_count",
            "false_negative_count",
        ):
            if (
                not isinstance(row[field], int)
                or isinstance(row[field], bool)
                or row[field] < 0
            ):
                raise QualityReportError(
                    "quality v4 diagnostics source counts are invalid"
                )
    controls = diagnostics["controls"]
    if not isinstance(controls, dict) or set(controls) != {"conflict", "abstention"}:
        raise QualityReportError("quality v4 diagnostics controls mismatch")
    category_cases = diagnostics["category_cases"]
    stratum_cases = diagnostics["stratum_cases"]
    if not isinstance(category_cases, dict) or set(category_cases) != categories:
        raise QualityReportError("quality v4 category case coverage mismatch")
    if not isinstance(stratum_cases, dict) or set(stratum_cases) != categories:
        raise QualityReportError("quality v4 stratum case coverage mismatch")
    category_case_total = 0
    for name in categories:
        category_value = category_cases[name]
        if not isinstance(category_value, dict) or set(category_value) != {
            "cases",
            "eligible_cases",
            "excluded_cases",
        }:
            raise QualityReportError("quality v4 category case counts are malformed")
        if any(
            not isinstance(category_value[field], int)
            or isinstance(category_value[field], bool)
            or category_value[field] < 0
            for field in category_value
        ):
            raise QualityReportError("quality v4 category case counts are invalid")
        if (
            category_value["eligible_cases"] + category_value["excluded_cases"]
            != category_value["cases"]
        ):
            raise QualityReportError("quality v4 category case arithmetic mismatch")
        category_case_total += category_value["cases"]
        if (
            not isinstance(stratum_cases[name], dict)
            or set(stratum_cases[name]) != required_shapes
        ):
            raise QualityReportError("quality v4 stratum case strata are malformed")
        for shape in required_shapes:
            shape_value = stratum_cases[name][shape]
            if not isinstance(shape_value, dict) or set(shape_value) != {
                "cases",
                "eligible_cases",
                "excluded_cases",
            }:
                raise QualityReportError("quality v4 stratum case counts are malformed")
            if (
                shape_value["eligible_cases"] + shape_value["excluded_cases"]
                != shape_value["cases"]
            ):
                raise QualityReportError("quality v4 stratum case arithmetic mismatch")
    if category_case_total != 124 - 4:
        raise QualityReportError("quality v4 diagnostics denominator mismatch")


def _profile_payload(profile: RunProfile) -> JsonObject:
    provider: JsonValue = None
    if profile.morphology_provider is not None:
        provider = asdict(profile.morphology_provider)
    return {
        "id": profile.id.value,
        "morphology_provider": provider,
        "planned_morphology_source_semantics": (
            profile.planned_morphology_source_semantics
        ),
        "planned_non_morphology_source_semantics": (
            profile.planned_non_morphology_source_semantics
        ),
    }


def _parse_v2_identity(
    root: JsonObject, schema_version: int
) -> tuple[str | None, RunProfile | None]:
    if schema_version == 1:
        return None, None
    source = _nested(root, "source", {"git_sha"})
    source_sha = _string(source, "git_sha", "source")
    if _SOURCE_SHA.fullmatch(source_sha) is None:
        raise QualityReportError("quality report source git_sha must be a commit SHA")
    raw_profile = _nested(
        root,
        "profile",
        {
            "id",
            "morphology_provider",
            "planned_morphology_source_semantics",
            "planned_non_morphology_source_semantics",
        },
    )
    try:
        profile_id = InstallationProfile(_string(raw_profile, "id", "profile"))
    except ValueError:
        raise QualityReportError("quality report profile id is unsupported") from None
    raw_provider = raw_profile["morphology_provider"]
    provider: MorphologyProviderIdentity | None
    if raw_provider is None:
        provider = None
    else:
        parsed_provider = _require_object(raw_provider, "morphology_provider")
        _exact(
            parsed_provider,
            {
                "provider",
                "package_version",
                "dictionary_id",
                "dictionary_notice_sha256",
            },
            "morphology_provider",
        )
        provider = MorphologyProviderIdentity(
            provider=_string(parsed_provider, "provider", "morphology_provider"),
            package_version=_string(
                parsed_provider, "package_version", "morphology_provider"
            ),
            dictionary_id=_string(
                parsed_provider, "dictionary_id", "morphology_provider"
            ),
            dictionary_notice_sha256=_sha(
                parsed_provider, "dictionary_notice_sha256", "morphology_provider"
            ),
        )
    profile = RunProfile(
        id=profile_id,
        morphology_provider=provider,
        planned_morphology_source_semantics=_string(
            raw_profile, "planned_morphology_source_semantics", "profile"
        ),
        planned_non_morphology_source_semantics=_string(
            raw_profile, "planned_non_morphology_source_semantics", "profile"
        ),
    )
    _validate_profile(profile)
    return source_sha, profile


def _validate_profile(profile: RunProfile) -> None:
    if profile.id is InstallationProfile.DEFAULT:
        expected = (
            None,
            "provider-absent-abstention",
            "sources-not-implemented",
        )
    else:
        expected = (
            MorphologyProviderIdentity(
                provider="morfeusz2",
                package_version="1.99.15",
                dictionary_id="pl.sgjp.sgjp-2026.06.01",
                dictionary_notice_sha256=(
                    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
                ),
            ),
            "qualified-provider-exercised-sources-not-implemented",
            "sources-not-implemented",
        )
    actual = (
        profile.morphology_provider,
        profile.planned_morphology_source_semantics,
        profile.planned_non_morphology_source_semantics,
    )
    if actual != expected:
        raise QualityReportError("quality report profile identity mismatch")
