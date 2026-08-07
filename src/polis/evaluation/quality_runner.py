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
    QUALITY_DATASET_PATH,
    QUALITY_MANIFEST_PATH,
    QualityDataset,
    QualityDatasetError,
    as_evaluation_dataset,
    load_quality_dataset,
)
from polis.evaluation.quality_protocol import (
    NonDeterministicBaselineError,
    RunIdentity,
    UnsupportedRssPlatformError,
    run_quality_protocol,
)
from polis.evaluation.quality_report import (
    QualityReportError,
    load_threshold_proposal,
    validate_threshold_proposal,
    write_quality_report,
)

_ANALYZER_IDENTITY: Final = "Analyzer(AnalyzerConfig())"
_SHA256_PATTERN: Final = re.compile(r"[0-9a-f]{64}")


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m polis.evaluation.quality_runner",
        description="Run or validate the default Polis quality protocol",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser(
        "baseline", help="Measure the reviewed active dataset"
    )
    baseline.add_argument("--warmup", type=_nonnegative_integer, default=1)
    baseline.add_argument("--repetitions", type=_repetition_count, default=5)
    baseline.add_argument("--artifact-sha256", type=_artifact_sha256, required=True)
    baseline.add_argument("--output", type=Path, required=True)
    baseline.add_argument("--replace", action="store_true")

    proposal = subparsers.add_parser(
        "validate-proposal", help="Validate a pending threshold proposal"
    )
    proposal.add_argument("--baseline", type=Path, required=True)
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


def _manifest_sha256() -> str:
    return hashlib.sha256(QUALITY_MANIFEST_PATH.read_bytes()).hexdigest()


def _run_baseline(args: argparse.Namespace) -> None:
    dataset = load_quality_dataset(
        dataset_path=QUALITY_DATASET_PATH,
        manifest_path=QUALITY_MANIFEST_PATH,
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
        manifest_schema_version=1,
        manifest_sha256=_manifest_sha256(),
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
    validate_threshold_proposal(proposal, baseline_path=args.baseline)
    print("threshold proposal valid and pending maintainer approval")


def run(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
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
        UnsupportedRssPlatformError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(run(argv))


if __name__ == "__main__":
    main()
