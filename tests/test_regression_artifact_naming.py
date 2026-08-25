from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from scripts.validate_evaluation_artifact_inventory import validate_inventory

from polis.evaluation.quality_report import (
    load_quality_comparison,
    load_quality_report,
    load_quality_result,
    load_threshold_proposal,
)

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "project" / "evaluation-artifact-inventory.json"

BASELINE_ARTIFACTS = (
    "v1",
    "v2-default",
    "v2-morphology",
    "v3-default",
    "v3-morphology",
    "v4-default",
    "v4-morphology",
)
RESULT_ARTIFACTS = (
    "v2-default",
    "v2-morphology",
    "v3-default",
    "v3-morphology",
    "v4-default",
    "v4-morphology",
    "wave0-default",
    "wave0-morphology",
)


def test_canonical_development_measurements_use_regression_namespace() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    assert inventory["schema_id"] == "polis.evaluation-artifact-inventory"
    assert inventory["schema_version"] == 2
    assert inventory["legacy_alias_policy"]

    for prefix, suffixes, schema_id in (
        ("regression-baseline", BASELINE_ARTIFACTS, "polis.regression-baseline"),
        ("regression-result", RESULT_ARTIFACTS, "polis.regression-result"),
        (
            "regression-comparison",
            ("v2", "v3", "v4"),
            "polis.regression-comparison",
        ),
        (
            "regression-threshold-proposal",
            ("v1", "v2", "v3", "v4"),
            "polis.regression-threshold-proposal",
        ),
    ):
        for suffix in suffixes:
            path = ROOT / "docs" / f"{prefix}-{suffix}.json"
            assert path.is_file()
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert payload["schema_id"] == schema_id


def test_f1_payloads_are_still_measurements_of_the_development_suite() -> None:
    for path in (
        ROOT / "docs" / "regression-baseline-v4-default.json",
        ROOT / "docs" / "regression-baseline-v4-morphology.json",
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["dataset"]["id"] == "polis_v4_quality_development"
        assert payload["quality"]["f1"] == 1.0


def test_inventory_validates_alias_parity_and_canonical_parsers_read_new_names() -> (
    None
):
    assert validate_inventory(ROOT) == []

    baseline = load_quality_report(ROOT / "docs/regression-baseline-v4-default.json")
    result = load_quality_result(ROOT / "docs/regression-result-v4-default.json")
    comparison = load_quality_comparison(ROOT / "docs/regression-comparison-v4.json")
    proposal = load_threshold_proposal(
        ROOT / "docs/regression-threshold-proposal-v4.json"
    )

    assert baseline.quality_f1 == 1.0
    assert result.quality_f1 == 1.0
    assert comparison.aggregate_verdict == "pass"
    assert proposal.enforced is True


def test_canonical_comparisons_bind_canonical_proposal_serialization() -> None:
    for version in ("v2", "v3", "v4"):
        proposal_path = ROOT / f"docs/regression-threshold-proposal-{version}.json"
        comparison_path = ROOT / f"docs/regression-comparison-{version}.json"
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        canonical_proposal = (
            json.dumps(proposal, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")

        assert comparison["proposal_path"] == str(proposal_path.relative_to(ROOT))
        assert (
            comparison["proposal_sha256"]
            == hashlib.sha256(canonical_proposal).hexdigest()
        )


def test_inventory_rejects_a_canonical_comparison_with_stale_proposal_hash(
    tmp_path: Path,
) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    comparison_path = tmp_path / "docs" / "regression-comparison-v4.json"
    legacy_comparison_path = tmp_path / "docs" / "quality-comparison-v4.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    legacy_comparison = json.loads(legacy_comparison_path.read_text(encoding="utf-8"))
    comparison["proposal_sha256"] = legacy_comparison["proposal_sha256"]
    comparison_path.write_text(
        json.dumps(comparison, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    errors = validate_inventory(tmp_path)

    assert any("canonical proposal SHA-256 mismatch" in error for error in errors)


def test_quality_baseline_document_disclaims_product_quality() -> None:
    text = (ROOT / "docs" / "quality-baseline.md").read_text(encoding="utf-8")

    assert "is not a product-quality measurement" in text


def test_inventory_rejects_mutating_a_historical_alias_pair(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    canonical_path = tmp_path / "docs" / "regression-baseline-v4-default.json"
    legacy_path = tmp_path / "docs" / "quality-baseline-v4-default.json"

    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    canonical["quality"]["f1"] = 0.5
    legacy["quality"]["f1"] = 0.5
    canonical_path.write_text(
        json.dumps(canonical, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    legacy_path.write_text(
        json.dumps(legacy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    errors = validate_inventory(tmp_path)

    assert any("legacy artifact bytes changed" in error for error in errors)


@pytest.mark.parametrize("field", ("canonical", "legacy"))
@pytest.mark.parametrize("escape_kind", ("traversal", "absolute", "symlink"))
def test_inventory_rejects_alias_paths_outside_docs(
    tmp_path: Path, field: str, escape_kind: str
) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    inventory_path = (
        tmp_path / "docs" / "project" / "evaluation-artifact-inventory.json"
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    alias = inventory["aliases"][0]
    source_path = ROOT / alias[field]
    outside_path = tmp_path.parent / f"outside-{field}.json"
    outside_path.write_bytes(source_path.read_bytes())

    if escape_kind == "traversal":
        escaped_path = f"docs/../../{outside_path.name}"
    elif escape_kind == "absolute":
        escaped_path = str(outside_path)
    else:
        link_name = (
            "regression-baseline-v1-escape.json"
            if field == "canonical"
            else "quality-baseline-v1-escape.json"
        )
        link_path = tmp_path / "docs" / link_name
        link_path.symlink_to(outside_path)
        escaped_path = str(link_path.relative_to(tmp_path))
    alias[field] = escaped_path
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    errors = validate_inventory(tmp_path, inventory_path)

    assert any(f"{field} path escapes root/docs" in error for error in errors)


@pytest.mark.parametrize("escape_kind", ("traversal", "absolute", "symlink"))
def test_inventory_rejects_proposal_paths_outside_docs(
    tmp_path: Path, escape_kind: str
) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    comparison_path = tmp_path / "docs" / "regression-comparison-v4.json"
    proposal_path = tmp_path / "docs" / "regression-threshold-proposal-v4.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    outside_path = tmp_path.parent / "outside-proposal.json"
    outside_path.write_bytes(proposal_path.read_bytes())

    if escape_kind == "traversal":
        escaped_path = f"docs/../../{outside_path.name}"
    elif escape_kind == "absolute":
        escaped_path = str(outside_path)
    else:
        link_path = tmp_path / "docs" / "regression-threshold-proposal-v4-escape.json"
        link_path.symlink_to(outside_path)
        escaped_path = str(link_path.relative_to(tmp_path))
    comparison["proposal_path"] = escaped_path
    comparison["proposal_sha256"] = hashlib.sha256(
        proposal_path.read_bytes()
    ).hexdigest()
    comparison_path.write_text(
        json.dumps(comparison, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    errors = validate_inventory(tmp_path)

    assert any("proposal_path escapes root/docs" in error for error in errors)


@pytest.mark.parametrize("kind", (["baseline"], {"value": "baseline"}))
def test_inventory_rejects_non_scalar_alias_kind(
    tmp_path: Path, kind: list[str] | dict[str, str]
) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    inventory_path = (
        tmp_path / "docs" / "project" / "evaluation-artifact-inventory.json"
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["aliases"][0]["kind"] = kind
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    errors = validate_inventory(tmp_path, inventory_path)

    assert any("artifact alias 0 has an unknown kind" in error for error in errors)


@pytest.mark.parametrize("field", ("canonical", "legacy"))
@pytest.mark.parametrize(
    "malformed_path", ("docs/\x00escape.json", "docs/\ud800escape.json")
)
def test_inventory_rejects_malformed_alias_paths(
    tmp_path: Path, field: str, malformed_path: str
) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    inventory_path = (
        tmp_path / "docs" / "project" / "evaluation-artifact-inventory.json"
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["aliases"][0][field] = malformed_path
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    errors = validate_inventory(tmp_path, inventory_path)

    assert any(f"{field} path escapes root/docs" in error for error in errors)


@pytest.mark.parametrize(
    "malformed_path", ("docs/\x00escape.json", "docs/\ud800escape.json")
)
def test_inventory_rejects_malformed_proposal_paths(
    tmp_path: Path, malformed_path: str
) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    comparison_path = tmp_path / "docs" / "regression-comparison-v4.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison["proposal_path"] = malformed_path
    comparison_path.write_text(
        json.dumps(comparison, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    errors = validate_inventory(tmp_path)

    assert any("proposal_path escapes root/docs" in error for error in errors)


def _adr_evaluation_exports() -> tuple[str, ...]:
    text = (
        ROOT
        / "docs"
        / "architecture"
        / "decisions"
        / "0023-evaluation-namespace-1-0.md"
    ).read_text(encoding="utf-8")
    block = text.split("```python\n(", maxsplit=1)[1].split("\n)\n```", maxsplit=1)[0]
    value = ast.literal_eval("(" + block + "\n)")
    assert isinstance(value, tuple)
    assert all(isinstance(item, str) for item in value)
    return value


def test_evaluation_exports_match_adr_0023_byte_for_byte() -> None:
    import polis.evaluation as evaluation

    assert tuple(evaluation.__all__) == _adr_evaluation_exports()
