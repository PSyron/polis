from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest
from experiments.languagetool_rule_inventory.experiment import (
    InspectionInput,
    RuleObservation,
    disqualify_conflicting_rules,
    load_sentence_cases,
    normalize_inspection_response,
    score_rules,
    select_rule_allowlist,
    validate_privacy_safe_report,
)
from experiments.languagetool_rule_inventory.run_benchmark import (
    freeze_allowlist,
    reserve_holdout_once,
)

from polis.llm import TextEdit

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/evaluation/polish_correction_corpus_v3.json"


def test_inventory_loads_sentence_only_inputs_without_gold_fields() -> None:
    cases = load_sentence_cases(CORPUS, split="development")

    assert len(cases) == 69
    assert {field.name for field in fields(InspectionInput)} == {"source"}
    assert all(case.inspection_input.source for case in cases)
    assert not hasattr(cases[0].inspection_input, "case_id")
    assert not hasattr(cases[0].inspection_input, "expected_output")


def test_normalizer_converts_utf16_and_counts_every_replacement() -> None:
    source = "😀Wiem że wróci."
    payload = {
        "operation": "inspect",
        "software": {"name": "LanguageTool", "version": "6.8"},
        "matches": [
            {
                "offset": 2,
                "length": 7,
                "replacements": [{"value": "Wiem, że"}, {"value": "Wiem iż"}],
                "rule": {
                    "id": "TEST_RULE",
                    "category": {"id": "PUNCTUATION", "name": "Punctuation"},
                },
            }
        ],
    }

    predictions = normalize_inspection_response(source, payload)

    assert predictions == (
        RuleObservation("TEST_RULE", "PUNCTUATION", TextEdit(5, 5, "", ",")),
        RuleObservation("TEST_RULE", "PUNCTUATION", TextEdit(6, 8, "że", "iż")),
    )


def test_rule_scoring_rejects_best_replacement_gold_selection() -> None:
    gold = TextEdit(4, 4, "", ",")
    observations = {
        "case_1": (
            False,
            (gold,),
            (
                RuleObservation("RULE_A", "PUNCTUATION", gold),
                RuleObservation("RULE_A", "PUNCTUATION", TextEdit(0, 1, "W", "V")),
            ),
        ),
        "negative_1": (True, (), ()),
    }

    metrics = score_rules(observations)
    selection = select_rule_allowlist(metrics)

    assert metrics["RULE_A"].true_positive_edits == 1
    assert metrics["RULE_A"].false_positive_edits == 1
    assert metrics["RULE_A"].precision == 0.5
    assert selection == ()


def test_rule_selection_requires_tp_precision_one_and_clean_negatives() -> None:
    gold = TextEdit(4, 4, "", ",")
    observations = {
        "positive": (
            False,
            (gold,),
            (RuleObservation("SAFE_RULE", "PUNCTUATION", gold),),
        ),
        "negative": (True, (), ()),
    }

    metrics = score_rules(observations)

    assert select_rule_allowlist(metrics) == ("SAFE_RULE",)


def test_conflicting_rules_are_removed_from_combined_allowlist() -> None:
    observations = {
        "positive": (
            False,
            (TextEdit(4, 4, "", ","),),
            (
                RuleObservation("RULE_A", "PUNCTUATION", TextEdit(4, 4, "", ",")),
                RuleObservation("RULE_B", "PUNCTUATION", TextEdit(4, 4, "", ";")),
                RuleObservation("RULE_C", "TYPOGRAPHY", TextEdit(10, 11, "-", "–")),
            ),
        )
    }

    selected, conflicts = disqualify_conflicting_rules(
        observations, ("RULE_A", "RULE_B", "RULE_C")
    )

    assert selected == ("RULE_C",)
    assert conflicts == ("RULE_A", "RULE_B")


def test_inventory_report_rejects_raw_text_recursively() -> None:
    safe = {
        "schema_version": 1,
        "experiment_id": "polis-languagetool-rule-inventory-v1",
        "configuration_sha256": "0" * 64,
        "decision": {"selected_rule_ids": []},
        "environment": {},
        "summary": {},
        "rules": [],
        "case_evidence": [],
        "holdout": None,
    }
    validate_privacy_safe_report(safe)
    unsafe = dict(safe)
    unsafe["case_evidence"] = [{"source_text": "secret"}]

    with pytest.raises(ValueError, match="raw analyzed text"):
        validate_privacy_safe_report(unsafe)


def test_allowlist_freeze_and_holdout_reservation_are_atomic(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text('{"schema_version":1}\n', encoding="utf-8")
    bridge = tmp_path / "Bridge.java"
    bridge.write_text("final class Bridge {}\n", encoding="utf-8")
    frozen = tmp_path / "allowlist.json"
    marker = tmp_path / "holdout.started"

    freeze_allowlist(("SAFE_RULE",), config, bridge, frozen)
    reserve_holdout_once(frozen, config, bridge, marker)

    assert marker.exists()
    with pytest.raises(FileExistsError, match="already reserved"):
        reserve_holdout_once(frozen, config, bridge, marker)


def test_invalid_frozen_allowlist_does_not_consume_holdout(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text('{"schema_version":1}\n', encoding="utf-8")
    bridge = tmp_path / "Bridge.java"
    bridge.write_text("final class Bridge {}\n", encoding="utf-8")
    frozen = tmp_path / "allowlist.json"
    marker = tmp_path / "holdout.started"
    freeze_allowlist(("SAFE_RULE",), config, bridge, frozen)
    payload = json.loads(frozen.read_text(encoding="utf-8"))
    payload["rule_ids"] = [1]
    frozen.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="rule identifiers"):
        reserve_holdout_once(frozen, config, bridge, marker)

    assert not marker.exists()
