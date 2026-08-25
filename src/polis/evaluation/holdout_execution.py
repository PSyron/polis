from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from polis import Analyzer, AnalyzerConfig, Finding
from polis.evaluation.holdout_admission import (
    ExternalAdmission,
    HoldoutAdmissionError,
    load_external_admission,
)
from polis.evaluation.holdout_attestations import metadata_bytes
from polis.evaluation.holdout_contract import parse_holdout_config
from polis.evaluation.holdout_dataset import (
    HoldoutDatasetError,
    load_holdout_dataset_bytes,
)
from polis.evaluation.holdout_manifest import parse_dataset_manifest
from polis.evaluation.holdout_models import HoldoutConfig, JsonObject
from polis.evaluation.holdout_paths import require_canonical_config
from polis.evaluation.holdout_report import (
    RawReport,
    normalized_report_bytes,
    parse_raw_report,
)
from polis.evaluation.holdout_scoring import production_report
from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace
from polis.evaluation.quality_protocol import peak_rss_bytes


def _write_results(
    workspace: SecureHoldoutWorkspace,
    marker_name: str,
    config: HoldoutConfig,
    admission: ExternalAdmission,
    raw: JsonObject,
    parsed: RawReport,
) -> None:
    raw_bytes = (
        json.dumps(
            raw,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()
    normalized_bytes = normalized_report_bytes(parsed)
    workspace.create_output(config.paths.raw_report.name, raw_bytes)
    workspace.create_output(config.paths.normalized_report.name, normalized_bytes)
    result: JsonObject = {
        "schema_id": "polis.a-b-one-shot.result-manifest",
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "evaluated_source_sha": admission.evidence.merge_commit,
        "config_sha256": admission.evidence.config_sha256,
        "dataset_sha256": admission.evidence.dataset_sha256,
        "source_sha256": admission.evidence.source_sha256,
        "verification_payload_sha256": admission.evidence.verification_payload_sha256,
        "marker_sha256": hashlib.sha256(workspace.read_output(marker_name)).hexdigest(),
        "raw_report_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "normalized_report_sha256": hashlib.sha256(normalized_bytes).hexdigest(),
        "verdict": parsed.verdict,
    }
    result_bytes = (
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()
    workspace.create_output(config.paths.result_manifest.name, result_bytes)


def run_from_config(
    config_path: Path,
    *,
    repository_root: Path | None = None,
) -> int:
    canonical = require_canonical_config(config_path, repository_root=repository_root)
    root = repository_root or Path(__file__).resolve().parents[3]
    workspace = SecureHoldoutWorkspace.open(root)
    try:
        return _run_open_workspace(workspace, canonical)
    finally:
        workspace.close()


def _run_open_workspace(
    workspace: SecureHoldoutWorkspace,
    config_path: Path,
) -> int:
    config_document = metadata_bytes(workspace.read_config(), str(config_path))
    config = parse_holdout_config(config_document)
    manifest = metadata_bytes(workspace.read_manifest(), "dataset.manifest.json")
    parse_dataset_manifest(manifest, config)
    workspace.bind_approved_dataset_identity()

    def load_secure_metadata(path: Path) -> JsonObject:
        return metadata_bytes(workspace.read_evidence(path.name), path.name)

    def load_secure_evidence(path: Path) -> bytes:
        content: bytes = workspace.read_evidence(path.name)
        return content

    admission = load_external_admission(
        config_document,
        config,
        load_metadata=load_secure_metadata,
        load_evidence=load_secure_evidence,
    )
    if any(
        workspace.output_exists(path.name)
        for path in (
            config.paths.raw_report,
            config.paths.normalized_report,
            config.paths.result_manifest,
        )
    ):
        raise HoldoutAdmissionError("holdout output already exists")
    identity: JsonObject = {
        "experiment_id": config.experiment_id,
        "config_sha256": admission.evidence.config_sha256,
        "source_sha256": admission.evidence.source_sha256,
        "dataset_sha256": admission.evidence.dataset_sha256,
    }
    capability = workspace.reserve_dataset(
        identity,
        reserved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    try:
        secure_dataset = workspace.read_dataset(capability)
        dataset = load_holdout_dataset_bytes(
            secure_dataset.content, secure_dataset.mode, config
        )
    except HoldoutDatasetError as error:
        raise HoldoutAdmissionError(str(error)) from error
    analyzer = Analyzer(AnalyzerConfig())
    for _ in range(config.warmup_repetitions):
        for case in dataset.cases:
            analyzer.analyze(case.text)
    durations: list[int] = []
    first_findings: tuple[tuple[Finding, ...], ...] | None = None
    first_digest: str | None = None
    for _ in range(config.measured_repetitions):
        repetition: list[tuple[Finding, ...]] = []
        for case in dataset.cases:
            started = time.perf_counter_ns()
            findings = tuple(analyzer.analyze(case.text).issues)
            durations.append(time.perf_counter_ns() - started)
            repetition.append(findings)
        snapshot = json.dumps(
            [[finding.id for finding in findings] for findings in repetition],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        digest = hashlib.sha256(snapshot).hexdigest()
        if first_findings is None:
            first_findings, first_digest = tuple(repetition), digest
        elif digest != first_digest:
            raise HoldoutAdmissionError("measured analyzer output is non-deterministic")
    if first_findings is None or not durations:
        raise HoldoutAdmissionError("measured holdout output is incomplete")
    raw = production_report(
        config, admission, dataset, first_findings, durations, peak_rss_bytes()
    )
    parsed = parse_raw_report(raw)
    _write_results(workspace, config.paths.marker.name, config, admission, raw, parsed)
    return 0
