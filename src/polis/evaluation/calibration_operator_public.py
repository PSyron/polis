from __future__ import annotations

import hashlib
import json

from polis.evaluation._quality_rules import validate_quality_dataset
from polis.evaluation.calibration_json import (
    exact_object,
    fail,
    strict_integer,
    strict_string,
)
from polis.evaluation.calibration_models import (
    CalibrationCase,
    CalibrationContractError,
    CalibrationDataset,
    ExpectedFinding,
    JsonValue,
)
from polis.evaluation.calibration_operator_io import _SecureRepository
from polis.evaluation.calibration_overlap import DatasetLike
from polis.evaluation.dataset import EvaluationDataset, validate_dataset
from polis.evaluation.quality_dataset import as_evaluation_dataset


def _from_evaluation(dataset: EvaluationDataset) -> CalibrationDataset:
    cases = tuple(
        CalibrationCase(
            case.id,
            "error" if case.findings else "correct",
            "public:maintained",
            case.text,
            tuple(
                ExpectedFinding(
                    "public:maintained",
                    finding.category,
                    finding.start,
                    finding.end,
                    finding.original,
                    finding.suggestion,
                )
                for finding in case.findings
            ),
        )
        for case in dataset.cases
    )
    return CalibrationDataset(dataset.id, cases, dataset.canonical_hash)


def _json(raw: bytes) -> JsonValue:
    try:
        value: JsonValue = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationContractError("public reference is invalid JSON") from error
    return value


def _conservative(raw: bytes) -> CalibrationDataset:
    fields = frozenset(
        {
            "schema_version",
            "review_status",
            "cases",
        }
    )
    root = exact_object(_json(raw), fields, "public fixture")
    values = root["cases"]
    if root["schema_version"] != 1 or not isinstance(values, list):
        fail("public fixture identity is invalid")
    cases: list[CalibrationCase] = []
    base_case_fields = frozenset(
        {
            "id",
            "kind",
            "rule_source",
            "category",
            "input",
            "expected_issues",
        }
    )
    abstain_fields = frozenset({"id", "kind", "input", "expected_issues", "reason"})
    finding_fields = frozenset({"category", "start", "end", "replacement", "source"})
    for value in values:
        if not isinstance(value, dict):
            fail("public case must contain exactly the required fields")
        kind = strict_string(value.get("kind"), "public case kind")
        if kind == "error":
            fields = frozenset(value)
            if fields == base_case_fields | {"application", "expected_output"}:
                if value["application"] is not True:
                    fail("public application marker is invalid")
            elif fields == base_case_fields | {"overlap"}:
                if value["overlap"] is not True:
                    fail("public overlap marker is invalid")
            else:
                fail("public case must contain exactly the required fields")
            case = exact_object(value, fields, "public case")
        elif kind == "correct":
            case = exact_object(value, base_case_fields, "public case")
        elif kind == "abstain":
            case = exact_object(value, abstain_fields, "public case")
        else:
            fail("public case kind is invalid")
        text = strict_string(case["input"], "public input")
        issues = case["expected_issues"]
        if not isinstance(issues, list):
            fail("public expected issues must be a list")
        findings: list[ExpectedFinding] = []
        for issue in issues:
            finding = exact_object(issue, finding_fields, "public finding")
            start = strict_integer(finding["start"], "public finding start")
            end = strict_integer(finding["end"], "public finding end")
            findings.append(
                ExpectedFinding(
                    strict_string(finding["source"], "public finding source"),
                    strict_string(finding["category"], "public finding category"),
                    start,
                    end,
                    text[start:end],
                    strict_string(finding["replacement"], "public replacement"),
                )
            )
        cases.append(
            CalibrationCase(
                strict_string(case["id"], "public case id"),
                "error" if findings else "correct",
                (
                    strict_string(case["rule_source"], "public primary source")
                    if kind != "abstain"
                    else "public:maintained"
                ),
                text,
                tuple(findings),
            )
        )
    return CalibrationDataset(
        "conservative-corrections-v1",
        tuple(cases),
        hashlib.sha256(raw).hexdigest(),
    )


def _public_references(repo: _SecureRepository) -> tuple[DatasetLike, ...]:
    quality_root = ("src", "polis", "evaluation", "datasets", "quality", "v1")
    quality_raw = repo.read((*quality_root, "cases.json"), expected_mode=0o644)
    quality_manifest = repo.read((*quality_root, "manifest.json"), expected_mode=0o644)
    quality = as_evaluation_dataset(
        validate_quality_dataset(_json(quality_raw), _json(quality_manifest))
    )
    stable_raw = repo.read(
        ("src", "polis", "evaluation", "datasets", "v1", "cases.json"),
        expected_mode=0o644,
    )
    stable = validate_dataset(_json(stable_raw), source="public-maintained")
    conservative = repo.read(
        ("tests", "fixtures", "v1", "conservative_corrections.json"),
        expected_mode=0o644,
    )
    return (
        _from_evaluation(quality),
        _from_evaluation(stable),
        _conservative(conservative),
    )
