from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from urllib.request import Request

import pytest
from experiments.real_llm_benchmark.run_benchmark import (
    BenchmarkCase,
    OllamaClient,
    corrected_output_from_findings,
    load_cases,
    score_case,
    score_findings,
)

from polis.llm import validate_llm_response

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.json"


def test_loader_uses_planned_llm_and_negative_v2_cases() -> None:
    cases = load_cases(CORPUS_PATH)

    assert {case.verification for case in cases} == {"llm_planned", "negative"}
    assert all(case.expected_output for case in cases)
    planned_cases = (case for case in cases if case.verification == "llm_planned")
    negative_cases = (case for case in cases if case.verification == "negative")
    assert all(case.expected_findings for case in planned_cases)
    assert all(not case.expected_findings for case in negative_cases)


def test_loader_rejects_unknown_verification_mode(tmp_path: Path) -> None:
    source = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    source["cases"][0]["verification"] = "unknown"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown verification"):
        load_cases(invalid_path)


def test_client_rejects_non_loopback_url() -> None:
    with pytest.raises(ValueError, match="loopback"):
        OllamaClient("http://example.test", "qwen3:0.6b", timeout_seconds=10.0)


def test_client_posts_deterministic_json_to_local_chat_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return (
                b'{"message":{"content":"{\\"schema_version\\":1,\\"findings\\":[]}"}}'
            )

    def fake_urlopen(request: object, *, timeout: float) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "experiments.real_llm_benchmark.run_benchmark.urlopen", fake_urlopen
    )
    client = OllamaClient("http://127.0.0.1:11434", "qwen3:0.6b", 10.0)

    response = client.generate("strict prompt")

    request = cast(Request, captured["request"])
    assert response.raw_response == '{"schema_version":1,"findings":[]}'
    assert response.elapsed_ms >= 0
    assert captured["timeout"] == 10.0
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert request.data is not None
    payload = json.loads(cast(bytes, request.data).decode("utf-8"))
    assert payload == {
        "format": "json",
        "messages": [{"content": "strict prompt", "role": "user"}],
        "model": "qwen3:0.6b",
        "options": {"num_predict": 512, "seed": 42, "temperature": 0},
        "stream": False,
        "think": False,
    }


def test_negative_finding_disqualifies_candidate() -> None:
    case = BenchmarkCase(
        case_id="correct-name",
        source="Rozmawiałem z Anną Kowalską.",
        expected_output="Rozmawiałem z Anną Kowalską.",
        tags=("negative", "name"),
        verification="negative",
        tracking_issue=None,
        expected_findings=(),
    )

    score = score_case(
        case,
        corrected_output="Rozmawiałem z Anną Kowalską!",
        valid_response=True,
        elapsed_ms=12.0,
    )

    assert score.disqualified is True
    assert score.exact_match is False


def test_corrected_output_applies_only_validated_suggestions() -> None:
    source = "Ala ma kota."
    findings = validate_llm_response(
        json.dumps(
            {
                "schema_version": 1,
                "findings": [
                    {
                        "start": len(source),
                        "end": len(source),
                        "category": "punctuation",
                        "severity": "suggestion",
                        "message": "Dodaj wykrzyknik.",
                        "explanation": "Test aplikacji poprawki.",
                        "original": "",
                        "suggestion": "!",
                        "confidence": 0.9,
                    }
                ],
            }
        ),
        source_text=source,
        source_name="benchmark-test",
    )

    assert corrected_output_from_findings(source, findings) == "Ala ma kota.!"


def test_finding_score_requires_exact_gold_category_span_and_suggestion() -> None:
    case = next(
        item
        for item in load_cases(CORPUS_PATH)
        if item.case_id == "inflection_male_surname_instrumental"
    )
    findings = validate_llm_response(
        json.dumps(
            {
                "schema_version": 1,
                "findings": [
                    {
                        "start": 20,
                        "end": 25,
                        "category": "inflection",
                        "severity": "error",
                        "message": "Błędna odmiana nazwiska.",
                        "explanation": "Narzędnik wymaga odmiany.",
                        "original": "Nowak",
                        "suggestion": "Nowakiem",
                        "confidence": 0.9,
                    },
                    {
                        "start": 0,
                        "end": 11,
                        "category": "style",
                        "severity": "suggestion",
                        "message": "Niepotrzebna sugestia.",
                        "explanation": "Test fałszywego alarmu.",
                        "original": "Rozmawiałem",
                        "suggestion": "Mówiłem",
                        "confidence": 0.4,
                    },
                ],
            }
        ),
        source_text=case.source,
        source_name="benchmark-test",
    )

    score = score_findings(case, findings)

    assert score.true_positives == 1
    assert score.false_positives == 1
    assert score.false_negatives == 0
