"""Evaluation datasets, metrics, and quality regressions."""

from polis.evaluation.dataset import EvaluationDataset, load_dataset, validate_dataset
from polis.evaluation.metrics import (
    BaselineResult,
    QualityCounts,
    evaluate_baseline,
    findings_snapshot_for_run,
)
from polis.evaluation.safety_corpus import (
    CORPUS_ID as SAFETY_CORPUS_ID,
)
from polis.evaluation.safety_corpus import (
    REVIEW_CHECKLIST_VERSION as SAFETY_REVIEW_CHECKLIST_VERSION,
)
from polis.evaluation.safety_corpus import (
    assert_no_cross_corpus_leakage,
    load_safety_corpus_json,
    load_safety_corpus_xml,
    safety_corpus_digest,
    safety_entity_catalog_ids,
    select_safety_cases_for_purpose,
    validate_safety_corpus,
)

__all__ = [
    "BaselineResult",
    "EvaluationDataset",
    "QualityCounts",
    "SAFETY_CORPUS_ID",
    "SAFETY_REVIEW_CHECKLIST_VERSION",
    "assert_no_cross_corpus_leakage",
    "evaluate_baseline",
    "findings_snapshot_for_run",
    "load_dataset",
    "load_safety_corpus_json",
    "load_safety_corpus_xml",
    "safety_corpus_digest",
    "safety_entity_catalog_ids",
    "select_safety_cases_for_purpose",
    "validate_dataset",
    "validate_safety_corpus",
]
