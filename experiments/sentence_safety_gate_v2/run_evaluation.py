"""Run the aggregate-only installed-package sentence safety gate v2."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import tarfile
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from experiments.sentence_safety_gate.run_evaluation import (
    ArtifactAudit,
    CaseRun,
    InstalledRunnerSession,
    PerformanceEvidence,
    install_artifact_offline,
    preflight_release_capabilities,
    release_platform_profile,
    run_installed_cases,
)
from experiments.sentence_safety_gate.run_evaluation import (
    audit_release_artifacts as _generic_audit_release_artifacts,
)
from experiments.sentence_safety_gate.run_evaluation import (
    summarize_split as _generic_summarize_split,
)

from .gate import (  # type: ignore[attr-defined]
    FreezeInputs,
    GateConfig,
    SentenceCase,
    load_development_sentences,
    load_gate_config,
    load_reserved_holdout_sentences,
    reserve_holdout_once,
    verify_frozen_gate,
)

_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _ROOT / "scripts" / "run_sentence_safety_case.py"
_GATE_MODULE = Path(__file__).with_name("gate.py")
_EVALUATED_SOURCE = Path(__file__).with_name("evaluated_source.json")
_ANALYZER = _ROOT / "src" / "polis" / "analyzer.py"
_LT_ROOT = _ROOT / "third_party" / "languagetool-pl"
_LT_RUNNER = _LT_ROOT / "scripts" / "run_stdio.sh"
_LT_BRIDGE = (
    _LT_ROOT
    / "src"
    / "main"
    / "java"
    / "org"
    / "polis"
    / "languagetool"
    / "PolisStdioServer.java"
)
_LT_MANIFEST = _LT_ROOT / "manifest.json"
_LT_ARTIFACT = _LT_ROOT / "target" / "languagetool-pl-stdio-0.1.0-SNAPSHOT.jar"
_LT_DEPENDENCIES = _LT_ROOT / "target" / "dependency"
_PROXY_VARIABLES = (
    "ALL_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "all_proxy",
    "http_proxy",
    "https_proxy",
    "no_proxy",
)

_REPORT_KEYS = frozenset(
    {
        "schema_version",
        "experiment_id",
        "configuration_sha256",
        "environment",
        "artifact_audit",
        "fallback",
        "development",
        "holdout",
        "decision",
    }
)
_ENVIRONMENT_KEYS = frozenset(
    {
        "python_version",
        "implementation",
        "machine",
        "operating_system",
        "platform_profile",
        "source_policy_version",
        "language_tool_version",
        "language_tool_upstream_commit",
        "language_tool_manifest_sha256",
        "language_tool_bridge_sha256",
        "language_tool_runner_sha256",
        "language_tool_artifact_sha256",
        "language_tool_dependencies_sha256",
        "model_calls_per_sentence",
    }
)
_ARTIFACT_AUDIT_KEYS = frozenset(
    {"wheel_sha256", "sdist_sha256", "wheel_members", "sdist_members", "qualified"}
)
_FALLBACK_KEYS = frozenset(
    {
        "qualified",
        "status",
        "automatic_sources",
        "reviewable_sources",
        "model_calls",
        "output_hash",
    }
)
_SPLIT_KEYS = frozenset(
    {
        "total_cases",
        "automatic",
        "reviewable",
        "structured_outcome_validity",
        "protected_automatic_changes",
        "protected_reviewable_findings",
        "categories",
        "sources",
        "performance",
        "stable_repetition_digest",
        "decision",
    }
)
_CHANNEL_KEYS = frozenset(
    {
        "proposed_edits",
        "true_positive_edits",
        "false_positive_edits",
        "false_negative_edits",
        "precision",
        "recall",
        "correction_accuracy",
    }
)
_CATEGORY_CHANNEL_KEYS = _CHANNEL_KEYS - {"correction_accuracy"}
_PERFORMANCE_KEYS = frozenset(
    {
        "cold_e2e_ms",
        "warm_in_process_p50_ms",
        "warm_in_process_p95_ms",
        "warm_e2e_p50_ms",
        "warm_e2e_p95_ms",
        "cases_per_second",
        "characters_per_second",
        "python_loaded_rss_bytes",
        "child_loaded_rss_bytes",
        "combined_loaded_rss_bytes",
        "python_peak_rss_bytes",
        "child_peak_rss_bytes",
        "combined_peak_rss_bytes",
        "swap_delta_bytes",
        "socket_count",
        "model_calls",
        "process_start_count",
        "stable_repetitions",
    }
)
_SOURCE_METRIC_KEYS = frozenset(
    {
        "proposed_edits",
        "true_positive_edits",
        "false_positive_edits",
        "false_negative_edits",
        "precision",
        "recall",
        "recall_denominator",
    }
)
_FORBIDDEN_REPORT_KEYS = frozenset(
    {
        "case_id",
        "stratum",
        "text",
        "source",
        "source_text",
        "input",
        "expected_output",
        "original",
        "suggestion",
        "corrected_text",
        "selected_text",
        "raw_response",
        "case_evidence",
    }
)
_KNOWN_CATEGORY_IDENTIFIERS = frozenset(
    {"agreement", "inflection", "punctuation", "spelling", "style", "syntax"}
)
_SOURCE_IDENTIFIER = re.compile(r"rule:[a-z0-9][a-z0-9._-]{0,122}\Z")
_PRIVATE_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\Users\\)")


def audit_release_artifacts(wheel: Path, sdist: Path) -> ArtifactAudit:
    """Audit archives while adding v2 research and private-file exclusions."""

    with zipfile.ZipFile(wheel) as archive:
        _audit_v2_names(archive.namelist())
    with tarfile.open(sdist) as archive:
        _audit_v2_names(archive.getnames())
    return _generic_audit_release_artifacts(wheel, sdist)


def _audit_v2_names(names: Sequence[str]) -> None:
    private_names = frozenset(
        {".env", ".secrets", "id_rsa", "id_ed25519", "credentials.json"}
    )
    private_suffixes = (".key", ".p12", ".pfx", ".pem")
    research_fragments = (
        "/tests/fixtures/evaluation/",
        "/data/evaluation/",
        "polish_correction_safety_corpus_v2",
        "/frozen_gate.json",
        "/holdout.started",
        "/report.json",
        "/results/",
    )
    for raw_name in names:
        name = "/" + raw_name.replace("\\", "/").lower().lstrip("/")
        basename = name.rsplit("/", 1)[-1]
        if any(fragment in name for fragment in research_fragments):
            raise ValueError("distribution contains research data")
        if basename in private_names or basename.endswith(private_suffixes):
            raise ValueError("distribution contains private files")


def summarize_split(
    runs: tuple[CaseRun, ...], performance: PerformanceEvidence
) -> dict[str, object]:
    """Return aggregate scoring evidence with no per-case serialization."""

    generic_summary: object = _generic_summarize_split(runs, performance)
    summary = cast(dict[str, object], generic_summary)
    summary.pop("case_evidence", None)
    digest_payload = {
        "output_hashes": sorted(run.output_hash for run in runs),
        "repetitions": performance.stable_repetitions,
    }
    summary["stable_repetition_digest"] = _canonical_json_sha256(digest_payload)
    return summary


def validate_privacy_safe_report(
    raw: object, *, config: GateConfig | None = None
) -> Mapping[str, object]:
    """Validate the closed aggregate schema and reject private evidence."""

    report = _mapping_object(raw, "release report")

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in _FORBIDDEN_REPORT_KEYS:
                    raise ValueError("report cannot contain case or text evidence")
                if _PRIVATE_PATH.search(key):
                    raise ValueError("report cannot contain a private path")
                inspect(child)
        elif isinstance(value, list | tuple):
            for child in value:
                inspect(child)
        elif isinstance(value, str) and _PRIVATE_PATH.search(value):
            raise ValueError("report cannot contain a private path")

    inspect(report)
    _validate_report_schema(report, config=config)
    return report


def _validate_report_schema(
    report: Mapping[str, object], *, config: GateConfig | None
) -> None:
    _closed_keys(report, _REPORT_KEYS, "release report schema")
    if report["schema_version"] != 2:
        raise ValueError("release report schema version mismatch")
    _required_text(report["experiment_id"], "report experiment id")
    _digest(report["configuration_sha256"], "configuration hash")
    environment = _closed_mapping(
        report["environment"], _ENVIRONMENT_KEYS, "environment schema"
    )
    for key in _ENVIRONMENT_KEYS - {"model_calls_per_sentence"}:
        _required_text(environment[key], f"environment {key}")
    _number(environment["model_calls_per_sentence"], "model calls per sentence")
    audit = _closed_mapping(
        report["artifact_audit"], _ARTIFACT_AUDIT_KEYS, "artifact audit schema"
    )
    _digest(audit["wheel_sha256"], "wheel hash")
    _digest(audit["sdist_sha256"], "sdist hash")
    _count(audit["wheel_members"], "wheel members")
    _count(audit["sdist_members"], "sdist members")
    _boolean(audit["qualified"], "artifact audit decision")
    fallback = _closed_mapping(
        report["fallback"], _FALLBACK_KEYS, "fallback evidence schema"
    )
    _boolean(fallback["qualified"], "fallback decision")
    if fallback["status"] not in {"complete", "failed"}:
        raise ValueError("fallback status is invalid")
    configured_sources = (
        config.automatic_sources | config.reviewable_sources
        if config is not None
        else None
    )
    for source in _string_list(
        fallback["automatic_sources"], "fallback automatic sources"
    ):
        _validate_source_identifier(source, configured_sources)
    for source in _string_list(
        fallback["reviewable_sources"], "fallback reviewable sources"
    ):
        _validate_source_identifier(source, configured_sources)
    _count(fallback["model_calls"], "fallback model calls")
    _digest(fallback["output_hash"], "fallback output hash")
    _validate_split(
        report["development"],
        "development split",
        configured_sources=configured_sources,
    )
    if report["holdout"] is not None:
        _validate_split(
            report["holdout"],
            "holdout split",
            configured_sources=configured_sources,
        )
    decision = _closed_mapping(
        report["decision"], frozenset({"qualified", "scope"}), "report decision"
    )
    _boolean(decision["qualified"], "report decision")
    if decision["scope"] != "sentence_only":
        raise ValueError("report scope must be sentence-only")


def _validate_split(
    value: object,
    label: str,
    *,
    configured_sources: frozenset[str] | None,
) -> dict[str, Any]:
    split = _closed_mapping(value, _SPLIT_KEYS, f"{label} schema")
    _count(split["total_cases"], f"{label} cases", positive=True)
    _validate_channel(split["automatic"], f"{label} automatic")
    _validate_channel(split["reviewable"], f"{label} reviewable")
    _number(split["structured_outcome_validity"], f"{label} outcome validity")
    _count(split["protected_automatic_changes"], f"{label} protected changes")
    _count(split["protected_reviewable_findings"], f"{label} protected findings")
    categories = _mapping_object(split["categories"], f"{label} categories")
    for category_name, item in categories.items():
        if category_name not in _KNOWN_CATEGORY_IDENTIFIERS:
            raise ValueError("report category identifier is invalid")
        category = _closed_mapping(
            item,
            frozenset({"gold_edits", "automatic", "reviewable"}),
            f"{label} category",
        )
        _count(category["gold_edits"], f"{label} category gold edits")
        _validate_channel(
            category["automatic"], f"{label} category automatic", category=True
        )
        _validate_channel(
            category["reviewable"], f"{label} category reviewable", category=True
        )
    sources = _mapping_object(split["sources"], f"{label} sources")
    for source_name, item in sources.items():
        _validate_source_identifier(source_name, configured_sources)
        source = _closed_mapping(item, _SOURCE_METRIC_KEYS, f"{label} source")
        for key in _SOURCE_METRIC_KEYS - {"precision", "recall", "recall_denominator"}:
            _count(source[key], f"{label} source {key}")
        _optional_number(source["precision"], f"{label} source precision")
        _optional_number(source["recall"], f"{label} source recall")
        if source["recall_denominator"] != "all_gold_edits":
            raise ValueError("source recall denominator is invalid")
    performance = _closed_mapping(
        split["performance"], _PERFORMANCE_KEYS, f"{label} performance"
    )
    for key, item in performance.items():
        if key.endswith("_bytes") or key in {
            "socket_count",
            "model_calls",
            "process_start_count",
            "stable_repetitions",
        }:
            _count(item, f"{label} performance {key}")
        else:
            _number(item, f"{label} performance {key}")
    _digest(split["stable_repetition_digest"], f"{label} stability digest")
    decision = _closed_mapping(
        split["decision"], frozenset({"qualified"}), f"{label} decision"
    )
    _boolean(decision["qualified"], f"{label} decision")
    return split


def _validate_source_identifier(
    source: str, configured_sources: frozenset[str] | None
) -> None:
    if _SOURCE_IDENTIFIER.fullmatch(source) is None:
        raise ValueError("report source identifier is invalid")
    if configured_sources is not None and source not in configured_sources:
        raise ValueError("report source identifier is not configured")


def _validate_channel(value: object, label: str, *, category: bool = False) -> None:
    expected = _CATEGORY_CHANNEL_KEYS if category else _CHANNEL_KEYS
    channel = _closed_mapping(value, expected, f"{label} schema")
    for key in (
        "proposed_edits",
        "true_positive_edits",
        "false_positive_edits",
        "false_negative_edits",
    ):
        _count(channel[key], f"{label} {key}")
    _optional_number(channel["precision"], f"{label} precision")
    _optional_number(channel["recall"], f"{label} recall")
    if not category:
        _optional_number(channel["correction_accuracy"], f"{label} accuracy")


def gate_qualifies(report: Mapping[str, object], config: GateConfig) -> bool:
    """Return whether one aggregate split passes every frozen gate."""

    try:
        automatic = _mapping_object(report["automatic"], "automatic metrics")
        reviewable = _mapping_object(report["reviewable"], "reviewable metrics")
        performance = _mapping_object(report["performance"], "performance metrics")
        gates = config.gates
        return bool(
            _count(automatic["proposed_edits"], "automatic proposals") > 0
            and _number(automatic["precision"], "automatic precision")
            >= gates.automatic_minimum_precision
            and _number(automatic["correction_accuracy"], "automatic accuracy")
            >= gates.automatic_minimum_correction_accuracy
            and _count(reviewable["proposed_edits"], "reviewable proposals") > 0
            and _number(reviewable["precision"], "reviewable precision")
            >= gates.reviewable_minimum_precision
            and _number(report["structured_outcome_validity"], "outcome validity")
            >= gates.minimum_structured_outcome_validity
            and _count(report["protected_automatic_changes"], "protected changes")
            <= gates.maximum_protected_automatic_changes
            and _count(report["protected_reviewable_findings"], "protected findings")
            <= gates.maximum_protected_reviewable_findings
            and _number(performance["warm_in_process_p95_ms"], "in-process p95")
            <= gates.maximum_warm_in_process_p95_ms
            and _number(performance["warm_e2e_p95_ms"], "end-to-end p95")
            <= gates.maximum_warm_e2e_p95_ms
            and _count(performance["combined_peak_rss_bytes"], "peak RSS")
            <= gates.maximum_combined_peak_rss_bytes
            and _count(performance["swap_delta_bytes"], "swap delta")
            <= gates.maximum_swap_delta_bytes
            and _count(performance["socket_count"], "socket count")
            <= gates.maximum_socket_count
            and _count(performance["model_calls"], "model calls")
            == gates.required_model_calls
            and _count(performance["process_start_count"], "process starts")
            == gates.required_process_start_count
            and _count(performance["stable_repetitions"], "stable repetitions")
            >= gates.required_stable_repetitions
        )
    except (KeyError, TypeError, ValueError):
        return False


def authorize_and_load_holdout(
    *,
    prior_report: Mapping[str, object],
    config: GateConfig,
    frozen_path: Path,
    marker_path: Path,
    inputs: FreezeInputs,
    corpus_path: Path,
    approval_path: Path,
) -> tuple[SentenceCase, ...]:
    """Recompute development, reserve once, then load approved holdout."""

    preflight_release_capabilities()
    validate_privacy_safe_report(prior_report, config=config)
    _validate_development_report(prior_report, config, inputs)
    verify_frozen_gate(
        frozen_path,
        inputs,
        development_report=prior_report,
    )
    reservation = reserve_holdout_once(frozen_path, marker_path, inputs)
    return load_reserved_holdout_sentences(
        corpus_path,
        approval_path,
        marker_path,
        frozen_path,
        inputs,
        reservation=reservation,
    )


def _validate_development_report(
    report: Mapping[str, object], config: GateConfig, inputs: FreezeInputs
) -> None:
    validate_privacy_safe_report(report, config=config)
    if report["experiment_id"] != config.experiment_id:
        raise ValueError("development report identity mismatch")
    hashes = _freeze_hashes(inputs)
    if report["configuration_sha256"] != hashes.get("configuration_sha256"):
        raise ValueError("development report configuration identity mismatch")
    if report["holdout"] is not None or report["decision"] != {
        "qualified": False,
        "scope": "sentence_only",
    }:
        raise ValueError("development report decision mismatch")
    environment = _mapping_object(report["environment"], "development environment")
    expected_environment = {
        "source_policy_version": config.source_policy_version,
        "language_tool_version": config.language_tool["version"],
        "language_tool_upstream_commit": config.language_tool["upstream_commit"],
        "language_tool_manifest_sha256": config.language_tool["manifest_sha256"],
        "language_tool_bridge_sha256": config.language_tool["bridge_sha256"],
        "language_tool_runner_sha256": config.language_tool["runner_sha256"],
        "language_tool_artifact_sha256": config.language_tool["artifact_sha256"],
        "language_tool_dependencies_sha256": config.language_tool[
            "dependencies_sha256"
        ],
    }
    if any(environment[key] != value for key, value in expected_environment.items()):
        raise ValueError("development report runtime identity mismatch")
    if environment["platform_profile"] != config.platform_profile:
        raise ValueError("development report platform identity mismatch")
    audit = _mapping_object(report["artifact_audit"], "artifact audit")
    if (
        audit["qualified"] is not True
        or audit["wheel_sha256"] != hashes.get("wheel_sha256")
        or audit["sdist_sha256"] != hashes.get("sdist_sha256")
    ):
        raise ValueError("development report artifact identity mismatch")
    fallback = _mapping_object(report["fallback"], "fallback evidence")
    if (
        fallback["qualified"] is not True
        or fallback["status"] != "complete"
        or fallback["model_calls"] != config.gates.required_model_calls
    ):
        raise ValueError("development fallback did not qualify")
    development = _mapping_object(report["development"], "development split")
    if development["total_cases"] != 80:
        raise ValueError("development report must contain exactly 80 aggregate cases")
    decision = development["decision"]
    qualifies = gate_qualifies(development, config)
    if decision != {"qualified": qualifies} or not qualifies:
        raise ValueError("development sentence gate did not qualify")


def _validate_final_report(
    report: Mapping[str, object], config: GateConfig, inputs: FreezeInputs
) -> dict[str, object]:
    validate_privacy_safe_report(report, config=config)
    development_snapshot = dict(report)
    development_snapshot["holdout"] = None
    development_snapshot["decision"] = {
        "qualified": False,
        "scope": "sentence_only",
    }
    _validate_development_report(development_snapshot, config, inputs)
    holdout = report["holdout"]
    if holdout is None:
        raise ValueError("final report holdout metadata is unavailable")
    holdout_mapping = _mapping_object(holdout, "holdout split")
    if holdout_mapping["total_cases"] != 160:
        raise ValueError(
            "final report must contain exactly 160 aggregate holdout cases"
        )
    qualified = gate_qualifies(holdout_mapping, config)
    if holdout_mapping["decision"] != {"qualified": qualified}:
        raise ValueError("holdout decision metadata mismatch")
    if report["decision"] != {
        "qualified": qualified,
        "scope": "sentence_only",
    }:
        raise ValueError("final decision metadata mismatch")
    return development_snapshot


def run_prepared_split(
    *,
    cases: tuple[SentenceCase, ...] | None,
    prior_report: Mapping[str, object] | None,
    config: GateConfig,
    freeze_inputs: FreezeInputs,
    frozen_path: Path | None,
    marker_path: Path | None,
    corpus_path: Path,
    approval_path: Path,
    wheel: Path,
    sdist: Path,
    vendored_stdio: Path,
    timeout_seconds: float,
) -> tuple[
    tuple[SentenceCase, ...],
    tuple[CaseRun, ...],
    PerformanceEvidence,
    dict[str, object],
]:
    """Complete reversible installed setup before possible reservation."""

    with tempfile.TemporaryDirectory(prefix="polis-sentence-safety-v2-") as raw_temp:
        temporary = Path(raw_temp)
        wheel_python = install_artifact_offline(wheel, temporary / "wheel-install")
        sdist_python = install_artifact_offline(
            sdist,
            temporary / "sdist-install",
            build_backend_path=_build_backend_path(),
        )
        _installed_smoke(sdist_python, temporary / "sdist-smoke")
        fallback = _fallback_evidence(
            wheel_python,
            temporary,
            config,
            timeout_seconds=timeout_seconds,
        )
        with InstalledRunnerSession(
            python=wheel_python,
            runner=_RUNNER,
            vendored_stdio=vendored_stdio,
            working_directory=temporary / "evaluation",
            timeout_seconds=timeout_seconds,
        ) as session:
            selected_cases = cases
            if selected_cases is None:
                if prior_report is None or frozen_path is None or marker_path is None:
                    raise ValueError("holdout authorization inputs are unavailable")
                selected_cases = authorize_and_load_holdout(
                    prior_report=prior_report,
                    config=config,
                    frozen_path=frozen_path,
                    marker_path=marker_path,
                    inputs=freeze_inputs,
                    corpus_path=corpus_path,
                    approval_path=approval_path,
                )
            generic_runner = cast(Any, run_installed_cases)
            runs, performance = generic_runner(
                selected_cases,
                session,
                config,
                repetitions=config.gates.required_stable_repetitions,
            )
    return selected_cases, runs, performance, fallback


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--development", action="store_true")
    mode.add_argument("--holdout", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--verify-development", action="store_true")
    mode.add_argument("--verify-result", action="store_true")
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("config.json")
    )
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--vendored-stdio", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--frozen", type=Path)
    parser.add_argument("--holdout-marker", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    arguments = parser.parse_args(argv)
    if arguments.development and (arguments.output is None or arguments.freeze is None):
        parser.error("--development requires --output and --freeze")
    if arguments.holdout and (
        arguments.output is None
        or arguments.frozen is None
        or arguments.holdout_marker is None
    ):
        parser.error("--holdout requires --output, --frozen, and --holdout-marker")
    if arguments.verify_development and (
        arguments.output is None or arguments.freeze is None
    ):
        parser.error("--verify-development requires --output and --freeze")
    if arguments.verify_result and (
        arguments.output is None
        or arguments.frozen is None
        or arguments.holdout_marker is None
    ):
        parser.error(
            "--verify-result requires --output, --frozen, and --holdout-marker"
        )
    if not arguments.verify_result and arguments.vendored_stdio is None:
        parser.error("evaluation modes require --vendored-stdio")
    return arguments


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    config = load_gate_config(arguments.config)
    wheel, sdist = _distribution_paths(arguments.dist)
    audit = audit_release_artifacts(wheel, sdist)
    freeze_inputs = _freeze_inputs(arguments.config, wheel, sdist, config)

    if arguments.verify_result:
        assert arguments.output is not None
        assert arguments.frozen is not None
        assert arguments.holdout_marker is not None
        verified_report = _read_report(arguments.output)
        development_snapshot = _validate_final_report(
            verified_report, config, freeze_inputs
        )
        frozen = verify_frozen_gate(
            arguments.frozen,
            freeze_inputs,
            development_report=development_snapshot,
        )
        marker = _mapping_object(
            json.loads(arguments.holdout_marker.read_text(encoding="utf-8")),
            "holdout marker",
        )
        if marker != frozen.as_dict():
            raise ValueError("holdout marker identity mismatch")
        print("sentence safety v2 result metadata verified")
        return 0

    release_platform_profile()
    _validate_frozen_runtime(config)
    assert arguments.vendored_stdio is not None
    vendored_stdio = _validate_vendored_stdio(arguments.vendored_stdio, config)

    if arguments.preflight:
        preflight_release_capabilities()
        print("sentence safety v2 preflight qualified")
        return 0

    if arguments.verify_development:
        assert arguments.output is not None
        assert arguments.freeze is not None
        verified_report = _read_report(arguments.output)
        _validate_development_report(verified_report, config, freeze_inputs)
        verify_frozen_gate(
            arguments.freeze,
            freeze_inputs,
            development_report=verified_report,
        )
        print("sentence safety v2 development metadata verified")
        return 0

    prior_report: dict[str, Any] | None = None
    if arguments.holdout:
        assert arguments.output is not None
        prior_report = _read_report(arguments.output)
        cases: tuple[SentenceCase, ...] | None = None
    else:
        cases = load_development_sentences(_ROOT / config.corpus_xml_path)

    cases, runs, performance, fallback = run_prepared_split(
        cases=cases,
        prior_report=prior_report,
        config=config,
        freeze_inputs=freeze_inputs,
        frozen_path=arguments.frozen,
        marker_path=arguments.holdout_marker,
        corpus_path=_ROOT / config.corpus_json_path,
        approval_path=_ROOT / config.corpus_approval_path,
        wheel=wheel,
        sdist=sdist,
        vendored_stdio=vendored_stdio,
        timeout_seconds=arguments.timeout_seconds,
    )
    summary = summarize_split(runs, performance)
    qualified = bool(fallback["qualified"] and gate_qualifies(summary, config))
    split_payload = {**summary, "decision": {"qualified": qualified}}
    if arguments.development:
        report_payload: dict[str, object] = {
            "schema_version": 2,
            "experiment_id": config.experiment_id,
            "configuration_sha256": _sha256_path(arguments.config),
            "environment": _environment_payload(config, performance, runs),
            "artifact_audit": audit.as_dict(),
            "fallback": fallback,
            "development": split_payload,
            "holdout": None,
            "decision": {"qualified": False, "scope": "sentence_only"},
        }
    else:
        if prior_report is None:
            raise AssertionError("prior development metadata is unavailable")
        report_payload = prior_report
        report_payload["holdout"] = split_payload
        report_payload["decision"] = {
            "qualified": qualified,
            "scope": "sentence_only",
        }
    validate_privacy_safe_report(report_payload, config=config)
    if arguments.development and qualified:
        assert arguments.freeze is not None
        _freeze_gate(freeze_inputs, arguments.freeze, report_payload)
    assert arguments.output is not None
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("sentence safety v2 aggregate report written")
    return 0 if qualified else 1


def _read_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("aggregate report is unavailable")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], validate_privacy_safe_report(raw))


def _distribution_paths(dist: Path) -> tuple[Path, Path]:
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("distribution directory must contain one wheel and one sdist")
    return wheels[0], sdists[0]


def _validate_frozen_runtime(config: GateConfig) -> None:
    expected = config.language_tool
    files = {
        "manifest_sha256": _LT_MANIFEST,
        "bridge_sha256": _LT_BRIDGE,
        "runner_sha256": _LT_RUNNER,
        "artifact_sha256": _LT_ARTIFACT,
    }
    for name, path in files.items():
        if not path.is_file() or _sha256_path(path) != expected[name]:
            raise ValueError(f"LanguageTool {name} mismatch")
    if _directory_sha256(_LT_DEPENDENCIES) != expected["dependencies_sha256"]:
        raise ValueError("LanguageTool dependencies identity mismatch")
    corpus_files = {
        "JSON": (_ROOT / config.corpus_json_path, config.corpus_sha256),
        "XML": (_ROOT / config.corpus_xml_path, config.corpus_xml_sha256),
        "approval": (
            _ROOT / config.corpus_approval_path,
            config.corpus_approval_sha256,
        ),
    }
    for label, (path, digest) in corpus_files.items():
        if not path.is_file() or _sha256_path(path) != digest:
            raise ValueError(f"corpus {label} identity mismatch")


def _validate_vendored_stdio(path: Path, config: GateConfig) -> Path:
    resolved = path.resolve()
    if resolved != _LT_RUNNER.resolve():
        raise ValueError("vendored stdio must be the pinned runner")
    if _sha256_path(resolved) != config.language_tool["runner_sha256"]:
        raise ValueError("pinned runner identity mismatch")
    return resolved


def _freeze_inputs(
    config_path: Path, wheel: Path, sdist: Path, config: GateConfig
) -> FreezeInputs:
    return FreezeInputs(
        files={
            "configuration": config_path,
            "evaluator": Path(__file__),
            "gate": _GATE_MODULE,
            "evaluated_source": _EVALUATED_SOURCE,
            "installed_runner": _RUNNER,
            "source_policy": _ANALYZER,
            "corpus_json": _ROOT / config.corpus_json_path,
            "corpus_xml": _ROOT / config.corpus_xml_path,
            "corpus_approval": _ROOT / config.corpus_approval_path,
            "language_tool_bridge": _LT_BRIDGE,
            "language_tool_runner": _LT_RUNNER,
            "language_tool_manifest": _LT_MANIFEST,
            "language_tool_artifact": _LT_ARTIFACT,
            "wheel": wheel,
            "sdist": sdist,
        },
        directories={"language_tool_dependencies": _LT_DEPENDENCIES},
    )


def _freeze_gate(
    inputs: FreezeInputs,
    destination: Path,
    development_report: Mapping[str, object],
) -> None:
    payload = _freeze_hashes(inputs)
    payload["development_report_sha256"] = _canonical_json_sha256(development_report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _freeze_hashes(inputs: FreezeInputs) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, path in sorted(inputs.files.items()):
        if not path.is_file():
            raise ValueError(f"freeze file {name} is unavailable")
        hashes[f"{name}_sha256"] = _sha256_path(path)
    for name, path in sorted(inputs.directories.items()):
        hashes[f"{name}_sha256"] = _directory_sha256(path)
    return hashes


def _directory_sha256(path: Path) -> str:
    if not path.is_dir():
        raise ValueError("freeze directory is unavailable")
    records = [
        (item.relative_to(path).as_posix(), _sha256_path(item))
        for item in sorted(path.rglob("*"))
        if item.is_file()
    ]
    if not records:
        raise ValueError("freeze directory is empty")
    encoded = json.dumps(records, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_backend_path() -> Path:
    import hatchling

    if hatchling.__file__ is None:
        raise RuntimeError("offline build backend is unavailable")
    return Path(hatchling.__file__).resolve().parents[1]


def _installed_smoke(python: Path, working_directory: Path) -> None:
    working_directory.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        (
            os.fspath(python),
            "-c",
            "from polis import Analyzer, AnalyzerConfig; "
            "a=Analyzer(AnalyzerConfig()); "
            "r=a.analyze('Zeby wrócić.'); "
            "c=a.correct('Zeby wrócić.'); "
            "assert r.issues and c.corrected_text == 'Żeby wrócić.'",
        ),
        cwd=working_directory,
        env=_offline_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError("installed artifact public API smoke failed")


def _fallback_evidence(
    python: Path,
    temporary: Path,
    config: GateConfig,
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    unavailable = temporary / "unavailable-languagetool"
    unavailable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    unavailable.chmod(0o700)
    with InstalledRunnerSession(
        python=python,
        runner=_RUNNER,
        vendored_stdio=unavailable,
        working_directory=temporary / "fallback",
        timeout_seconds=timeout_seconds,
    ) as session:
        raw, _ = session.exchange(1, "Zeby wrócić.")
    if raw.get("status") != "complete":
        model_calls = _count(
            raw.get("model_calls", 0),
            "failed fallback model calls",
        )
        return {
            "qualified": False,
            "status": "failed",
            "automatic_sources": [],
            "reviewable_sources": [],
            "model_calls": model_calls,
            "output_hash": _canonical_json_sha256(raw),
        }
    automatic = raw.get("automatic_findings")
    reviewable = raw.get("reviewable_findings")
    automatic_sources = _finding_sources(automatic)
    reviewable_sources = _finding_sources(reviewable)
    model_calls = _count(raw.get("model_calls"), "fallback model calls")
    qualified = bool(
        automatic_sources == ["rule:spelling.zeby"]
        and not reviewable_sources
        and raw.get("corrected_text") == "Żeby wrócić."
        and model_calls == config.gates.required_model_calls
    )
    return {
        "qualified": qualified,
        "status": "complete",
        "automatic_sources": automatic_sources,
        "reviewable_sources": reviewable_sources,
        "model_calls": model_calls,
        "output_hash": _canonical_json_sha256(raw),
    }


def _finding_sources(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("fallback finding evidence is invalid")
    sources: set[str] = set()
    for raw in value:
        item = _mapping_object(raw, "fallback finding")
        sources.add(_required_text(item.get("source"), "fallback finding source"))
    return sorted(sources)


def _environment_payload(
    config: GateConfig,
    performance: PerformanceEvidence,
    runs: Sequence[CaseRun],
) -> dict[str, object]:
    versions = {run.observation.source_policy_version for run in runs}
    if versions != {config.source_policy_version}:
        raise ValueError("runner source policy identity mismatch")
    if any(
        item.source not in config.automatic_sources
        for run in runs
        for item in run.observation.automatic_edits
    ) or any(
        item.source not in config.reviewable_sources
        for run in runs
        for item in run.observation.reviewable_edits
    ):
        raise ValueError("runner channel source identity mismatch")
    return {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "machine": platform.machine(),
        "operating_system": platform.platform(),
        "platform_profile": release_platform_profile(),
        "source_policy_version": config.source_policy_version,
        "language_tool_version": config.language_tool["version"],
        "language_tool_upstream_commit": config.language_tool["upstream_commit"],
        "language_tool_manifest_sha256": config.language_tool["manifest_sha256"],
        "language_tool_bridge_sha256": config.language_tool["bridge_sha256"],
        "language_tool_runner_sha256": config.language_tool["runner_sha256"],
        "language_tool_artifact_sha256": config.language_tool["artifact_sha256"],
        "language_tool_dependencies_sha256": config.language_tool[
            "dependencies_sha256"
        ],
        "model_calls_per_sentence": (
            performance.model_calls / len(runs) if runs else 0.0
        ),
    }


def _offline_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PIP_NO_INDEX"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    for name in _PROXY_VARIABLES:
        environment.pop(name, None)
    return environment


def _mapping_object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _closed_mapping(
    value: object, expected: frozenset[str], label: str
) -> dict[str, Any]:
    mapping = _mapping_object(value, label)
    _closed_keys(mapping, expected, label)
    return mapping


def _closed_keys(
    value: Mapping[str, object], expected: frozenset[str], label: str
) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} must contain exactly the aggregate keys")


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"{label} must be a string list")
    return tuple(cast(list[str], value))


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _count(value: object, label: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < int(positive):
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _number(value: object, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{label} must be finite and non-negative")
    return float(value)


def _optional_number(value: object, label: str) -> float | None:
    return None if value is None else _number(value, label)


def _digest(value: object, label: str) -> str:
    if not (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be SHA-256")
    return value


__all__ = [
    "ArtifactAudit",
    "CaseRun",
    "InstalledRunnerSession",
    "PerformanceEvidence",
    "audit_release_artifacts",
    "authorize_and_load_holdout",
    "install_artifact_offline",
    "main",
    "run_installed_cases",
    "run_prepared_split",
    "summarize_split",
    "validate_privacy_safe_report",
]


if __name__ == "__main__":
    raise SystemExit(main())
