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
import scripts.rule_coverage_contract as rule_coverage_contract
from scripts.rule_coverage_contract import (
    REQUIRED_SHAPE_STRATA,
    RuleCoverageContractError,
    _load_target_runtime_state,
    _read_documented_rule_inventory,
    _validate_runtime_source_sha,
    load_rule_coverage_contract,
    validate_live_parity,
    validate_rule_coverage_contract,
)

from polis import Analyzer, AnalyzerConfig

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


def test_rule_coverage_contract_keeps_digest_strict_after_derived_bindings_change() -> (
    None
):
    raw = copy.deepcopy(load_rule_coverage_contract().data)
    source_governance = raw["source_governance"]
    assert isinstance(source_governance, dict)
    baseline = source_governance["runtime_snapshot"]["planning_baseline"]
    assert isinstance(baseline, dict)
    baseline["full_sha"] = "1" * 40
    baseline["snapshot_sha256"] = "2" * 64
    inventory = source_governance["maintained_rule_inventory"]
    assert isinstance(inventory, dict)
    inventory["rows_sha256"] = "3" * 64
    correction_governance = raw["correction_governance"]
    assert isinstance(correction_governance, dict)
    correction_governance["automatic_promotion"] += " Permissive drift."

    with pytest.raises(RuleCoverageContractError, match="canonical digest"):
        validate_rule_coverage_contract(raw)


def test_rule_coverage_contract_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_id": 1, "schema_id": 2}', encoding="utf-8")

    with pytest.raises(RuleCoverageContractError, match="duplicate JSON key"):
        load_rule_coverage_contract(path)


@pytest.mark.parametrize(
    ("package_source", "message"),
    [
        ('raise RuntimeError("fixture failure")\n', "subprocess failed"),
        (
            "print('noise')\n"
            "class AnalyzerConfig: pass\n"
            "class Analyzer:\n"
            "    def __init__(self, config): pass\n"
            "    source_identity_snapshot = ()\n",
            "invalid JSON",
        ),
        (
            "from types import SimpleNamespace\n"
            "class AnalyzerConfig: pass\n"
            "class Analyzer:\n"
            "    def __init__(self, config): pass\n"
            "    source_identity_snapshot = "
            "(SimpleNamespace(source=1, operation='op', behavior_version='1'),)\n",
            "source must be a non-empty string",
        ),
    ],
)
def test_target_runtime_state_fails_closed_on_invalid_subprocess_result(
    tmp_path: Path,
    package_source: str,
    message: str,
) -> None:
    package_path = tmp_path / "src/polis/__init__.py"
    package_path.parent.mkdir(parents=True)
    package_path.write_text(package_source, encoding="utf-8")
    policy_path = tmp_path / "src/polis/correction/policy.py"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        "SOURCE_POLICY_VERSION = '1.2'\n_ACTIVE_POLICY_ENTRIES = ()\n",
        encoding="utf-8",
    )

    with pytest.raises(RuleCoverageContractError, match=message):
        _load_target_runtime_state(tmp_path)


@pytest.mark.parametrize(
    ("stdout", "message"),
    [
        ("[]", "target runtime state must be an object"),
        (
            json.dumps(
                {
                    "source_identities": [],
                    "source_policy_version": "1.2",
                    "active_policy_entries": [],
                    "unexpected": True,
                }
            ),
            "target runtime state fields mismatch",
        ),
        (
            json.dumps(
                {
                    "source_identities": [],
                    "source_policy_version": 1,
                    "active_policy_entries": [],
                }
            ),
            "source_policy_version must be a non-empty string",
        ),
        (
            json.dumps(
                {
                    "source_identities": [],
                    "source_policy_version": "1.2",
                    "active_policy_entries": [
                        {
                            "source": "rule:agreement.copula",
                            "category": 1,
                            "operation": "replace.copula_form",
                            "behavior_version": "agreement-copula/1.0",
                            "source_policy_version": "1.2",
                        }
                    ],
                }
            ),
            "category must be a non-empty string",
        ),
    ],
)
def test_target_runtime_state_strictly_parses_json_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stdout: str,
    message: str,
) -> None:
    result = subprocess.CompletedProcess(
        args=(), returncode=0, stdout=stdout, stderr=""
    )
    monkeypatch.setattr(
        rule_coverage_contract.subprocess,
        "run",
        lambda *_args, **_kwargs: result,
    )

    with pytest.raises(RuleCoverageContractError, match=message):
        _load_target_runtime_state(tmp_path)


def test_rule_coverage_contract_binds_ordered_runtime_snapshot_to_inventory() -> None:
    contract = load_rule_coverage_contract()
    analyzer = Analyzer(AnalyzerConfig())
    runtime = tuple(identity.source for identity in analyzer.source_identity_snapshot)
    documented = _documented_source_identifiers(
        (ROOT / "docs/rules.md").read_text(encoding="utf-8")
    )

    assert len(runtime) == 63
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
    runtime_state = _load_target_runtime_state(ROOT)
    monkeypatch.setattr(
        rule_coverage_contract,
        "_load_target_runtime_state",
        lambda root: dataclasses.replace(
            runtime_state,
            active_policy_entries=runtime_state.active_policy_entries[:-1],
        ),
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
    runtime_state = _load_target_runtime_state(ROOT)
    first = runtime_state.active_policy_entries[0]
    drifted_entry = dataclasses.replace(
        first,
        category="spelling",
        source_policy_version="9.9",
    )
    monkeypatch.setattr(
        rule_coverage_contract,
        "_load_target_runtime_state",
        lambda root: dataclasses.replace(
            runtime_state,
            active_policy_entries=(drifted_entry,)
            + runtime_state.active_policy_entries[1:],
        ),
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


def test_rule_coverage_contract_cli_refreshes_and_validates_digest_fields(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    subprocess.run(
        ["git", "clone", "--no-local", str(ROOT), str(repository)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    runtime_path = repository / "src/polis/rules/spelling.py"
    runtime_source = runtime_path.read_text(encoding="utf-8")
    old_behavior_version = 'return "spelling-co-niemiara/1.0"'
    assert old_behavior_version in runtime_source
    runtime_path.write_text(
        runtime_source.replace(
            old_behavior_version,
            'return "spelling-co-niemiara/1.1"',
            1,
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Polis test",
            "-c",
            "user.email=polis-test@example.invalid",
            "commit",
            "-am",
            "test: commit runtime source fixture",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )

    pycache_path = repository / "src/polis/rules/__pycache__/generated.pyc"
    pycache_path.parent.mkdir(parents=True)
    pycache_path.write_bytes(b"generated bytecode fixture")
    contract_path = repository / "docs/project/rule-coverage-contract-v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    planning_baseline = contract["source_governance"]["runtime_snapshot"][
        "planning_baseline"
    ]
    planning_baseline["full_sha"] = "0" * 40
    planning_baseline["snapshot_sha256"] = "0" * 64
    contract["source_governance"]["maintained_rule_inventory"]["rows_sha256"] = "0" * 64
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    pre_refresh_contract = contract_path.read_bytes()
    assert pre_refresh_contract.endswith(b"\n")

    command = [
        sys.executable,
        str(VALIDATOR),
        "--root",
        str(repository),
        "--refresh",
    ]
    refreshed = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )
    assert refreshed.returncode == 0, refreshed.stderr
    validated = subprocess.run(
        command[:-1], cwd=ROOT, text=True, capture_output=True, check=False
    )
    assert validated.returncode == 0, validated.stderr
    assert validated.stdout == "rule coverage contract is valid\n"

    refreshed_contract_bytes = contract_path.read_bytes()
    assert refreshed_contract_bytes.endswith(b"\n")
    normalized_pre_refresh = pre_refresh_contract
    normalized_refreshed = refreshed_contract_bytes
    for field in ("full_sha", "snapshot_sha256", "rows_sha256"):
        pattern = re.compile(rf'("{field}"\s*:\s*)"([^"]+)"'.encode())
        pre_refresh_match = pattern.search(normalized_pre_refresh)
        refreshed_match = pattern.search(normalized_refreshed)
        assert pre_refresh_match is not None
        assert refreshed_match is not None
        assert pre_refresh_match.group(1) == refreshed_match.group(1)
        assert pre_refresh_match.group(2) != refreshed_match.group(2)
        normalized_pre_refresh = (
            normalized_pre_refresh[: pre_refresh_match.start(2)]
            + b"<digest>"
            + normalized_pre_refresh[pre_refresh_match.end(2) :]
        )
        normalized_refreshed = (
            normalized_refreshed[: refreshed_match.start(2)]
            + b"<digest>"
            + normalized_refreshed[refreshed_match.end(2) :]
        )
    assert normalized_refreshed == normalized_pre_refresh

    refreshed_contract = json.loads(refreshed_contract_bytes)
    source_governance = refreshed_contract["source_governance"]
    expected_full_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    assert source_governance["runtime_snapshot"]["planning_baseline"]["full_sha"] == (
        expected_full_sha
    )
    validator_snapshot = hashlib.sha256(
        json.dumps(
            [
                {
                    "source": identity.source,
                    "operation": identity.operation,
                    "behavior_version": identity.behavior_version,
                }
                for identity in Analyzer(AnalyzerConfig()).source_identity_snapshot
            ],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    target_snapshot = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import hashlib,json,sys\n"
                "sys.path.insert(0,sys.argv[1])\n"
                "from polis import Analyzer,AnalyzerConfig\n"
                "snapshot=[{'source': item.source, 'operation': item.operation, "
                "'behavior_version': item.behavior_version} for item in "
                "Analyzer(AnalyzerConfig()).source_identity_snapshot]\n"
                "encoded=json.dumps(snapshot,ensure_ascii=False,sort_keys=True,"
                "separators=(',',':')).encode('utf-8')\n"
                "print(hashlib.sha256(encoded).hexdigest())\n"
            ),
            str(repository / "src"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    assert target_snapshot != validator_snapshot
    assert (
        source_governance["runtime_snapshot"]["planning_baseline"]["snapshot_sha256"]
        == target_snapshot
    )
    assert (
        source_governance["runtime_snapshot"]["planning_baseline"]["snapshot_sha256"]
        != validator_snapshot
    )
    assert (
        source_governance["maintained_rule_inventory"]["rows_sha256"]
        == hashlib.sha256(
            json.dumps(
                [
                    dict(row)
                    for row in _read_documented_rule_inventory(
                        repository / "docs/rules.md"
                    )
                ],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )


def test_rule_coverage_contract_cli_uses_target_correction_policy(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    subprocess.run(
        ["git", "clone", "--no-local", str(ROOT), str(repository)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    policy_path = repository / "src/polis/correction/policy.py"
    policy_source = policy_path.read_text(encoding="utf-8")
    assert 'SOURCE_POLICY_VERSION: Final[str] = "1.2"' in policy_source
    policy_path.write_text(
        policy_source.replace(
            'SOURCE_POLICY_VERSION: Final[str] = "1.2"',
            'SOURCE_POLICY_VERSION: Final[str] = "9.9"',
            1,
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Polis test",
            "-c",
            "user.email=polis-test@example.invalid",
            "commit",
            "-am",
            "test: commit correction policy drift fixture",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    target_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    contract_path = repository / "docs/project/rule-coverage-contract-v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    source_governance = contract["source_governance"]
    assert isinstance(source_governance, dict)
    runtime_snapshot = source_governance["runtime_snapshot"]
    assert isinstance(runtime_snapshot, dict)
    planning_baseline = runtime_snapshot["planning_baseline"]
    assert isinstance(planning_baseline, dict)
    planning_baseline["full_sha"] = target_sha
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    validated = subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(repository)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert validated.returncode != 0
    assert "correction policy version drifted" in validated.stderr


def test_rule_coverage_contract_cli_refresh_rejects_dirty_runtime_source(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    subprocess.run(
        ["git", "clone", "--no-local", str(ROOT), str(repository)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    contract_path = repository / "docs/project/rule-coverage-contract-v1.json"
    original_contract = contract_path.read_bytes()
    runtime_path = repository / "src/polis/__init__.py"
    runtime_path.write_bytes(runtime_path.read_bytes() + b"\n")

    refreshed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(repository),
            "--refresh",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert refreshed.returncode != 0
    assert "committed source" in refreshed.stderr.lower()
    assert contract_path.read_bytes() == original_contract


def test_rule_coverage_contract_cli_refresh_rejects_nested_root_in_parent_repository(
    tmp_path: Path,
) -> None:
    parent_repository = tmp_path / "parent-repository"
    subprocess.run(
        ["git", "clone", "--no-local", str(ROOT), str(parent_repository)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    nested_root = parent_repository / "nested"
    for relative in ("docs", "src"):
        shutil.copytree(parent_repository / relative, nested_root / relative)
    subprocess.run(
        ["git", "add", "--", "nested"],
        cwd=parent_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Polis test",
            "-c",
            "user.email=polis-test@example.invalid",
            "commit",
            "-m",
            "test: add nested project fixture",
        ],
        cwd=parent_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    contract_path = nested_root / "docs/project/rule-coverage-contract-v1.json"
    original_contract = contract_path.read_bytes()
    runtime_path = nested_root / "src/polis/__init__.py"
    runtime_path.write_bytes(runtime_path.read_bytes() + b"\n")

    refreshed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(nested_root),
            "--refresh",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert refreshed.returncode != 0
    assert (
        "refresh --root must resolve to the exact Git top-level used for HEAD and "
        "dirty checks" in refreshed.stderr
    )
    assert contract_path.read_bytes() == original_contract


def test_rule_coverage_contract_cli_refresh_rejects_staged_runtime_source(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    subprocess.run(
        ["git", "clone", "--no-local", str(ROOT), str(repository)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    contract_path = repository / "docs/project/rule-coverage-contract-v1.json"
    original_contract = contract_path.read_bytes()
    runtime_path = repository / "src/polis/__init__.py"
    runtime_path.write_bytes(runtime_path.read_bytes() + b"\n")
    subprocess.run(
        ["git", "add", "--", "src/polis/__init__.py"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )

    refreshed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(repository),
            "--refresh",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert refreshed.returncode != 0
    assert "committed source" in refreshed.stderr.lower()
    assert contract_path.read_bytes() == original_contract


def test_rule_coverage_contract_cli_refresh_rejects_untracked_runtime_source(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    subprocess.run(
        ["git", "clone", "--no-local", str(ROOT), str(repository)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    contract_path = repository / "docs/project/rule-coverage-contract-v1.json"
    original_contract = contract_path.read_bytes()
    untracked_path = repository / "src/polis/rules/untracked_runtime_file.py"
    untracked_path.write_text("UNTRACKED_RUNTIME_FILE = True\n", encoding="utf-8")

    refreshed = subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "python",
            str(VALIDATOR),
            "--root",
            str(repository),
            "--refresh",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert refreshed.returncode != 0
    assert "committed source" in refreshed.stderr
    assert contract_path.read_bytes() == original_contract


def test_rule_coverage_contract_cli_refresh_rejects_ignored_runtime_source(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    subprocess.run(
        ["git", "clone", "--no-local", str(ROOT), str(repository)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    contract_path = repository / "docs/project/rule-coverage-contract-v1.json"
    original_contract = contract_path.read_bytes()
    ignored_runtime_path = repository / "src/polis/rules/ignored_runtime_file.py"
    with (repository / ".git/info/exclude").open("a", encoding="utf-8") as exclude:
        exclude.write("\n/src/polis/rules/ignored_runtime_file.py\n")
    ignored_runtime_path.write_text("IGNORED_RUNTIME_FILE = True\n", encoding="utf-8")

    refreshed = subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "python",
            str(VALIDATOR),
            "--root",
            str(repository),
            "--refresh",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert refreshed.returncode != 0
    assert "committed source" in refreshed.stderr
    assert contract_path.read_bytes() == original_contract


def test_rule_coverage_contract_cli_refresh_rejects_ignored_python_source_in_pycache(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    subprocess.run(
        ["git", "clone", "--no-local", str(ROOT), str(repository)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    contract_path = repository / "docs/project/rule-coverage-contract-v1.json"
    original_contract = contract_path.read_bytes()
    ignored_runtime_path = repository / "src/polis/rules/__pycache__/ignored_source.py"
    ignored_runtime_path.parent.mkdir(parents=True)
    ignored_runtime_path.write_text("IGNORED_RUNTIME_SOURCE = True\n", encoding="utf-8")

    refreshed = subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "python",
            str(VALIDATOR),
            "--root",
            str(repository),
            "--refresh",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert refreshed.returncode != 0
    assert "committed source" in refreshed.stderr
    assert contract_path.read_bytes() == original_contract


def test_rule_coverage_contract_cli_validates_without_refresh(
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

    valid = subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert valid.returncode == 0, valid.stderr
    assert valid.stdout == "rule coverage contract is valid\n"


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
