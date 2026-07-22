from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from experiments.role_prompt_benchmark.run_benchmark import TimedResponse
from experiments.two_pass_qwen35.assemble_report import assemble_report
from experiments.two_pass_qwen35.experiment import (
    CaseObservation,
    FocusMetrics,
    VariantMetrics,
    load_experiment_config,
    select_development_variant,
    summarize_observations,
    validate_privacy_safe_report,
)
from experiments.two_pass_qwen35.run_benchmark import (
    OllamaPromptClient,
    freeze_development_selection,
    reserve_holdout_run,
    run_two_pass_text,
    verify_prompt_hashes,
)

from polis.llm import TextEdit
from polis.llm.corrected_text import FiniteCandidate, PromptRequest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments" / "two_pass_qwen35" / "config.json"


def _observation(
    case_id: str,
    *,
    focus: str = "syntax",
    negative: bool = False,
    valid: bool = True,
    actual: tuple[TextEdit, ...] = (),
    expected: tuple[TextEdit, ...] = (),
    latency_ms: float = 100.0,
    calls: int = 1,
) -> CaseObservation:
    return CaseObservation(
        case_id=case_id,
        focus=focus,
        protected_negative=negative,
        valid_response=valid,
        actual_edits=actual,
        expected_edits=expected,
        exact_output_match=actual == expected,
        latency_ms=latency_ms,
        call_count=calls,
        outcome_hash="a" * 64,
        status="valid" if valid else "invalid_response",
        source_char_count=20,
    )


def _passing_metrics(name: str = "strict") -> VariantMetrics:
    focus_metrics = {
        focus: FocusMetrics(
            total_cases=10,
            valid_responses=10,
            true_positive_edits=5,
            false_positive_edits=0,
            false_negative_edits=5,
        )
        for focus in ("inflection", "syntax", "punctuation")
    }
    return VariantMetrics(
        variant=name,
        prompt_hash=(name[0] * 64),
        split="development",
        total_cases=40,
        valid_responses=40,
        negative_cases=10,
        negative_changes=0,
        true_positive_edits=15,
        false_positive_edits=0,
        false_negative_edits=15,
        exact_output_matches=25,
        median_latency_ms=500.0,
        warm_p95_latency_ms=1000.0,
        mean_call_count=1.5,
        maximum_call_count=2,
        loaded_memory_bytes=2_500_000_000,
        swap_delta_bytes=0,
        focus_metrics=focus_metrics,
        case_evidence=(),
        cold_latency_ms=2500.0,
        throughput_chars_per_second=40.0,
        process_rss_bytes=2_000_000_000,
    )


def test_config_pins_artifacts_three_variants_and_all_gates() -> None:
    config = load_experiment_config(CONFIG)

    assert config.model.identifier == "qwen3.5:2b-mxfp8"
    assert len(config.model.digest) == 64
    assert config.runtime.version == "0.20.7"
    assert config.corpus.sha256 == (
        "bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2"
    )
    assert [item.name for item in config.prompt_variants] == [
        "strict",
        "checklist",
        "counterexample",
    ]
    assert set(config.operation_prompt_hashes) == {
        "inflection_candidate",
        "syntax_correction",
        "punctuation_correction",
    }
    assert all(len(value) == 64 for value in config.operation_prompt_hashes.values())
    assert config.selection.minimum_edit_precision == 0.9
    assert config.selection.minimum_focus_recall == 0.25
    assert config.selection.maximum_loaded_memory_bytes == 4 * 1024**3
    assert config.selection.maximum_swap_delta_bytes == 64 * 1024**2
    verify_prompt_hashes(config)


def test_prompt_hash_verification_rejects_changed_second_pass() -> None:
    config = load_experiment_config(CONFIG)
    changed = dict(config.operation_prompt_hashes)
    changed["syntax_correction"] = "0" * 64
    with pytest.raises(ValueError, match="operation prompt hash mismatch"):
        verify_prompt_hashes(replace(config, operation_prompt_hashes=changed))


def test_config_rejects_non_local_corpus_path_and_unknown_fields(
    tmp_path: Path,
) -> None:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["corpus"]["path"] = "https://example.test/private.json"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="local relative path"):
        load_experiment_config(path)

    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["unexpected"] = True
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="fields"):
        load_experiment_config(path)


def test_summary_scores_exact_half_open_edits_by_focus() -> None:
    expected = (TextEdit(5, 5, "", ","),)
    observations = (
        _observation("tp", actual=expected, expected=expected, calls=2),
        _observation(
            "fp",
            actual=(TextEdit(4, 4, "", ";"),),
            expected=expected,
            calls=2,
        ),
        _observation("fn", expected=expected),
        _observation("negative", negative=True),
    )

    result = summarize_observations(
        "strict",
        "b" * 64,
        "development",
        observations,
        loaded_memory_bytes=2_000_000_000,
        swap_delta_bytes=0,
        process_rss_bytes=1_500_000_000,
    )

    assert (result.true_positive_edits, result.false_positive_edits) == (1, 1)
    assert result.false_negative_edits == 2
    assert result.edit_precision == 0.5
    assert result.edit_recall == 1 / 3
    assert result.focus_metrics["syntax"].true_positive_edits == 1
    assert result.maximum_call_count == 2
    assert result.negative_changes == 0
    assert result.cold_latency_ms == 100.0
    assert result.throughput_chars_per_second == 200.0
    assert result.process_rss_bytes == 1_500_000_000


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"valid_responses": 39}, "structured-response"),
        ({"negative_changes": 1}, "protected-negative"),
        ({"false_positive_edits": 2}, "edit-precision"),
        ({"warm_p95_latency_ms": 2000.1}, "latency"),
        ({"maximum_call_count": 3}, "call-count"),
        ({"loaded_memory_bytes": 4 * 1024**3 + 1}, "memory"),
        ({"swap_delta_bytes": 64 * 1024**2 + 1}, "swap"),
    ],
)
def test_selection_fails_each_mandatory_gate(
    mutation: dict[str, object], reason: str
) -> None:
    config = load_experiment_config(CONFIG)
    result = select_development_variant(
        config.selection,
        (replace(_passing_metrics(), **cast(dict[str, Any], mutation)),),
    )
    assert result.selected is None
    assert any(reason in item for item in result.reasons)


def test_selection_requires_recall_in_each_focus_and_uses_frozen_tiebreaker() -> None:
    config = load_experiment_config(CONFIG)
    passing = _passing_metrics("strict")
    low_recall = dict(passing.focus_metrics)
    low_recall["punctuation"] = replace(
        low_recall["punctuation"], true_positive_edits=1, false_negative_edits=9
    )
    rejected = select_development_variant(
        config.selection, (replace(passing, focus_metrics=low_recall),)
    )
    assert rejected.selected is None
    assert any("punctuation recall gate failed" in item for item in rejected.reasons)

    faster = replace(
        _passing_metrics("checklist"),
        prompt_hash="c" * 64,
        warm_p95_latency_ms=900.0,
    )
    selected = select_development_variant(config.selection, (passing, faster))
    assert selected.selected == "checklist"


def test_report_validator_rejects_raw_analyzed_text_or_response() -> None:
    config = load_experiment_config(CONFIG)
    safe = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "configuration_sha256": "d" * 64,
        "decision": {"status": "reject", "reasons": ["gate failed"]},
        "environment": {},
        "variants": [],
        "holdout": None,
    }
    assert validate_privacy_safe_report(safe, config)["holdout"] is None
    for key in ("source_text", "raw_response", "corrected_text"):
        unsafe = dict(safe)
        unsafe["environment"] = {key: "prywatny tekst"}
        with pytest.raises(ValueError, match="analyzed text"):
            validate_privacy_safe_report(unsafe, config)


class _ScriptedClient:
    def __init__(self, *responses: str) -> None:
        self.responses = iter(responses)
        self.requests: list[object] = []

    def generate(self, request: object) -> TimedResponse:
        self.requests.append(request)
        return TimedResponse(next(self.responses), 10.0)


class _Candidates:
    def __init__(self, values: tuple[FiniteCandidate, ...] = ()) -> None:
        self.values = values
        self.calls: list[tuple[str, int, int]] = []

    def generate(
        self, source_text: str, start: int, end: int
    ) -> tuple[FiniteCandidate, ...]:
        self.calls.append((source_text, start, end))
        return self.values


def test_two_pass_abstention_uses_one_call_and_never_queries_candidates() -> None:
    client = _ScriptedClient('{"decision":"unchanged"}')
    candidates = _Candidates()

    result = run_two_pass_text(
        client, candidates, "To zdanie jest poprawne.", variant="strict"
    )

    assert result.corrected_text == "To zdanie jest poprawne."
    assert result.valid_response is True
    assert result.call_count == 1
    assert candidates.calls == []
    assert len(client.requests) == 1


def test_two_pass_punctuation_is_evidence_bound_and_uses_two_calls() -> None:
    client = _ScriptedClient(
        '{"decision":"inspect","focus":"punctuation","evidence":"że"}',
        '{"corrected_text":"Wiem, że wróci."}',
    )

    result = run_two_pass_text(
        client, _Candidates(), "Wiem że wróci.", variant="checklist"
    )

    assert result.corrected_text == "Wiem, że wróci."
    assert result.call_count == 2
    assert result.valid_response is True
    protocol_ids = [
        cast(PromptRequest, request).protocol_id for request in client.requests
    ]
    assert protocol_ids == [
        "specialist-diagnostic-router",
        "evidence-bound-corrected-text",
    ]


def test_two_pass_inflection_can_only_apply_local_finite_candidate() -> None:
    source = "Rozmawiam z Jan Nowak."
    start = source.index("Nowak")
    options = (
        FiniteCandidate("original", start, start + 5, "Nowak"),
        FiniteCandidate("instrumental", start, start + 5, "Nowakiem"),
    )
    client = _ScriptedClient(
        '{"decision":"inspect","focus":"inflection","evidence":"Nowak"}',
        '{"candidate_id":"instrumental"}',
    )
    candidates = _Candidates(options)

    result = run_two_pass_text(client, candidates, source, variant="strict")

    assert result.corrected_text == "Rozmawiam z Jan Nowakiem."
    assert candidates.calls == [(source, start, start + 5)]
    assert result.call_count == 2


def test_two_pass_invalid_response_fails_closed_without_third_call() -> None:
    client = _ScriptedClient(
        '{"decision":"inspect","focus":"punctuation","evidence":"że"}',
        '{"corrected_text":"Całkiem inny tekst."}',
    )
    result = run_two_pass_text(
        client, _Candidates(), "Wiem że wróci.", variant="strict"
    )

    assert result.corrected_text == "Wiem że wróci."
    assert result.valid_response is False
    assert result.status == "invalid_response"
    assert result.call_count == 2


def test_ollama_transport_rejects_non_loopback_and_pins_payload() -> None:
    with pytest.raises(ValueError, match="loopback"):
        OllamaPromptClient(
            base_url="https://example.test",
            model="qwen3.5:2b-mxfp8",
            digest="a" * 64,
            timeout_seconds=10,
        )


def test_frozen_selection_and_holdout_sentinel_are_single_use(tmp_path: Path) -> None:
    config = load_experiment_config(CONFIG)
    selection_path = tmp_path / "selection.json"
    sentinel = tmp_path / "holdout.started"

    frozen = freeze_development_selection(
        config,
        replace(
            _passing_metrics("strict"),
            prompt_hash=config.prompt_variants[0].prompt_hash,
        ),
        selection_path,
    )
    assert frozen.variant == "strict"
    assert selection_path.is_file()
    reserve_holdout_run(config, selection_path, sentinel)
    with pytest.raises(FileExistsError, match="already reserved"):
        reserve_holdout_run(config, selection_path, sentinel)


def test_assembler_publishes_rejection_without_exposing_raw_text() -> None:
    config = load_experiment_config(CONFIG)
    development = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "configuration_sha256": "d" * 64,
        "split": "development",
        "environment": {"runtime_version": "0.20.7"},
        "metrics": [{"variant": "strict", "case_evidence": []}],
        "selection": {
            "selected": None,
            "selected_prompt_hash": None,
            "reasons": ["strict: recall gate failed"],
            "eligible_variants": [],
        },
    }

    report = assemble_report(config, development, holdout=None)

    assert report["decision"] == {
        "status": "reject",
        "selected_variant": None,
        "reasons": ["strict: recall gate failed"],
    }
    assert report["holdout"] is None
    validate_privacy_safe_report(report, config)
