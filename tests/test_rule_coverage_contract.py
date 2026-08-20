from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.rule_coverage_contract import (
    REQUIRED_SHAPE_STRATA,
    RuleCoverageContractError,
    _read_documented_rule_inventory,
    _validate_runtime_source_sha,
    load_rule_coverage_contract,
    validate_live_parity,
    validate_rule_coverage_contract,
)

from polis import Analyzer, AnalyzerConfig, Category
from polis.correction import policy as correction_policy

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "rule_coverage_contract.py"
RULE_TABLE_HEADER = re.compile(r"^\|\s*Źródło\s*\|\s*Kategoria\s*\|\s*Zakres\s*\|\s*$")
RULE_TABLE_ROW = re.compile(r"^\|\s*`(rule:[^`|]+)`\s*\|")


def test_rule_coverage_contract_exposes_all_required_dimensions() -> None:
    contract = load_rule_coverage_contract()

    assert contract.schema_id == "polis.rule-coverage-contract"
    assert contract.schema_version == 1
    assert contract.categories == (
        "agreement",
        "inflection",
        "punctuation",
        "spelling",
        "syntax",
    )
    assert set(contract.profiles) == {"provider-absent", "qualified-morphology"}
    assert {
        "exact-edit-precision",
        "exact-edit-recall",
        "exact-edit-f1",
        "exact-half-open-span-accuracy",
        "exact-suggestion-accuracy",
        "correct-sentence-false-alarm-rate",
        "category-counts-and-rates",
        "shape-stratum-counts-and-rates",
        "source-identity-and-behavior-consistency",
        "isolated-runtime-performance",
    } <= contract.metric_ids

    sampling = contract.data["sampling"]
    assert isinstance(sampling, dict)
    strata = sampling["shape_strata"]
    assert isinstance(strata, list)
    assert {
        item["id"]
        for item in strata
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    } == REQUIRED_SHAPE_STRATA
    assert sampling["category_applicability"]["agreement"]["simple-local"] == "required"
    assert (
        sampling["category_applicability"]["agreement"]["not_applicable_reasons"] == {}
    )
    source_governance = contract.data["source_governance"]
    assert source_governance["normative_candidate_inventory"]["schema_id"] == (
        "polis.rule-normative-candidate-inventory"
    )


def test_rule_coverage_contract_requires_all_five_category_sampling_rows() -> None:
    contract = load_rule_coverage_contract()
    sampling = contract.data["sampling"]
    assert isinstance(sampling, dict)
    categories = sampling["categories"]
    assert isinstance(categories, list)
    assert {
        item["id"]
        for item in categories
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    } == set(contract.categories)
    for item in categories:
        assert isinstance(item, dict)
        assert item["minimum_positive_expected_findings"] >= 8
        assert item["minimum_correct_hard_negative_cases"] >= 16
        assert item["minimum_phenomenon_or_family_count"] >= 3
        assert item["minimum_paired_positive_negative_examples"] >= 4
        assert item["capability_claim"]
        assert item["claim_boundary"]
        assert set(item["required_shape_strata"]) == REQUIRED_SHAPE_STRATA


def test_rule_coverage_contract_rejects_an_incomplete_fixture() -> None:
    raw = copy.deepcopy(load_rule_coverage_contract().data)
    metrics = raw["metrics"]
    assert isinstance(metrics, list)
    del metrics[0]

    with pytest.raises(RuleCoverageContractError, match="metrics must be exactly"):
        validate_rule_coverage_contract(raw)


def test_rule_coverage_contract_rejects_missing_category_sampling() -> None:
    raw = copy.deepcopy(load_rule_coverage_contract().data)
    sampling = raw["sampling"]
    assert isinstance(sampling, dict)
    categories = sampling["categories"]
    assert isinstance(categories, list)
    del categories[-1]

    with pytest.raises(
        RuleCoverageContractError, match="sampling must define agreement"
    ):
        validate_rule_coverage_contract(raw)


def test_rule_coverage_contract_rejects_semantic_policy_drift() -> None:
    raw = copy.deepcopy(load_rule_coverage_contract().data)
    sampling = raw["sampling"]
    assert isinstance(sampling, dict)
    categories = sampling["categories"]
    assert isinstance(categories, list)
    assert isinstance(categories[0], dict)
    categories[0]["minimum_positive_expected_findings"] = 1

    with pytest.raises(RuleCoverageContractError, match="below 8"):
        validate_rule_coverage_contract(raw)

    raw = copy.deepcopy(load_rule_coverage_contract().data)
    governance = raw["correction_governance"]
    assert isinstance(governance, dict)
    governance["new_family_default"] = "automatic"

    with pytest.raises(RuleCoverageContractError, match="new_family_default"):
        validate_rule_coverage_contract(raw)

    raw = copy.deepcopy(load_rule_coverage_contract().data)
    metrics = raw["metrics"]
    assert isinstance(metrics, list)
    precision = next(
        item
        for item in metrics
        if isinstance(item, dict) and item.get("id") == "exact-edit-precision"
    )
    precision["formula"] = "FN / (FN + TP)"

    with pytest.raises(RuleCoverageContractError, match="exact-edit-precision"):
        validate_rule_coverage_contract(raw)

    raw = copy.deepcopy(load_rule_coverage_contract().data)
    metrics = raw["metrics"]
    assert isinstance(metrics, list)
    precision = next(
        item
        for item in metrics
        if isinstance(item, dict) and item.get("id") == "exact-edit-precision"
    )
    precision["zero_denominator"] = "zero means no errors"

    with pytest.raises(RuleCoverageContractError, match="zero_denominator"):
        validate_rule_coverage_contract(raw)

    raw = copy.deepcopy(load_rule_coverage_contract().data)
    metrics = raw["metrics"]
    assert isinstance(metrics, list)
    precision = next(
        item
        for item in metrics
        if isinstance(item, dict) and item.get("id") == "exact-edit-precision"
    )
    precision["abstention_handling"] = "Include all abstentions in precision."

    with pytest.raises(RuleCoverageContractError, match="abstention_handling"):
        validate_rule_coverage_contract(raw)


def test_rule_coverage_contract_rejects_identity_and_parity_drift() -> None:
    raw = copy.deepcopy(load_rule_coverage_contract().data)
    profiles = raw["profiles"]
    assert isinstance(profiles, list)
    qualified = next(
        item
        for item in profiles
        if isinstance(item, dict) and item.get("id") == "qualified-morphology"
    )
    provider = qualified["provider_identity"]
    assert isinstance(provider, dict)
    provider["dictionary_notice_sha256"] = "0" * 64

    with pytest.raises(RuleCoverageContractError, match="provider identity"):
        validate_rule_coverage_contract(raw)

    raw = copy.deepcopy(load_rule_coverage_contract().data)
    relationships = raw["relationships"]
    assert isinstance(relationships, list)
    assert isinstance(relationships[0], dict)
    relationships[0]["to"] = relationships[1]["to"]

    with pytest.raises(RuleCoverageContractError, match="required edge"):
        validate_rule_coverage_contract(raw)

    raw = copy.deepcopy(load_rule_coverage_contract().data)
    source_governance = raw["source_governance"]
    assert isinstance(source_governance, dict)
    quality_artifacts = source_governance["quality_artifacts"]
    assert isinstance(quality_artifacts, dict)
    quality_artifacts["parity_rule"] = "Artifacts bind a dataset."

    with pytest.raises(RuleCoverageContractError, match="quality_artifacts parity"):
        validate_rule_coverage_contract(raw)


def test_rule_coverage_contract_rejects_non_boolean_or_duplicate_shape_values() -> None:
    raw = copy.deepcopy(load_rule_coverage_contract().data)
    raw["schema_version"] = True

    with pytest.raises(RuleCoverageContractError, match="schema_version"):
        validate_rule_coverage_contract(raw)

    raw = copy.deepcopy(load_rule_coverage_contract().data)
    sampling = raw["sampling"]
    assert isinstance(sampling, dict)
    categories = sampling["categories"]
    assert isinstance(categories, list)
    assert isinstance(categories[0], dict)
    shape_strata = categories[0]["required_shape_strata"]
    assert isinstance(shape_strata, list)
    shape_strata.append(shape_strata[0])

    with pytest.raises(RuleCoverageContractError, match="omits a required shape"):
        validate_rule_coverage_contract(raw)


def test_rule_coverage_contract_rejects_contradictory_fail_open_additions() -> None:
    raw = copy.deepcopy(load_rule_coverage_contract().data)
    metrics = raw["metrics"]
    assert isinstance(metrics, list)
    precision = next(
        item
        for item in metrics
        if isinstance(item, dict) and item.get("id") == "exact-edit-precision"
    )
    precision["zero_denominator"] += (
        " A zero denominator still permits a passing quality gate."
    )

    with pytest.raises(RuleCoverageContractError, match="canonical digest"):
        validate_rule_coverage_contract(raw)

    raw = copy.deepcopy(load_rule_coverage_contract().data)
    gates = raw["gates"]
    assert isinstance(gates, dict)
    precision_gate = gates["precision"]
    assert isinstance(precision_gate, dict)
    precision_gate["rule"] += (
        " A precision regression is permitted when aggregate recall is high."
    )

    with pytest.raises(RuleCoverageContractError, match="canonical digest"):
        validate_rule_coverage_contract(raw)


def test_rule_coverage_contract_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_id": 1, "schema_id": 2}', encoding="utf-8")

    with pytest.raises(RuleCoverageContractError, match="duplicate JSON key"):
        load_rule_coverage_contract(path)


def test_rule_coverage_contract_binds_ordered_runtime_snapshot_to_inventory() -> None:
    contract = load_rule_coverage_contract()
    analyzer = Analyzer(AnalyzerConfig())
    runtime = tuple(identity.source for identity in analyzer.source_identity_snapshot)
    documented = _documented_source_identifiers(
        (ROOT / "docs/rules.md").read_text(encoding="utf-8")
    )

    assert len(runtime) == 60
    assert len(runtime) == len(set(runtime))
    assert len(documented) == len(set(documented))
    assert runtime == documented

    snapshot = [
        {
            "source": identity.source,
            "operation": identity.operation,
            "behavior_version": identity.behavior_version,
        }
        for identity in analyzer.source_identity_snapshot
    ]
    encoded = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    source_governance = contract.data["source_governance"]
    assert isinstance(source_governance, dict)
    runtime_snapshot = source_governance["runtime_snapshot"]
    assert isinstance(runtime_snapshot, dict)
    baseline = runtime_snapshot["planning_baseline"]
    assert isinstance(baseline, dict)
    assert hashlib.sha256(encoded).hexdigest() == baseline["snapshot_sha256"]


def test_rule_coverage_contract_rejects_stale_planning_baseline_source() -> None:
    with pytest.raises(
        RuleCoverageContractError,
        match="live runtime differs from the planning baseline source SHA",
    ):
        _validate_runtime_source_sha(ROOT, "59d5a62f12d529f64b3355412d6d316a5d6eb4ae")


def test_rule_coverage_contract_rejects_missing_active_policy_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = load_rule_coverage_contract()
    monkeypatch.setattr(
        correction_policy,
        "_ACTIVE_POLICY_ENTRIES",
        correction_policy._ACTIVE_POLICY_ENTRIES[:-1],
    )

    with pytest.raises(
        RuleCoverageContractError,
        match="active entries are not exact parity",
    ):
        validate_live_parity(contract)


def test_rule_coverage_contract_rejects_complete_policy_key_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = load_rule_coverage_contract()
    first = correction_policy._ACTIVE_POLICY_ENTRIES[0]
    drifted_key = dataclasses.replace(
        first.key,
        category=Category.SPELLING,
        source_policy_version="9.9",
    )
    monkeypatch.setattr(
        correction_policy,
        "_ACTIVE_POLICY_ENTRIES",
        (dataclasses.replace(first, key=drifted_key),)
        + correction_policy._ACTIVE_POLICY_ENTRIES[1:],
    )

    with pytest.raises(
        RuleCoverageContractError,
        match="active entries are not exact parity",
    ):
        validate_live_parity(contract)


def test_rule_coverage_contract_rejects_quality_source_sha_drift(
    tmp_path: Path,
) -> None:
    contract = load_rule_coverage_contract()
    for relative in (
        "docs/rules.md",
        "docs/quality-comparison-v3.json",
        "docs/quality-baseline-v3-default.json",
        "docs/quality-baseline-v3-morphology.json",
        "docs/quality-result-v3-default.json",
        "docs/quality-result-v3-morphology.json",
        "docs/project/rule-coverage-quality-artifact-provenance-v1.json",
        "docs/project/rule-coverage-normative-candidate-inventory-v1.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    result_path = tmp_path / "docs/quality-result-v3-default.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["source"]["git_sha"] = "0" * 40
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    comparison_path = tmp_path / "docs/quality-comparison-v3.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison["profiles"]["default"]["result_sha256"] = hashlib.sha256(
        result_path.read_bytes()
    ).hexdigest()
    comparison_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(RuleCoverageContractError, match="quality comparison digest"):
        validate_live_parity(contract, root=tmp_path)


def test_rule_coverage_contract_rejects_inventory_category_or_scope_drift(
    tmp_path: Path,
) -> None:
    contract = load_rule_coverage_contract()
    for relative in (
        "docs/rules.md",
        "docs/quality-comparison-v3.json",
        "docs/quality-baseline-v3-default.json",
        "docs/quality-baseline-v3-morphology.json",
        "docs/quality-result-v3-default.json",
        "docs/quality-result-v3-morphology.json",
        "docs/project/rule-coverage-quality-artifact-provenance-v1.json",
        "docs/project/rule-coverage-normative-candidate-inventory-v1.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    inventory_path = tmp_path / "docs/rules.md"
    inventory = inventory_path.read_text(encoding="utf-8")
    inventory = inventory.replace(
        "| `rule:agreement.copula` | `agreement` |",
        "| `rule:agreement.copula` | `spelling` |",
        1,
    )
    inventory_path.write_text(inventory, encoding="utf-8")

    with pytest.raises(
        RuleCoverageContractError,
        match="category or scope digest",
    ):
        validate_live_parity(contract, root=tmp_path)


def test_rule_coverage_contract_rejects_malformed_inventory_row(
    tmp_path: Path,
) -> None:
    contract = load_rule_coverage_contract()
    for relative in (
        "docs/rules.md",
        "docs/quality-comparison-v3.json",
        "docs/quality-baseline-v3-default.json",
        "docs/quality-baseline-v3-morphology.json",
        "docs/quality-result-v3-default.json",
        "docs/quality-result-v3-morphology.json",
        "docs/project/rule-coverage-quality-artifact-provenance-v1.json",
        "docs/project/rule-coverage-normative-candidate-inventory-v1.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    inventory_path = tmp_path / "docs/rules.md"
    inventory = inventory_path.read_text(encoding="utf-8")
    inventory = inventory.replace(
        "| --- | --- | --- |\n",
        "| --- | --- | --- |\n"
        "| malformed inventory row | changed | silently ignored |\n",
        1,
    )
    inventory_path.write_text(inventory, encoding="utf-8")

    with pytest.raises(
        RuleCoverageContractError,
        match="malformed maintained rule inventory row",
    ):
        validate_live_parity(contract, root=tmp_path)


def test_rule_coverage_contract_rejects_inventory_extra_column(tmp_path: Path) -> None:
    inventory_path = tmp_path / "rules.md"
    inventory = (ROOT / "docs/rules.md").read_text(encoding="utf-8")
    inventory = inventory.replace(
        "| `rule:agreement.copula` | `agreement` |",
        "| `rule:agreement.copula` | `agreement` | scope | unexpected-column |",
        1,
    )
    inventory_path.write_text(inventory, encoding="utf-8")

    with pytest.raises(
        RuleCoverageContractError,
        match="malformed maintained rule inventory row",
    ):
        _read_documented_rule_inventory(inventory_path)


def test_rule_coverage_contract_accepts_escaped_inventory_pipe(
    tmp_path: Path,
) -> None:
    inventory_path = tmp_path / "rules.md"
    inventory_path.write_text(
        "\n".join(
            (
                "| Źródło | Kategoria | Zakres |",
                "| --- | --- | --- |",
                r"| `rule:test` | `spelling` | scope \| literal |",
                "",
            )
        ),
        encoding="utf-8",
    )

    assert _read_documented_rule_inventory(inventory_path) == (
        {"source": "rule:test", "category": "spelling", "scope": "scope | literal"},
    )


def test_rule_coverage_contract_rejects_quality_comparison_metadata_drift(
    tmp_path: Path,
) -> None:
    contract = load_rule_coverage_contract()
    for relative in (
        "docs/rules.md",
        "docs/quality-comparison-v3.json",
        "docs/quality-baseline-v3-default.json",
        "docs/quality-baseline-v3-morphology.json",
        "docs/quality-result-v3-default.json",
        "docs/quality-result-v3-morphology.json",
        "docs/project/rule-coverage-quality-artifact-provenance-v1.json",
        "docs/project/rule-coverage-normative-candidate-inventory-v1.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    comparison_path = tmp_path / "docs/quality-comparison-v3.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison["aggregate_verdict"] = "pass"
    comparison_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(RuleCoverageContractError, match="quality comparison digest"):
        validate_live_parity(contract, root=tmp_path)


def test_rule_coverage_contract_cli_validates_and_fails_closed(
    tmp_path: Path,
) -> None:
    for relative in (
        "docs/project/rule-coverage-contract-v1.json",
        "docs/rules.md",
        "docs/quality-comparison-v3.json",
        "docs/quality-baseline-v3-default.json",
        "docs/quality-baseline-v3-morphology.json",
        "docs/quality-result-v3-default.json",
        "docs/quality-result-v3-morphology.json",
        "docs/project/rule-coverage-quality-artifact-provenance-v1.json",
        "docs/project/rule-coverage-normative-candidate-inventory-v1.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    command = [sys.executable, str(VALIDATOR), "--root", str(tmp_path)]
    valid = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )
    assert valid.returncode == 0, valid.stderr
    assert valid.stdout == "rule coverage contract is valid\n"

    inventory_path = tmp_path / "docs/rules.md"
    inventory = inventory_path.read_text(encoding="utf-8")
    inventory_path.write_text(
        inventory.replace(
            "| `rule:agreement.copula` | `agreement` |",
            "| `rule:agreement.copula` | `spelling` |",
            1,
        ),
        encoding="utf-8",
    )
    drifted = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )
    assert drifted.returncode != 0
    assert "rule coverage contract validation failed" in drifted.stderr


def _documented_source_identifiers(markdown: str) -> tuple[str, ...]:
    rows = iter(markdown.splitlines())
    for row in rows:
        if RULE_TABLE_HEADER.fullmatch(row.strip()):
            break
    else:
        return ()

    identifiers: list[str] = []
    for row in rows:
        if not row.strip():
            break
        match = RULE_TABLE_ROW.match(row.strip())
        if match is not None:
            identifiers.append(match.group(1))
    return tuple(identifiers)
