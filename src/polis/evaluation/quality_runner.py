from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from polis import Analyzer, AnalyzerConfig
from polis.core import PolisError
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
    load_threshold_proposal,
    validate_threshold_proposal,
    write_quality_report,
)
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

    baseline = subparsers.add_parser(
        "baseline", help="Measure the reviewed active dataset", allow_abbrev=False
    )
    baseline.add_argument("--warmup", type=_nonnegative_integer, default=1)
    baseline.add_argument("--repetitions", type=_repetition_count, default=5)
    baseline.add_argument(
        "--dataset-version",
        type=QualityDatasetVersion,
        choices=tuple(QualityDatasetVersion),
        default=QualityDatasetVersion.V1,
    )
    baseline.add_argument("--artifact-sha256", type=_artifact_sha256, required=True)
    baseline.add_argument("--source-sha", type=_source_sha)
    baseline.add_argument(
        "--profile", type=InstallationProfile, choices=tuple(InstallationProfile)
    )
    baseline.add_argument("--output", type=Path, required=True)
    baseline.add_argument("--replace", action="store_true")

    proposal = subparsers.add_parser(
        "validate-proposal",
        help="Validate a pending threshold proposal",
        allow_abbrev=False,
    )
    proposal.add_argument("--baseline", type=Path, required=True)
    proposal.add_argument("--morphology-baseline", type=Path)
    proposal.add_argument("--proposal", type=Path, required=True)
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


def _run_baseline(args: argparse.Namespace) -> None:
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
    result = run_quality_protocol(
        dataset=as_evaluation_dataset(dataset),
        analyzer=lambda text: tuple(analyzer.analyze(text).issues),
        run_identity=identity,
        warmup_repetitions=args.warmup,
        measured_repetitions=args.repetitions,
    )
    write_quality_report(result, args.output, replace=args.replace)


def _validate_proposal(args: argparse.Namespace) -> None:
    proposal = load_threshold_proposal(args.proposal)
    validate_threshold_proposal(
        proposal,
        baseline_path=args.baseline,
        morphology_baseline_path=args.morphology_baseline,
    )
    print("threshold proposal valid and pending maintainer approval")


def run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "baseline" and args.dataset_version is QualityDatasetVersion.V2:
        missing = tuple(
            flag
            for flag, value in (
                ("--source-sha", args.source_sha),
                ("--profile", args.profile),
            )
            if value is None
        )
        if missing:
            parser.error(f"v2 baseline requires {' and '.join(missing)}")
    if args.command == "baseline" and args.dataset_version is QualityDatasetVersion.V1:
        if args.source_sha is not None or args.profile is not None:
            parser.error("source SHA and profile are reserved for v2 baselines")
    try:
        if args.command == "baseline":
            _run_baseline(args)
        else:
            _validate_proposal(args)
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
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(run(argv))


if __name__ == "__main__":
    main()
