from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from polis import Analyzer, AnalyzerConfig
from polis.core import Category, PolisError, SourceKind
from polis.evaluation.metrics import BaselineResult, QualityCounts
from polis.evaluation.quality_dataset import (
    QualityDataset,
    QualityDatasetError,
    QualityDatasetVersion,
    as_evaluation_dataset,
    load_quality_dataset,
    quality_dataset_paths,
)
from polis.evaluation.quality_protocol import (
    InstallationProfile,
    MorphologyProviderIdentity,
    NonDeterministicBaselineError,
    RunIdentity,
    RunProfile,
    UnsupportedRssPlatformError,
    run_quality_protocol,
)
from polis.evaluation.quality_report import (
    QualityReportError,
    load_quality_report,
    load_threshold_proposal,
    validate_threshold_proposal,
    write_quality_report,
    write_quality_result,
)
from polis.evaluation.quality_v4_measurement import measure_v4
from polis.rules._morfeusz import _load_qualified_morfeusz

_ANALYZER_IDENTITY: Final = "Analyzer(AnalyzerConfig())"
_SHA256_PATTERN: Final = re.compile(r"[0-9a-f]{64}")
_SOURCE_SHA_PATTERN: Final = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True, slots=True)
class IncompleteQualityReviewError(Exception):
    status: str
    reviewed_cases: int
    total_cases: int

    def __str__(self) -> str:
        return (
            "quality dataset requires completed maintainer review "
            f"(status={self.status}, reviewed={self.reviewed_cases}/"
            f"{self.total_cases})"
        )


@dataclass(frozen=True, slots=True)
class QualityProfileError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def _nonnegative_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be greater than or equal to 0")
    return parsed


def _repetition_count(value: str) -> int:
    parsed = int(value)
    if parsed < 2:
        raise argparse.ArgumentTypeError("must be greater than or equal to 2")
    return parsed


def _artifact_sha256(value: str) -> str:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(
            "must be exactly 64 lowercase hexadecimal characters"
        )
    return value


def _source_sha(value: str) -> str:
    if _SOURCE_SHA_PATTERN.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(
            "must be exactly 40 lowercase hexadecimal characters"
        )
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m polis.evaluation.quality_runner",
        description="Run or validate the default Polis quality protocol",
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("baseline", "Measure the reviewed active dataset"),
        ("result", "Measure a post-change result artifact"),
    ):
        measurement = subparsers.add_parser(command, help=help_text, allow_abbrev=False)
        measurement.add_argument("--warmup", type=_nonnegative_integer, default=1)
        measurement.add_argument("--repetitions", type=_repetition_count, default=5)
        measurement.add_argument(
            "--dataset-version",
            type=QualityDatasetVersion,
            choices=tuple(QualityDatasetVersion),
            default=QualityDatasetVersion.V1,
        )
        measurement.add_argument(
            "--artifact-sha256", type=_artifact_sha256, required=True
        )
        measurement.add_argument("--source-sha", type=_source_sha)
        measurement.add_argument(
            "--profile", type=InstallationProfile, choices=tuple(InstallationProfile)
        )
        measurement.add_argument("--output", type=Path, required=True)
        measurement.add_argument("--replace", action="store_true")

    candidate = subparsers.add_parser(
        "propose",
        help="Derive a pending v4 candidate from measured baselines",
        allow_abbrev=False,
    )
    candidate.add_argument("--baseline", type=Path, required=True)
    candidate.add_argument("--morphology-baseline", type=Path, required=True)
    candidate.add_argument("--wheel-filename", required=True)
    candidate.add_argument("--output", type=Path, required=True)
    candidate.add_argument("--replace", action="store_true")

    proposal = subparsers.add_parser(
        "validate-proposal",
        help="Validate a pending threshold proposal",
        allow_abbrev=False,
    )
    proposal.add_argument("--baseline", type=Path, required=True)
    proposal.add_argument("--morphology-baseline", type=Path)
    proposal.add_argument("--proposal", type=Path, required=True)

    compare = subparsers.add_parser(
        "compare", help="Compare two v4 profile measurements", allow_abbrev=False
    )
    for flag in (
        "baseline-default",
        "baseline-morphology",
        "result-default",
        "result-morphology",
        "proposal",
    ):
        compare.add_argument(f"--{flag}", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    compare.add_argument("--replace", action="store_true")
    return parser


def _require_complete_review(dataset: QualityDataset) -> None:
    case_ids = {case.id for case in dataset.cases}
    reviewed_case_ids = dataset.review.reviewed_case_ids
    if (
        dataset.review.status != "maintainer-reviewed"
        or len(reviewed_case_ids) != len(dataset.cases)
        or set(reviewed_case_ids) != case_ids
    ):
        raise IncompleteQualityReviewError(
            status=dataset.review.status,
            reviewed_cases=len(reviewed_case_ids),
            total_cases=len(dataset.cases),
        )


def _manifest_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _profile_identity(profile: InstallationProfile) -> RunProfile:
    if profile is InstallationProfile.DEFAULT:
        try:
            importlib.metadata.version("morfeusz2")
        except importlib.metadata.PackageNotFoundError:
            return RunProfile(
                id=profile,
                morphology_provider=None,
                planned_morphology_source_semantics="provider-absent-abstention",
                planned_non_morphology_source_semantics="sources-not-implemented",
            )
        raise QualityProfileError(
            "default profile requires morfeusz2 to be absent from the environment"
        )
    provider = _load_qualified_morfeusz()
    if provider is None:
        raise QualityProfileError(
            "morphology profile requires the qualified morfeusz2 provider"
        )
    return RunProfile(
        id=profile,
        morphology_provider=MorphologyProviderIdentity(
            provider="morfeusz2",
            package_version=provider.identity.package_version,
            dictionary_id=provider.identity.dictionary_id,
            dictionary_notice_sha256=provider.identity.dictionary_notice_sha256,
        ),
        planned_morphology_source_semantics=(
            "qualified-provider-exercised-sources-not-implemented"
        ),
        planned_non_morphology_source_semantics="sources-not-implemented",
    )


def _run_baseline(args: argparse.Namespace, *, result_schema: bool = False) -> None:
    version = QualityDatasetVersion(args.dataset_version)
    dataset_path, manifest_path = quality_dataset_paths(version)
    dataset = load_quality_dataset(
        dataset_path=dataset_path,
        manifest_path=manifest_path,
        version=version,
    )
    _require_complete_review(dataset)
    analyzer = Analyzer(AnalyzerConfig())
    identity = RunIdentity(
        analyzer=_ANALYZER_IDENTITY,
        artifact_sha256=args.artifact_sha256,
        package_version=importlib.metadata.version("polis-nlp"),
        python_version=platform.python_version(),
        platform_system=platform.system(),
        platform_release=platform.release(),
        platform_machine=platform.machine(),
        dataset_schema_id=dataset.schema_id,
        dataset_schema_version=dataset.schema_version,
        manifest_schema_id="polis.quality-development-manifest",
        manifest_schema_version=dataset.schema_version,
        manifest_sha256=_manifest_sha256(manifest_path),
        source_sha=args.source_sha,
        profile=(
            _profile_identity(InstallationProfile(args.profile))
            if args.profile is not None
            else None
        ),
    )
    if version is QualityDatasetVersion.V4:
        source_snapshot = tuple(
            {
                "source": item.source,
                "operation": item.operation,
                "behavior_version": item.behavior_version,
            }
            for item in analyzer.source_identity_snapshot
        )
        identity = RunIdentity(
            analyzer=identity.analyzer,
            artifact_sha256=identity.artifact_sha256,
            package_version=identity.package_version,
            python_version=identity.python_version,
            platform_system=identity.platform_system,
            platform_release=identity.platform_release,
            platform_machine=identity.platform_machine,
            dataset_schema_id=identity.dataset_schema_id,
            dataset_schema_version=identity.dataset_schema_version,
            manifest_schema_id=identity.manifest_schema_id,
            manifest_schema_version=identity.manifest_schema_version,
            manifest_sha256=identity.manifest_sha256,
            source_sha=identity.source_sha,
            profile=identity.profile,
            source_snapshot=source_snapshot,
        )
        measured = measure_v4(
            dataset=dataset,
            analyzer=lambda text: tuple(analyzer.analyze(text).issues),
            run_identity=identity,
            warmup_repetitions=args.warmup,
            measured_repetitions=args.repetitions,
        )
        by_category = {
            Category(category): counts
            for category, counts in measured.categories.items()
        }
        baseline = BaselineResult(
            run_label="quality-protocol-v4",
            run_reference=identity.artifact_sha256,
            configuration=identity.analyzer,
            dataset_id=dataset.id,
            dataset_schema_version=dataset.schema_version,
            dataset_cases=len(dataset.cases),
            dataset_source=f"quality:{dataset.id}@{dataset.dataset_version}",
            dataset_hash=dataset.canonical_sha256,
            incorrect_case_count=sum(
                case.kind.value == "error" for case in dataset.cases
            ),
            correct_case_count=sum(
                case.kind.value == "correct" for case in dataset.cases
            ),
            aggregate=measured.aggregate,
            by_category=by_category,
            by_source={kind: QualityCounts() for kind in SourceKind},
        )
        from polis.evaluation.quality_protocol import QualityProtocolResult

        result = QualityProtocolResult(
            run_identity=identity,
            dataset_id=dataset.id,
            dataset_sha256=dataset.canonical_sha256,
            warmup_repetitions=args.warmup,
            measured_repetitions=args.repetitions,
            repetition_hashes=measured.repetition_hashes,
            baseline=baseline,
            latency=measured.latency,
            throughput=measured.throughput,
            resources=measured.resources,
            v4_diagnostics=measured.v4_diagnostics,
        )
    else:
        result = run_quality_protocol(
            dataset=as_evaluation_dataset(dataset),
            analyzer=lambda text: tuple(analyzer.analyze(text).issues),
            run_identity=identity,
            warmup_repetitions=args.warmup,
            measured_repetitions=args.repetitions,
        )
    if result_schema:
        write_quality_result(result, args.output, replace=args.replace)
    else:
        write_quality_report(result, args.output, replace=args.replace)


def _floor_payload(raw: dict[str, object]) -> dict[str, object]:
    return {
        "minimum_precision": raw["exact_edit_precision"],
        "minimum_recall": raw["exact_edit_recall"],
        "minimum_f1": raw["exact_edit_f1"],
        "minimum_exact_span_accuracy": raw["span_accuracy"],
        "minimum_exact_correction_accuracy": raw["suggestion_accuracy"],
        "maximum_false_alarm_rate": raw["correct_sentence_false_alarm_rate"],
    }


def _performance_payload(report: object) -> dict[str, object]:
    assert hasattr(report, "latency")
    assert hasattr(report, "throughput")
    assert hasattr(report, "resources")
    assert hasattr(report, "warmup_repetitions")
    assert hasattr(report, "measured_repetitions")
    return {
        "maximum_p95_latency_ns": report.latency.p95_ns,
        "minimum_throughput_cases_per_second": report.throughput.cases_per_second,
        "maximum_peak_rss_bytes": report.resources.peak_rss_bytes,
        "required_warmup_repetitions": report.warmup_repetitions,
        "required_measured_repetitions": report.measured_repetitions,
        "require_identical_repetition_hashes": True,
        "required_environment_match": [
            "python_version",
            "platform_system",
            "platform_release",
            "platform_machine",
        ],
        "allowed_regression_fraction": 0.0,
        "missing_metric": "fail",
        "nondeterminism": "fail",
        "environment_mismatch": "fail",
        "performance_regression": "fail",
    }


def _pending_v4_proposal(args: argparse.Namespace) -> None:
    default = load_quality_report(args.baseline)
    morphology = load_quality_report(args.morphology_baseline)
    reports = (default, morphology)
    if any(report.run_identity.dataset_schema_version != 4 for report in reports):
        raise QualityReportError("v4 proposal requires v4 baselines")
    if default.dataset_sha256 != morphology.dataset_sha256:
        raise QualityReportError("v4 proposal baselines use different datasets")
    if default.run_identity.manifest_sha256 != morphology.run_identity.manifest_sha256:
        raise QualityReportError("v4 proposal baselines use different manifests")
    if (
        default.run_identity.source_sha is None
        or default.run_identity.source_sha != morphology.run_identity.source_sha
    ):
        raise QualityReportError("v4 proposal baselines use different source SHAs")
    if default.run_identity.source_snapshot != morphology.run_identity.source_snapshot:
        raise QualityReportError("v4 proposal baselines use different source snapshots")
    if default.run_identity.artifact_sha256 != morphology.run_identity.artifact_sha256:
        raise QualityReportError("v4 proposal baselines use different wheel artifacts")

    def profile(report: object, path: Path) -> dict[str, object]:
        assert hasattr(report, "diagnostics")
        diagnostics = report.diagnostics
        assert isinstance(diagnostics, dict)
        return {
            "baseline_path": str(path),
            "baseline_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "quality_floors": _floor_payload(diagnostics["aggregate"]),
            "category_floors": {
                name: _floor_payload(diagnostics["category"][name])
                for name in (
                    "agreement",
                    "inflection",
                    "punctuation",
                    "spelling",
                    "syntax",
                )
            },
            "stratum_floors": {
                name: {
                    shape: _floor_payload(diagnostics["shape_strata"][name][shape])
                    for shape in (
                        "simple-local",
                        "sentence-internal",
                        "multi-sentence",
                        "repeated-occurrence",
                        "unicode-and-case",
                        "quotation-or-literal",
                        "conflict-or-abstention",
                    )
                }
                for name in (
                    "agreement",
                    "inflection",
                    "punctuation",
                    "spelling",
                    "syntax",
                )
            },
            "performance_comparison": _performance_payload(report),
        }

    payload = {
        "schema_id": "polis.quality-threshold-proposal",
        "schema_version": 4,
        "dataset_sha256": default.dataset_sha256,
        "manifest_sha256": default.run_identity.manifest_sha256,
        "source_git_sha": default.run_identity.source_sha,
        "wheel_sha256": default.run_identity.artifact_sha256,
        "wheel_filename": args.wheel_filename,
        "source_snapshot": list(default.source_snapshot or ()),
        "profiles": {
            "default": profile(default, args.baseline),
            "morphology": profile(morphology, args.morphology_baseline),
        },
        "status": "pending_maintainer_approval",
        "enforced": False,
        "decision": None,
    }
    mode = "w" if args.replace else "x"
    with args.output.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def _validate_proposal(args: argparse.Namespace) -> None:
    proposal = load_threshold_proposal(args.proposal)
    validate_threshold_proposal(
        proposal,
        baseline_path=args.baseline,
        morphology_baseline_path=args.morphology_baseline,
    )
    if getattr(proposal, "status", None) == "approved":
        print("threshold proposal valid, approved, and enforced")
    else:
        print("threshold proposal valid and pending maintainer approval")


def run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command in {"baseline", "result"} and args.dataset_version in {
        QualityDatasetVersion.V2,
        QualityDatasetVersion.V3,
        QualityDatasetVersion.V4,
    }:
        missing = tuple(
            flag
            for flag, value in (
                ("--source-sha", args.source_sha),
                ("--profile", args.profile),
            )
            if value is None
        )
        if missing:
            label = args.dataset_version.value
            parser.error(f"{label} baseline requires {' and '.join(missing)}")
    if args.command == "result" and args.dataset_version is QualityDatasetVersion.V1:
        parser.error("result requires dataset version v2, v3, or v4")
    if args.command == "baseline" and args.dataset_version is QualityDatasetVersion.V1:
        if args.source_sha is not None or args.profile is not None:
            parser.error("source SHA and profile are reserved for v2/v3 baselines")
    try:
        if args.command in {"baseline", "result"}:
            _run_baseline(args, result_schema=args.command == "result")
        elif args.command == "propose":
            _pending_v4_proposal(args)
        elif args.command == "validate-proposal":
            _validate_proposal(args)
        else:
            from polis.evaluation.quality_comparison_v4 import compare_quality_v4

            compare_quality_v4(
                baseline_default=args.baseline_default,
                baseline_morphology=args.baseline_morphology,
                result_default=args.result_default,
                result_morphology=args.result_morphology,
                proposal=args.proposal,
                output=args.output,
                replace=args.replace,
            )
    except FileExistsError:
        print(f"error: output already exists: {args.output}", file=sys.stderr)
        return 2
    except (
        IncompleteQualityReviewError,
        NonDeterministicBaselineError,
        OSError,
        PolisError,
        QualityDatasetError,
        QualityReportError,
        QualityProfileError,
        UnsupportedRssPlatformError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(run(argv))


if __name__ == "__main__":
    main()
