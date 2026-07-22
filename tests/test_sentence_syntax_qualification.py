from __future__ import annotations

import hashlib
import json
from dataclasses import fields
from pathlib import Path
from typing import cast

import pytest
from experiments.sentence_category_routing.experiment import (
    RoutingInput,
    load_cases,
)
from experiments.sentence_category_routing.run_benchmark import TimedResponse
from experiments.sentence_syntax_qualification.assemble_report import (
    assemble_development_report,
)
from experiments.sentence_syntax_qualification.experiment import (
    QualificationInput,
    load_qualification_config,
)
from experiments.sentence_syntax_qualification.protocol import (
    build_diagnostic_request,
    build_evidence_verifier_request,
    build_proposal_request,
    normalize_proposal,
    prepare_decision,
    validate_diagnostic_response,
    validate_evidence_verdict,
    validate_proposal_response,
)
from experiments.sentence_syntax_qualification.run_benchmark import (
    StaticClient,
    run_case,
)

from polis.core import Category, Confidence, Finding, Severity, Source

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments" / "sentence_syntax_qualification" / "config.json"
CORPUS = (
    ROOT / "tests" / "fixtures" / "evaluation" / ("polish_correction_corpus_v3.json")
)
REPORT = ROOT / "experiments" / "sentence_syntax_qualification" / "report.json"


def test_config_freezes_one_model_three_prompt_variants_and_sentence_gates() -> None:
    config = load_qualification_config(CONFIG)

    assert config.sentence_only is True
    assert config.model.identifier == "mlx-community/Qwen3-1.7B-4bit"
    assert config.model.revision == ("3b1b1768f8f8cf8351c712464f906e86c2b8269e")
    assert config.runtime.version == "0.31.3"
    assert config.runtime.framework_version == "0.32.0"
    assert config.runtime.chat_template_args == {"enable_thinking": False}
    assert config.variants == (
        "generic_verified-v1",
        "evidence_checklist_verified-v1",
        "diagnose_then_correct-v1",
    )
    assert config.selection.supported_focuses == ("syntax",)
    assert config.selection.minimum_edit_precision == 0.9
    assert config.selection.minimum_focus_recall == 0.25
    assert config.selection.maximum_calls_per_sentence == 2


def test_qualification_input_cannot_carry_gold_or_labels() -> None:
    names = {field.name for field in fields(QualificationInput)}

    assert names == {"source", "deterministic_findings", "entity_spans"}
    assert names.isdisjoint(
        {"case_id", "focus", "expected_output", "gold_edits", "tags"}
    )


def test_prepare_decision_is_sentence_only_and_protects_deterministic_edits() -> None:
    source = "Czekamy za autobusem przy rondzie."
    finding = Finding.create(
        category=Category.PUNCTUATION,
        severity=Severity.SUGGESTION,
        message="test",
        explanation="test",
        original="",
        suggestion=",",
        start=20,
        end=20,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test"),
    )

    decision = prepare_decision(QualificationInput(source, (finding,)))

    assert decision.syntax_window is not None
    assert (20, 20) in decision.protected_spans
    assert (
        prepare_decision(QualificationInput(source + " Drugie zdanie.")).eligible
        is False
    )


def test_evidence_checklist_request_contains_source_only_bounded_contract() -> None:
    source = "Czekamy za autobusem przy rondzie."
    decision = prepare_decision(QualificationInput(source))

    request = build_proposal_request(
        source,
        decision,
        variant="evidence_checklist_verified-v1",
    )

    assert request.protocol_id == "sentence-syntax-evidence-checklist"
    assert request.protocol_version == "1.0"
    assert request.generation["temperature"] == 0
    serialized = json.dumps(request.messages, ensure_ascii=False)
    assert "rekcję" in serialized
    assert '"decision":"unchanged"' in request.messages[0]["content"]
    assert source in serialized
    assert "expected" not in serialized.casefold()
    assert "gold" not in serialized.casefold()


def test_proposal_validation_requires_coherent_decision_and_evidence_bound_edit() -> (
    None
):
    source = "Czekamy za autobusem przy rondzie."
    decision = prepare_decision(QualificationInput(source))

    proposal = validate_proposal_response(
        '{"decision":"corrected","corrected_text":"Czekamy na autobus przy rondzie."}',
        source=source,
        decision=decision,
    )

    assert proposal is not None
    assert tuple((edit.original, edit.suggestion) for edit in proposal.edits) == (
        ("za", "na"),
        ("autobusem", "autobus"),
    )
    with pytest.raises(ValueError, match="decision"):
        validate_proposal_response(
            '{"decision":"unchanged","corrected_text":'
            '"Czekamy na autobus przy rondzie."}',
            source=source,
            decision=decision,
        )


def test_proposal_cannot_replace_text_at_a_protected_insertion_boundary() -> None:
    source = "Czekamy za autobusem przy rondzie."
    finding = Finding.create(
        category=Category.PUNCTUATION,
        severity=Severity.SUGGESTION,
        message="test",
        explanation="test",
        original="",
        suggestion=",",
        start=8,
        end=8,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test"),
    )
    decision = prepare_decision(QualificationInput(source, (finding,)))

    with pytest.raises(ValueError, match="protected deterministic"):
        validate_proposal_response(
            '{"decision":"corrected","corrected_text":'
            '"Czekamy na autobus przy rondzie."}',
            source=source,
            decision=decision,
        )


def test_diagnostic_and_evidence_verifier_contracts_are_separate() -> None:
    source = "Nie spodziewaliśmy tak szybkiej odpowiedzi."
    decision = prepare_decision(QualificationInput(source))

    diagnostic = build_diagnostic_request(source, decision)
    parsed = validate_diagnostic_response(
        '{"decision":"change","requirement":"Czasownik wymaga partykuły się."}'
    )
    verifier = build_evidence_verifier_request(
        source,
        "Nie spodziewaliśmy się tak szybkiej odpowiedzi.",
        decision,
    )

    assert diagnostic.protocol_id == "sentence-syntax-diagnostic"
    assert parsed.decision == "change"
    assert verifier.protocol_id == "sentence-syntax-evidence-verifier"
    assert validate_evidence_verdict('{"decision":"accept"}') is True
    assert validate_evidence_verdict('{"decision":"reject"}') is False


def test_correlative_insertion_is_canonicalized_without_changing_output() -> None:
    source = "Im dłużej czekaliśmy, bardziej byliśmy niecierpliwi."
    decision = prepare_decision(QualificationInput(source))
    proposal = validate_proposal_response(
        '{"decision":"corrected","corrected_text":'
        '"Im dłużej czekaliśmy, tym bardziej byliśmy niecierpliwi."}',
        source=source,
        decision=decision,
    )

    assert proposal is not None
    normalized = normalize_proposal(source, proposal, decision)
    assert normalized.edits[0].start == 22
    assert normalized.edits[0].suggestion == "tym "


def test_development_loader_still_exposes_gold_only_to_evaluation_wrapper() -> None:
    cases = load_cases(CORPUS, split="development")
    routed = QualificationInput(cases[0].routing_input.source)

    assert len(cases) == 69
    assert isinstance(cases[0].routing_input, RoutingInput)
    assert routed.source == cases[0].routing_input.source


def test_checklist_orchestration_accepts_one_verified_sentence_edit() -> None:
    case = next(
        case
        for case in load_cases(CORPUS, split="development")
        if case.case_id == "syntax_021"
    )
    client = StaticClient(
        (
            TimedResponse(
                '{"decision":"corrected","corrected_text":'
                '"Ona boi się ciemności od dziecka."}',
                10.0,
            ),
            TimedResponse('{"decision":"accept"}', 5.0),
        )
    )

    observation = run_case(
        case,
        variant="evidence_checklist_verified-v1",
        client=client,
    )

    assert observation.valid_response is True
    assert observation.exact_output_match is True
    assert observation.call_count == 2
    assert client.calls == 2


def test_malformed_diagnostic_fails_closed_after_one_call() -> None:
    case = next(
        case
        for case in load_cases(CORPUS, split="development")
        if case.case_id == "syntax_021"
    )
    client = StaticClient((TimedResponse('{"decision":"change"}', 10.0),))

    observation = run_case(
        case,
        variant="diagnose_then_correct-v1",
        client=client,
    )

    assert observation.valid_response is False
    assert observation.actual_edits == ()
    assert observation.call_count == 1


def test_report_rejects_all_failing_variants_and_keeps_holdout_unopened() -> None:
    runs = tuple(
        _run(variant, precision=0.5, recall=0.2)
        for variant in load_qualification_config(CONFIG).variants
    )

    report = assemble_development_report(CONFIG, runs)
    decision = cast(dict[str, object], report["decision"])

    assert decision["selected"] is None
    assert decision["eligible_variants"] == []
    assert report["holdout"] == {
        "status": "unopened",
        "reason": "no development variant passed every gate",
    }


def test_report_rejects_raw_text_or_response_fields() -> None:
    variants = load_qualification_config(CONFIG).variants
    runs = [_run(variant, precision=1.0, recall=0.3) for variant in variants]
    run = runs[0]
    metrics = cast(dict[str, object], run["metrics"])
    metrics["raw_response"] = "forbidden"

    with pytest.raises(ValueError, match="privacy-safe"):
        assemble_development_report(CONFIG, tuple(runs))


def test_committed_report_matches_frozen_config_and_leaves_holdout_unopened() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert (
        report["configuration_sha256"]
        == hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    )
    assert report["decision"]["selected"] is None
    assert report["holdout"]["status"] == "unopened"
    assert [item["model"] for item in report["variants"]] == list(
        load_qualification_config(CONFIG).variants
    )


def _run(variant: str, *, precision: float, recall: float) -> dict[str, object]:
    return {
        "schema_version": 1,
        "experiment_id": "polis-qwen17-sentence-syntax-qualification-v1",
        "configuration_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "environment": {"runtime_engine": "mlx"},
        "metrics": {
            "model": variant,
            "split": "development",
            "total_cases": 69,
            "valid_responses": 69,
            "negative_changes": 0,
            "maximum_call_count": 2,
            "warm_p95_latency_ms": 900.0,
            "loaded_memory_bytes": 1_400_000_000,
            "swap_delta_bytes": 0,
            "channel_metrics": {
                "model_syntax": {
                    "edit_precision": precision,
                    "edit_recall": recall,
                }
            },
        },
    }
