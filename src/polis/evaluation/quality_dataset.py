"""Load the active, reviewed quality-development dataset."""

from __future__ import annotations

from polis.evaluation._quality_rules import (
    load_quality_dataset as load_quality_dataset,
)
from polis.evaluation._quality_rules import (
    validate_quality_dataset as validate_quality_dataset,
)
from polis.evaluation._quality_types import (
    QUALITY_DATASET_PATH as QUALITY_DATASET_PATH,
)
from polis.evaluation._quality_types import (
    QUALITY_MANIFEST_PATH as QUALITY_MANIFEST_PATH,
)
from polis.evaluation._quality_types import (
    JsonValue as JsonValue,
)
from polis.evaluation._quality_types import (
    QualityCase as QualityCase,
)
from polis.evaluation._quality_types import (
    QualityCaseKind as QualityCaseKind,
)
from polis.evaluation._quality_types import (
    QualityDataset,
)
from polis.evaluation._quality_types import (
    QualityDatasetError as QualityDatasetError,
)
from polis.evaluation._quality_types import (
    QualityDatasetVersion as QualityDatasetVersion,
)
from polis.evaluation._quality_types import (
    QualityExpectedFinding as QualityExpectedFinding,
)
from polis.evaluation._quality_types import (
    QualityFeature as QualityFeature,
)
from polis.evaluation._quality_types import (
    QualityPhenomenon as QualityPhenomenon,
)
from polis.evaluation._quality_types import (
    QualityReview as QualityReview,
)
from polis.evaluation._quality_types import (
    quality_dataset_paths as quality_dataset_paths,
)
from polis.evaluation.dataset import EvaluationCase, EvaluationDataset, ExpectedFinding


def as_evaluation_dataset(dataset: QualityDataset) -> EvaluationDataset:
    """Convert active cases to the stable value types consumed by metrics."""

    return EvaluationDataset(
        schema_version=dataset.schema_version,
        id=dataset.id,
        cases=tuple(
            EvaluationCase(
                id=case.id,
                outcome="incorrect" if case.findings else "correct",
                text=case.text,
                findings=tuple(
                    ExpectedFinding(
                        category=finding.category,
                        start=finding.start,
                        end=finding.end,
                        original=finding.original,
                        suggestion=finding.suggestion,
                        rationale=finding.rationale,
                    )
                    for finding in case.findings
                ),
            )
            for case in dataset.cases
        ),
        source=f"quality:{dataset.id}@{dataset.dataset_version}",
        canonical_hash=dataset.canonical_sha256,
    )
