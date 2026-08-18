from __future__ import annotations

import json
import sys

from polis.evaluation._quality_parsing import require_object
from polis.evaluation._quality_rules import (
    _load_json_document,
    validate_quality_dataset,
)
from polis.evaluation.quality_dataset import (
    QualityDatasetVersion,
    quality_dataset_paths,
)


def main() -> int:
    if sys.argv[1:] not in ([], ["--json"]):
        raise SystemExit("usage: validate_quality_dataset_v4.py [--json]")
    dataset_path, manifest_path = quality_dataset_paths(QualityDatasetVersion.V4)
    dataset_raw = _load_json_document(dataset_path, "quality dataset")
    manifest_raw = _load_json_document(manifest_path, "quality manifest")
    dataset = validate_quality_dataset(dataset_raw, manifest_raw)
    manifest = require_object(manifest_raw, "quality manifest")
    summary = manifest["summary"]
    result = {
        "dataset_id": dataset.id,
        "dataset_version": dataset.dataset_version,
        "case_count": len(dataset.cases),
        "canonical_sha256": dataset.canonical_sha256,
        "category_counts": {
            category: {
                "positive_findings": values["positive_findings"],
                "hard_negative_cases": values["hard_negative_cases"],
                "paired_examples": values["paired_examples"],
            }
            for category, values in summary["category"].items()
        },
        "phenomenon_counts": summary["phenomenon"],
        "role_counts": summary["kind"],
        "shape_strata": summary["shape_strata"],
    }
    if sys.argv[1:] == ["--json"]:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"{result['dataset_id']}@v{result['dataset_version']}: "
            f"{result['case_count']} cases"
        )
        print(f"canonical_sha256={result['canonical_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
