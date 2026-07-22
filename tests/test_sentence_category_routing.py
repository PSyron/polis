from __future__ import annotations

import json
from collections import Counter
from dataclasses import fields
from pathlib import Path

import pytest
from experiments.sentence_category_routing.assemble_report import (
    assemble_development_report,
)
from experiments.sentence_category_routing.experiment import (
    CaseObservation,
    EvaluationCase,
    RoutingInput,
    SelectionThresholds,
    load_cases,
    load_experiment_config,
    select_development_winner,
    summarize_observations,
    validate_privacy_safe_report,
)
from experiments.sentence_category_routing.protocol import (
    build_syntax_request,
    validate_syntax_response,
)
from experiments.sentence_category_routing.routing import route_sentence
from experiments.sentence_category_routing.run_benchmark import (
    TimedResponse,
    build_ollama_payload,
    freeze_selection,
    reserve_holdout_once,
    run_case,
    run_cases,
    serialize_metrics,
)

from polis.core import Category, Confidence, Finding, Severity, Source
from polis.llm import TextEdit

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments" / "sentence_category_routing" / "config.json"
CORPUS = (
    ROOT / "tests" / "fixtures" / "evaluation" / ("polish_correction_corpus_v3.json")
)


def test_config_freezes_sentence_only_three_model_matrix_and_gates() -> None:
    config = load_experiment_config(CONFIG)

    assert config.schema_version == 1
    assert config.sentence_only is True
    assert tuple(model.name for model in config.models) == (
        "qwen3-1.7b-mlx-4bit",
        "bielik-1.5b-mlx-8bit",
        "qwen3-0.6b-ollama",
    )
    assert tuple(model.engine for model in config.models) == (
        "mlx",
        "mlx",
        "ollama",
    )
    assert config.corpus.sha256 == (
        "bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2"
    )
    assert config.selection.required_valid_response_rate == 1.0
    assert config.selection.maximum_negative_changes == 0
    assert config.selection.minimum_edit_precision == 0.9
    assert config.selection.minimum_focus_recall == 0.25
    assert config.selection.supported_focuses == ("syntax", "punctuation")
    assert config.selection.maximum_calls_per_sentence == 2
    assert config.selection.maximum_warm_p95_latency_ms == 2_000.0
    assert config.selection.maximum_loaded_memory_bytes == 4_294_967_296
    assert config.selection.maximum_swap_delta_bytes == 67_108_864


def test_routing_input_cannot_carry_evaluation_labels_or_gold() -> None:
    names = {field.name for field in fields(RoutingInput)}

    assert names == {"source", "deterministic_findings", "entity_spans"}
    assert names.isdisjoint(
        {"case_id", "focus", "stratum", "tags", "expected_output", "gold_edits"}
    )


def test_load_cases_exposes_gold_only_on_evaluation_wrapper() -> None:
    cases = load_cases(CORPUS, split="development")

    assert len(cases) == 69
    assert all(case.split == "development" for case in cases)
    assert all(case.routing_input.source for case in cases)
    assert all(not case.routing_input.deterministic_findings for case in cases)
    assert all(not case.routing_input.entity_spans for case in cases)
    assert {case.focus for case in cases} == {
        "inflection",
        "syntax",
        "punctuation",
    }
    assert Counter(case.focus for case in cases) == {
        "inflection": 28,
        "syntax": 22,
        "punctuation": 19,
    }
    assert sum(case.protected_negative for case in cases) == 16


def test_config_rejects_unknown_top_level_fields(tmp_path: Path) -> None:
    raw = CONFIG.read_text(encoding="utf-8").replace(
        '"schema_version": 1,', '"schema_version": 1, "unexpected": true,'
    )
    invalid = tmp_path / "config.json"
    invalid.write_text(raw, encoding="utf-8")

    with pytest.raises(ValueError, match="configuration fields"):
        load_experiment_config(invalid)


def _finding(
    text: str,
    *,
    category: Category,
    source: str,
    start: int,
    end: int,
    suggestion: str,
) -> Finding:
    return Finding.create(
        category=category,
        severity=Severity.SUGGESTION,
        message="test",
        explanation="test",
        original=text[start:end],
        suggestion=suggestion,
        start=start,
        end=end,
        confidence=Confidence(0.9),
        source=Source.parse(source),
    )


def test_routing_rejects_more_than_one_sentence() -> None:
    decision = route_sentence(RoutingInput("To działa. To też działa."))

    assert decision.eligible is False
    assert decision.reason == "not_one_sentence"
    assert decision.syntax_window is None


def test_routing_measures_deterministic_channels_separately() -> None:
    text = "Wiem że wróci."
    comma = _finding(
        text,
        category=Category.PUNCTUATION,
        source="rule:languagetool.pl",
        start=4,
        end=4,
        suggestion=",",
    )
    inflection = _finding(
        text,
        category=Category.INFLECTION,
        source="rule:test.inflection",
        start=9,
        end=14,
        suggestion="wrócą",
    )

    decision = route_sentence(RoutingInput(text, (comma, inflection)))

    assert decision.deterministic_punctuation == (comma,)
    assert decision.deterministic_inflection == (inflection,)


def test_routing_builds_one_source_evidence_window_for_known_valency() -> None:
    text = "Czekamy za autobusem przy rondzie."

    decision = route_sentence(RoutingInput(text))

    assert decision.eligible is True
    assert decision.reason == "residual_syntax_evidence"
    assert decision.syntax_window is not None
    assert decision.syntax_window.kind == "government"
    assert text[decision.syntax_window.start : decision.syntax_window.end] == (
        "Czekamy za autobusem"
    )


def test_routing_does_not_rewrite_valid_marked_word_order() -> None:
    decision = route_sentence(RoutingInput("Ten raport wczoraj przygotowała Anna."))

    assert decision.eligible is True
    assert decision.reason == "no_residual_syntax_evidence"
    assert decision.syntax_window is None


def test_routing_protects_urls_numbers_quotes_and_detected_names() -> None:
    text = "Anna podała 42 i https://example.org w cytacie „bez zmian”."

    decision = route_sentence(RoutingInput(text))
    protected = tuple(text[start:end] for start, end in decision.protected_spans)

    assert "Anna" in protected
    assert "42" in protected
    assert "https://example.org" in protected
    assert "„bez zmian”" in protected


def test_routing_result_does_not_change_when_evaluation_wrapper_changes() -> None:
    source = "Nie spodziewaliśmy tak szybkiej odpowiedzi."
    first = route_sentence(RoutingInput(source))
    second = route_sentence(RoutingInput(source))

    assert first == second
    assert first.syntax_window is not None
    assert first.syntax_window.kind == "missing_reflexive"


def test_syntax_request_is_category_specific_evidence_and_protected_aware() -> None:
    text = "Czekamy za autobusem przy rondzie."
    decision = route_sentence(RoutingInput(text))

    request = build_syntax_request(text, decision)

    assert request.protocol_id == "sentence-syntax-evidence"
    assert request.response_schema["required"] == ["corrected_text"]
    assert request.generation["temperature"] == 0
    system = request.messages[0]["content"]
    user = request.messages[-1]["content"]
    assert "wyłącznie składnię" in system
    assert "interpunkcji ani fleksji" in system
    assert "<INPUT_JSON_START>" in user
    assert "</INPUT_JSON_END>" in user
    assert '"evidence_kind":"government"' in user
    assert '"protected_spans"' in user


def test_syntax_response_accepts_unchanged_or_one_in_window_proposal() -> None:
    text = "Czekamy za autobusem przy rondzie."
    decision = route_sentence(RoutingInput(text))

    unchanged = validate_syntax_response(
        '{"corrected_text":"Czekamy za autobusem przy rondzie."}',
        source=text,
        decision=decision,
    )
    changed = validate_syntax_response(
        '{"corrected_text":"Czekamy na autobus przy rondzie."}',
        source=text,
        decision=decision,
    )

    assert unchanged is None
    assert changed is not None
    assert tuple((edit.original, edit.suggestion) for edit in changed.edits) == (
        ("za", "na"),
        ("autobusem", "autobus"),
    )


def test_syntax_response_rejects_out_of_window_and_protected_changes() -> None:
    text = "Czekamy za autobusem przy rondzie."
    decision = route_sentence(RoutingInput(text))

    with pytest.raises(ValueError, match="outside the evidence window"):
        validate_syntax_response(
            '{"corrected_text":"Czekamy za autobusem obok ronda."}',
            source=text,
            decision=decision,
        )

    named = "Anna boi ciemności od dziecka."
    named_decision = route_sentence(RoutingInput(named))
    with pytest.raises(ValueError, match="protected"):
        validate_syntax_response(
            '{"corrected_text":"Ania boi się ciemności od dziecka."}',
            source=named,
            decision=named_decision,
        )


def test_syntax_response_rejects_extra_fields_and_missing_evidence() -> None:
    text = "To zdanie jest poprawne."
    decision = route_sentence(RoutingInput(text))

    with pytest.raises(ValueError, match="syntax evidence"):
        build_syntax_request(text, decision)

    routed = route_sentence(RoutingInput("Potrzebuję ołówek do szkicowania."))
    with pytest.raises(ValueError, match="exactly corrected_text"):
        validate_syntax_response(
            '{"corrected_text":"Potrzebuję ołówka do szkicowania.","why":"x"}',
            source="Potrzebuję ołówek do szkicowania.",
            decision=routed,
        )


def _observation(
    case_id: str,
    *,
    focus: str,
    actual: tuple[TextEdit, ...],
    expected: tuple[TextEdit, ...],
    negative: bool = False,
    latency_ms: float = 10.0,
    calls: int = 1,
) -> CaseObservation:
    channel = {
        "inflection": "deterministic_inflection",
        "syntax": "model_syntax",
        "punctuation": "deterministic_punctuation",
    }[focus]
    return CaseObservation(
        case_id=case_id,
        focus=focus,
        protected_negative=negative,
        valid_response=True,
        actual_edits=actual,
        expected_edits=expected,
        channel_edits={
            "deterministic_punctuation": (
                actual if channel == "deterministic_punctuation" else ()
            ),
            "deterministic_inflection": (
                actual if channel == "deterministic_inflection" else ()
            ),
            "model_syntax": actual if channel == "model_syntax" else (),
        },
        exact_output_match=actual == expected,
        latency_ms=latency_ms,
        call_count=calls,
        status="valid",
        source_char_count=30,
        outcome_hash="0" * 64,
    )


def test_scoring_separates_channels_and_selects_gate_passing_winner() -> None:
    syntax = TextEdit(8, 10, "za", "na")
    punctuation = TextEdit(4, 4, "", ",")
    observations = (
        _observation(
            "syntax_001", focus="syntax", actual=(syntax,), expected=(syntax,)
        ),
        _observation(
            "punctuation_001",
            focus="punctuation",
            actual=(punctuation,),
            expected=(punctuation,),
        ),
        _observation(
            "hard_negative_001",
            focus="syntax",
            actual=(),
            expected=(),
            negative=True,
        ),
    )
    metrics = summarize_observations(
        "fast-model",
        "development",
        observations,
        loaded_memory_bytes=1_000_000,
        swap_delta_bytes=0,
        process_rss_bytes=500_000,
    )
    thresholds = SelectionThresholds(
        1.0,
        0,
        0.9,
        0.25,
        ("syntax", "punctuation"),
        2,
        2_000.0,
        4_294_967_296,
        67_108_864,
    )

    selection = select_development_winner(thresholds, (metrics,))

    assert metrics.edit_precision == 1.0
    assert metrics.focus_metrics["syntax"].edit_recall == 1.0
    assert metrics.focus_metrics["punctuation"].edit_recall == 1.0
    assert metrics.channel_metrics["model_syntax"].true_positive_edits == 1
    assert metrics.channel_metrics["model_syntax"].false_negative_edits == 0
    assert metrics.channel_metrics["deterministic_punctuation"].true_positive_edits == 1
    assert (
        metrics.channel_metrics["deterministic_punctuation"].false_negative_edits == 0
    )
    assert selection.selected == "fast-model"


def test_selection_rejects_call_memory_latency_and_negative_gate_failures() -> None:
    edit = TextEdit(0, 1, "x", "y")
    observations = (
        _observation(
            "hard_negative_001",
            focus="syntax",
            actual=(edit,),
            expected=(),
            negative=True,
            latency_ms=2_100.0,
            calls=3,
        ),
    )
    metrics = summarize_observations(
        "unsafe",
        "development",
        observations,
        loaded_memory_bytes=5_000_000_000,
        swap_delta_bytes=70_000_000,
        process_rss_bytes=1,
    )
    thresholds = load_experiment_config(CONFIG).selection

    selection = select_development_winner(thresholds, (metrics,))

    assert selection.selected is None
    assert any("protected-negative" in reason for reason in selection.reasons)
    assert any("call-count" in reason for reason in selection.reasons)
    assert any("latency" in reason for reason in selection.reasons)
    assert any("loaded-memory" in reason for reason in selection.reasons)
    assert any("swap" in reason for reason in selection.reasons)


def test_report_validation_rejects_source_and_raw_response_recursively() -> None:
    safe = {
        "schema_version": 1,
        "experiment_id": "polis-sentence-category-routing-v1",
        "configuration_sha256": "0" * 64,
        "decision": {"selected": None},
        "environment": {},
        "models": [],
        "holdout": None,
    }
    validate_privacy_safe_report(safe, load_experiment_config(CONFIG))

    unsafe = dict(safe)
    unsafe["models"] = [{"cases": [{"raw_response": "secret"}]}]
    with pytest.raises(ValueError, match="raw analyzed text"):
        validate_privacy_safe_report(unsafe, load_experiment_config(CONFIG))


class _ScriptedClient:
    def __init__(self, responses: tuple[str | Exception, ...]) -> None:
        self._responses = iter(responses)
        self.requests: list[object] = []

    def generate(self, request: object) -> TimedResponse:
        self.requests.append(request)
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return TimedResponse(response, 12.0)


class _StaticChecker:
    def __init__(self, findings: tuple[Finding, ...], elapsed_ms: float) -> None:
        self.findings = findings
        self.elapsed_ms = elapsed_ms

    def check(self, source: str) -> tuple[tuple[Finding, ...], float]:
        del source
        return self.findings, self.elapsed_ms


def _case(
    case_id: str, source: str, expected: str, edits: tuple[TextEdit, ...]
) -> EvaluationCase:
    return next(
        case
        for case in load_cases(CORPUS, split="development")
        if case.case_id == case_id
    )


def test_runner_stops_unchanged_after_one_call_and_keeps_report_private() -> None:
    case = _case(
        "syntax_003",
        "Czekamy za autobusem przy rondzie.",
        "Czekamy na autobus przy rondzie.",
        (),
    )
    client = _ScriptedClient(
        ('{"corrected_text":"Czekamy za autobusem przy rondzie."}',)
    )

    observation = run_case(case, deterministic_findings=(), client=client)

    assert observation.status == "valid"
    assert observation.call_count == 1
    assert observation.actual_edits == ()
    assert not hasattr(observation, "source")
    assert len(client.requests) == 1


def test_run_cases_includes_deterministic_channel_and_end_to_end_latency() -> None:
    case = _case("punctuation_001", "", "", ())
    source = case.routing_input.source
    comma = _finding(
        source,
        category=Category.PUNCTUATION,
        source="rule:languagetool.pl",
        start=4,
        end=4,
        suggestion=",",
    )

    observations = run_cases(
        (case,),
        checker=_StaticChecker((comma,), 3.5),
        client=_ScriptedClient(()),
    )

    assert observations[0].actual_edits == (TextEdit(4, 4, "", ","),)
    assert observations[0].channel_edits["deterministic_punctuation"] == (
        TextEdit(4, 4, "", ","),
    )
    assert observations[0].call_count == 0
    assert observations[0].latency_ms == 3.5
    assert observations[0].exact_output_match is True


def test_ollama_transport_requests_json_mode_not_runtime_json_schema() -> None:
    text = "Czekamy za autobusem przy rondzie."
    request = build_syntax_request(text, route_sentence(RoutingInput(text)))

    payload = build_ollama_payload("qwen3:0.6b", request)

    assert payload["format"] == "json"
    assert payload["model"] == "qwen3:0.6b"
    assert payload["messages"] == request.messages
    assert request.response_schema not in payload.values()


def test_runner_requires_verifier_and_never_exceeds_two_calls() -> None:
    case = _case(
        "syntax_003",
        "Czekamy za autobusem przy rondzie.",
        "Czekamy na autobus przy rondzie.",
        (),
    )
    client = _ScriptedClient(
        (
            '{"corrected_text":"Czekamy na autobus przy rondzie."}',
            '{"decision":"accept"}',
        )
    )

    observation = run_case(case, deterministic_findings=(), client=client)

    assert observation.status == "valid"
    assert observation.call_count == 2
    assert observation.exact_output_match is True
    assert observation.actual_edits == observation.expected_edits
    assert len(client.requests) == 2


def test_runner_fails_closed_on_invalid_model_response() -> None:
    case = _case("syntax_003", "", "", ())
    client = _ScriptedClient(('{"corrected_text":"zupełnie inny tekst"}',))

    observation = run_case(case, deterministic_findings=(), client=client)

    assert observation.status == "invalid_response"
    assert observation.valid_response is False
    assert observation.actual_edits == ()
    assert observation.call_count == 1


def test_freeze_and_holdout_reservation_are_configuration_bound_and_once(
    tmp_path: Path,
) -> None:
    config = load_experiment_config(CONFIG)
    selection = select_development_winner(
        config.selection,
        (
            summarize_observations(
                "qwen3-1.7b-mlx-4bit",
                "development",
                (
                    _observation(
                        "syntax_001",
                        focus="syntax",
                        actual=(TextEdit(0, 1, "x", "y"),),
                        expected=(TextEdit(0, 1, "x", "y"),),
                    ),
                    _observation(
                        "punctuation_001",
                        focus="punctuation",
                        actual=(TextEdit(1, 1, "", ","),),
                        expected=(TextEdit(1, 1, "", ","),),
                    ),
                ),
                loaded_memory_bytes=1,
                swap_delta_bytes=0,
                process_rss_bytes=1,
            ),
        ),
    )
    frozen = tmp_path / "selection.json"
    marker = tmp_path / "holdout.started"

    freeze_selection(selection, CONFIG, frozen)
    reserve_holdout_once(frozen, CONFIG, marker)

    payload = json.loads(frozen.read_text(encoding="utf-8"))
    assert payload["selected"] == "qwen3-1.7b-mlx-4bit"
    assert marker.exists()
    with pytest.raises(FileExistsError, match="already reserved"):
        reserve_holdout_once(frozen, CONFIG, marker)


def test_assembler_selects_from_exact_frozen_matrix_and_emits_private_report() -> None:
    config = load_experiment_config(CONFIG)
    edit = TextEdit(0, 1, "x", "y")
    observations = (
        _observation("syntax_001", focus="syntax", actual=(edit,), expected=(edit,)),
        _observation(
            "punctuation_001", focus="punctuation", actual=(edit,), expected=(edit,)
        ),
    )
    runs = []
    for index, model in enumerate(config.models):
        metrics = summarize_observations(
            model.name,
            "development",
            observations,
            loaded_memory_bytes=100 + index,
            swap_delta_bytes=0,
            process_rss_bytes=100,
        )
        runs.append(
            {
                "schema_version": 1,
                "experiment_id": config.experiment_id,
                "configuration_sha256": __import__("hashlib")
                .sha256(CONFIG.read_bytes())
                .hexdigest(),
                "environment": {"runtime_engine": model.engine},
                "metrics": serialize_metrics(metrics),
            }
        )

    report = assemble_development_report(CONFIG, tuple(runs))

    decision = report["decision"]
    models = report["models"]
    assert isinstance(decision, dict)
    assert isinstance(models, list)
    assert decision["selected"] == "qwen3-1.7b-mlx-4bit"
    assert len(models) == 3
    assert report["holdout"] is None
    validate_privacy_safe_report(report, config)
