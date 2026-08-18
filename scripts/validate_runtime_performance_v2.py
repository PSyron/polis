from __future__ import annotations

import argparse
from pathlib import Path

from polis.evaluation.quality_dataset import (
    QUALITY_MANIFEST_PATH,
    QualityDatasetVersion,
    load_quality_dataset,
)
from polis.evaluation.quality_performance_artifact import (
    file_sha256,
    load_runtime_performance_v2,
)
from polis.evaluation.quality_report_models import PerformanceArtifactBinding


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate one isolated runtime-performance-v2 artifact"
    )
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--profile", choices=("default", "morphology"), required=True)
    parser.add_argument("--role", choices=("reference", "current"), required=True)
    parser.add_argument("--dataset-id", default=None)
    parser.add_argument("--dataset-sha256", default=None)
    parser.add_argument("--manifest-sha256", default=None)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--wheel-sha256", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--worker-sha256", required=True)
    args = parser.parse_args()

    dataset = load_quality_dataset(version=QualityDatasetVersion.V4)
    dataset_id = args.dataset_id or dataset.id
    dataset_sha256 = args.dataset_sha256 or dataset.canonical_sha256
    manifest_sha256 = args.manifest_sha256 or file_sha256(QUALITY_MANIFEST_PATH)
    digest = file_sha256(args.artifact)
    binding = PerformanceArtifactBinding(
        path=str(args.artifact),
        sha256=digest,
        protocol_version=2,
        protocol_sha256=args.protocol_sha256,
        worker_sha256=args.worker_sha256,
    )
    load_runtime_performance_v2(
        args.artifact,
        binding=binding,
        profile=args.profile,
        expected_dataset_id=dataset_id,
        expected_dataset_sha256=dataset_sha256,
        expected_manifest_sha256=manifest_sha256,
        expected_source_sha=args.source_sha,
        expected_wheel_sha256=args.wheel_sha256,
        expected_role=args.role,
    )
    print(f"valid runtime-performance-v2 artifact: {args.artifact}")


if __name__ == "__main__":
    main()
