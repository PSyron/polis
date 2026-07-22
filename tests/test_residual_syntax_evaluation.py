from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from experiments.residual_syntax_rules import run_evaluation as evaluator

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "residual_syntax_rules"


def test_residual_syntax_evaluator_is_available() -> None:
    assert (
        importlib.util.find_spec("experiments.residual_syntax_rules.run_evaluation")
        is not None
    )


def test_residual_syntax_evaluator_exposes_auditable_contract() -> None:
    assert hasattr(evaluator, "ExactEdit")
    assert hasattr(evaluator, "CaseObservation")
    assert hasattr(evaluator, "score_observations")
    assert hasattr(evaluator, "validate_privacy_safe_report")
    assert hasattr(evaluator, "reserve_holdout_once")
    assert hasattr(evaluator, "load_sentence_cases")
    assert hasattr(evaluator, "run_cases")
    assert hasattr(evaluator, "development_qualifies")
    assert hasattr(evaluator, "freeze_rules")


def test_exact_edit_scorer_is_independent_of_categories_and_sources() -> None:
    correct = evaluator.ExactEdit(7, 7, "", " się")
    missed = evaluator.ExactEdit(22, 22, "", "tym ")
    extra = evaluator.ExactEdit(3, 3, "", ",")
    observations = (
        evaluator.CaseObservation("syntax_021", False, (correct,), (correct,), 0.2),
        evaluator.CaseObservation("syntax_057", False, (missed,), (), 0.3),
        evaluator.CaseObservation("hard_negative_001", True, (), (extra,), 0.4),
    )

    summary = evaluator.score_observations(observations)

    assert summary == {
        "total_cases": 3,
        "proposed_edits": 2,
        "true_positive_edits": 1,
        "false_positive_edits": 1,
        "false_negative_edits": 1,
        "precision": 0.5,
        "recall": 0.5,
        "protected_negative_changes": 1,
        "exact_output_matches": 1,
        "warm_median_ms": 0.35,
        "warm_p95_ms": 0.4,
    }


def test_report_validator_rejects_raw_sentence_material() -> None:
    safe = {"case_evidence": [{"case_id": "syntax_021", "edit_hash": "abc"}]}

    assert evaluator.validate_privacy_safe_report(safe) == safe
    with pytest.raises(ValueError, match="raw analyzed text"):
        evaluator.validate_privacy_safe_report({"source_text": "tajne zdanie"})


def test_holdout_reservation_is_one_shot_and_bound_to_frozen_hashes(
    tmp_path: Path,
) -> None:
    frozen = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    frozen.write_text(json.dumps({"rules_sha256": "a" * 64}), encoding="utf-8")

    evaluator.reserve_holdout_once(frozen, marker)

    assert json.loads(marker.read_text(encoding="utf-8")) == {"rules_sha256": "a" * 64}
    with pytest.raises(FileExistsError, match="already reserved"):
        evaluator.reserve_holdout_once(frozen, marker)


def test_committed_sentence_report_records_non_vacuous_policy_decision() -> None:
    report = json.loads((EXPERIMENT / "report.json").read_text(encoding="utf-8"))
    frozen = json.loads((EXPERIMENT / "frozen_rules.json").read_text(encoding="utf-8"))
    marker = json.loads((EXPERIMENT / "holdout.started").read_text(encoding="utf-8"))

    assert evaluator.validate_privacy_safe_report(report) == report
    assert report["decision"] == {"automatic_policy": False, "qualified": False}
    assert report["development"]["summary"]["total_cases"] == 69
    assert report["development"]["summary"]["true_positive_edits"] == 3
    assert report["development"]["summary"]["false_positive_edits"] == 0
    assert report["development"]["summary"]["precision"] == 1.0
    assert report["development"]["summary"]["protected_negative_changes"] == 0
    assert report["holdout"]["summary"]["total_cases"] == 142
    assert report["holdout"]["summary"]["proposed_edits"] == 0
    assert report["holdout"]["summary"]["protected_negative_changes"] == 0
    assert frozen == marker
    assert frozen == {
        "configuration_sha256": evaluator._sha256(EXPERIMENT / "config.json"),
        "evaluator_sha256": evaluator._sha256(EXPERIMENT / "run_evaluation.py"),
        "rules_sha256": evaluator._sha256(
            ROOT / "src" / "polis" / "rules" / "syntax.py"
        ),
    }
