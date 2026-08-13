from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from polis.evaluation.quality_dataset import (
    QualityDatasetVersion,
    as_evaluation_dataset,
    load_quality_dataset,
    quality_dataset_paths,
)
from polis.evaluation.quality_protocol import (
    InstallationProfile,
    RunIdentity,
    RunProfile,
    run_quality_protocol,
)
from polis.evaluation.quality_report import (
    QualityReportError,
    load_quality_report,
    quality_report_json,
)

ROOT = Path(__file__).resolve().parents[1]


def test_v2_report_binds_source_profile_and_contains_no_case_plaintext(
    tmp_path: Path,
) -> None:
    # Given
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    _, manifest_path = quality_dataset_paths(QualityDatasetVersion.V2)
    ticks = iter(range(1, len(dataset.cases) * 4 + 1))
    identity = RunIdentity(
        analyzer="Analyzer(AnalyzerConfig())",
        artifact_sha256="a" * 64,
        package_version="0.2.0",
        python_version="3.14.3",
        platform_system="Darwin",
        platform_release="25.5.0",
        platform_machine="arm64",
        dataset_schema_id=dataset.schema_id,
        dataset_schema_version=dataset.schema_version,
        manifest_schema_id="polis.quality-development-manifest",
        manifest_schema_version=2,
        manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        source_sha="0840e1e432f4962f74b2535fc00fa84553617131",
        profile=RunProfile(
            id=InstallationProfile.DEFAULT,
            morphology_provider=None,
            planned_morphology_source_semantics="provider-absent-abstention",
            planned_non_morphology_source_semantics="sources-not-implemented",
        ),
    )
    result = run_quality_protocol(
        dataset=as_evaluation_dataset(dataset),
        analyzer=lambda _text: (),
        run_identity=identity,
        warmup_repetitions=0,
        measured_repetitions=2,
        clock_ns=lambda: next(ticks),
        rss_probe=lambda: 1024,
    )

    # When
    encoded = quality_report_json(result)
    report_path = tmp_path / "baseline-v2.json"
    report_path.write_text(encoded, encoding="utf-8")
    report = load_quality_report(report_path)
    payload = json.loads(encoded)

    # Then
    assert payload["schema_version"] == 2
    assert payload["source"] == {"git_sha": "0840e1e432f4962f74b2535fc00fa84553617131"}
    assert payload["profile"]["id"] == "default"
    assert payload["profile"]["morphology_provider"] is None
    assert report.run_identity.source_sha == identity.source_sha
    forbidden = {"text", "gold", "original", "suggestion", "pii", "path"}
    assert forbidden.isdisjoint(_all_keys(payload))


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {key for key in value if isinstance(key, str)} | {
            key for item in value.values() for key in _all_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def test_committed_v2_reports_bind_one_wheel_and_both_profiles() -> None:
    # Given
    paths = (
        ROOT / "docs/quality-baseline-v2-default.json",
        ROOT / "docs/quality-baseline-v2-morphology.json",
    )

    # When
    reports = tuple(load_quality_report(path) for path in paths)

    # Then
    assert {
        report.run_identity.profile.id
        for report in reports
        if report.run_identity.profile
    } == {
        InstallationProfile.DEFAULT,
        InstallationProfile.MORPHOLOGY,
    }
    assert {report.artifact_sha256 for report in reports} == {
        "51e865182de68914584a2214d3d1db4a869ed3aeb7f1b273082ae3006dc47ad3"
    }
    assert {report.run_identity.source_sha for report in reports} == {
        "c2f1dbfec00d46cb6286caaba958ae088eeb0f53"
    }
    assert all(report.dataset_cases == 92 for report in reports)
    assert all(len(set(report.repetition_hashes)) == 1 for report in reports)


def test_v2_dataset_rejects_v1_report_identity(tmp_path: Path) -> None:
    # Given
    payload = json.loads(
        (ROOT / "docs/quality-baseline-v2-default.json").read_text(encoding="utf-8")
    )
    payload["schema_version"] = 1
    del payload["source"]
    del payload["profile"]
    report_path = tmp_path / "v2-dataset-v1-report.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    # When / Then
    with pytest.raises(QualityReportError, match="schema version mismatch"):
        load_quality_report(report_path)


def test_v2_report_rejects_v1_dataset_identity(tmp_path: Path) -> None:
    # Given
    payload = json.loads(
        (ROOT / "docs/quality-baseline-v1.json").read_text(encoding="utf-8")
    )
    v2_payload = json.loads(
        (ROOT / "docs/quality-baseline-v2-default.json").read_text(encoding="utf-8")
    )
    payload["schema_version"] = 2
    payload["source"] = v2_payload["source"]
    payload["profile"] = v2_payload["profile"]
    report_path = tmp_path / "v1-dataset-v2-report.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    # When / Then
    with pytest.raises(QualityReportError, match="schema version mismatch"):
        load_quality_report(report_path)


def test_v1_report_rejects_source_and_profile_identity(tmp_path: Path) -> None:
    # Given
    payload = json.loads(
        (ROOT / "docs/quality-baseline-v1.json").read_text(encoding="utf-8")
    )
    v2_payload = json.loads(
        (ROOT / "docs/quality-baseline-v2-default.json").read_text(encoding="utf-8")
    )
    payload["source"] = v2_payload["source"]
    payload["profile"] = v2_payload["profile"]
    report_path = tmp_path / "v1-report-with-v2-identity.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    # When / Then
    with pytest.raises(QualityReportError, match="unexpected fields"):
        load_quality_report(report_path)
