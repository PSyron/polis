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

    if result.run_identity.analyzer != _ANALYZER:
        raise QualityReportError("quality report analyzer must use the default runtime")
    validate_quality_protocol_measurements(result)
    if (
        result.dataset_id != result.baseline.dataset_id
        or result.dataset_sha256 != result.baseline.dataset_hash
        or result.run_identity.dataset_schema_version
        != result.baseline.dataset_schema_version
    ):
        raise QualityReportError("active dataset identity mismatch")
    payload = _report_payload(result)
    _validate_active_dataset_identity(payload["dataset"])
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_quality_report(
    result: QualityProtocolResult,
    path: Path,
    *,
    replace: bool = False,
) -> None:
    """Write a canonical report, refusing to replace evidence by default."""

    mode = "w" if replace else "x"
    with path.open(mode, encoding="utf-8", newline="\n") as stream:
        stream.write(quality_report_json(result))


def load_quality_report(path: Path) -> QualityReport:
    """Parse a baseline report and reject every unknown or malformed field."""

    root = _load_json_object(path, "quality report")
    schema_version = _integer(root, "schema_version", "quality report")
    if schema_version not in {1, 2, 3}:
        raise QualityReportError("quality report schema_version must be 1, 2, or 3")
    root_fields: set[str] = set(
        "schema_id schema_version analyzer artifact dataset "
        "quality performance environment reproducibility".split()
    )
    if schema_version in {2, 3}:
        root_fields.update({"source", "profile"})
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


def _report_payload(result: QualityProtocolResult) -> JsonObject:
    identity = result.run_identity
    counts = result.baseline.aggregate
    uses_profile = identity.dataset_schema_version in {2, 3}
    has_profile_identity = (
        identity.source_sha is not None and identity.profile is not None
    )
    if uses_profile != has_profile_identity:
        raise QualityReportError(
            "v2/v3 quality report requires source and profile identity"
        )
    payload: JsonObject = {
        "schema_id": _REPORT_SCHEMA_ID,
        "schema_version": identity.dataset_schema_version if uses_profile else 1,
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
