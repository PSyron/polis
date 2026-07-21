from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from urllib.request import Request

import pytest
from experiments.real_llm_benchmark.run_benchmark import (
    BenchmarkCase,
    BenchmarkObservation,
    FindingScore,
    GoldFinding,
    OllamaClient,
    TimedResponse,
    corrected_output_from_findings,
    load_cases,
    main,
    report_as_json,
    run_cases,
    score_case,
    score_findings,
    summarize_observations,
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


def test_summary_reports_category_metrics_and_rejects_negative_change() -> None:
    inflection = BenchmarkCase(
        case_id="inflection",
        source="Rozmawiałem z Jan Nowak.",
        expected_output="Rozmawiałem z Janem Nowakiem.",
        tags=("inflection",),
        verification="llm_planned",
        tracking_issue=48,
        expected_findings=(
            # The concrete offsets are immaterial to aggregation.
            # They describe the expected replacement in the source string.
            GoldFinding("inflection", 14, 19, "Nowak", "Nowakiem"),
        ),
    )
    negative = BenchmarkCase(
        case_id="negative",
        source="Anna Kowalska przeczytała raport.",
        expected_output="Anna Kowalska przeczytała raport.",
        tags=("negative",),
        verification="negative",
        tracking_issue=None,
        expected_findings=(),
    )

    report = summarize_observations(
        (
            BenchmarkObservation(
                case=inflection,
                valid_response=True,
                elapsed_ms=120.0,
                finding_score=FindingScore(1, 0, 0),
                corrected_output=inflection.expected_output,
            ),
            BenchmarkObservation(
                case=negative,
                valid_response=True,
                elapsed_ms=80.0,
                finding_score=FindingScore(0, 1, 0),
                corrected_output="Anna Kowalska przeczytała raport!",
            ),
        )
    )

    assert report.valid_responses == 2
    assert report.negative_cases_changed == 1
    assert report.safety_eligible is False
    assert report.overall_metrics.precision == 0.5
    assert report.overall_metrics.recall == 1.0
    assert round(report.overall_metrics.f1, 3) == 0.667
    assert report.category_metrics["inflection"].f1 == 1.0
    assert report.category_metrics["inflection"].precision == 1.0
    assert report.category_metrics["inflection"].recall == 1.0


def test_summary_excludes_invalid_responses_from_latency_median() -> None:
    case = BenchmarkCase(
        case_id="negative",
        source="Poprawne zdanie.",
        expected_output="Poprawne zdanie.",
        tags=("negative",),
        verification="negative",
        tracking_issue=None,
        expected_findings=(),
    )

    report = summarize_observations(
        (
            BenchmarkObservation(
                case=case,
                valid_response=False,
                elapsed_ms=0.0,
                finding_score=FindingScore(0, 0, 0),
                corrected_output=case.source,
            ),
            BenchmarkObservation(
                case=case,
                valid_response=True,
                elapsed_ms=120.0,
                finding_score=FindingScore(0, 0, 0),
                corrected_output=case.source,
            ),
        )
    )

    assert report.median_latency_ms == 120.0


def test_run_cases_turns_an_invalid_model_response_into_a_safe_observation() -> None:
    case = BenchmarkCase(
        case_id="negative",
        source="Anna Kowalska przeczytała raport.",
        expected_output="Anna Kowalska przeczytała raport.",
        tags=("negative",),
        verification="negative",
        tracking_issue=None,
        expected_findings=(),
    )

    class InvalidClient:
        def generate(self, prompt: str) -> TimedResponse:
            assert "Anna Kowalska" in prompt
            return TimedResponse("not json", 25.0)

    observation = run_cases(InvalidClient(), (case,))[0]

    assert observation.case == case
    assert observation.valid_response is False
    assert observation.corrected_output == case.source
    assert observation.finding_score == FindingScore(0, 0, 0)


def test_run_cases_accepts_a_valid_empty_response() -> None:
    case = BenchmarkCase(
        case_id="negative_case",
        source="Anna Kowalska przeczytała raport.",
        expected_output="Anna Kowalska przeczytała raport.",
        tags=("negative",),
        verification="negative",
        tracking_issue=None,
        expected_findings=(),
    )

    class ValidClient:
        def generate(self, prompt: str) -> TimedResponse:
            assert "Anna Kowalska" in prompt
            return TimedResponse('{"schema_version":1,"findings":[]}', 25.0)

    observation = run_cases(ValidClient(), (case,))[0]

    assert observation.valid_response is True
    assert observation.elapsed_ms == 25.0
    assert observation.corrected_output == case.source


def test_report_as_json_is_a_stable_auditable_summary() -> None:
    report = summarize_observations(
        (
            BenchmarkObservation(
                case=BenchmarkCase(
                    case_id="safe",
                    source="Poprawne zdanie.",
                    expected_output="Poprawne zdanie.",
                    tags=("negative",),
                    verification="negative",
                    tracking_issue=None,
                    expected_findings=(),
                ),
                valid_response=True,
                elapsed_ms=7.5,
                finding_score=FindingScore(0, 0, 0),
                corrected_output="Poprawne zdanie.",
            ),
        )
    )

    payload = json.loads(report_as_json(report))

    assert payload == {
        "category_metrics": {},
        "overall_metrics": {
            "f1": 0.0,
            "false_negatives": 0,
            "false_positives": 0,
            "precision": 0.0,
            "recall": 0.0,
            "true_positives": 0,
        },
        "safety_eligible": True,
        "median_latency_ms": 7.5,
        "negative_cases_changed": 0,
        "total_responses": 1,
        "valid_responses": 1,
    }


def test_main_writes_json_report_without_network(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    case = BenchmarkCase(
        case_id="safe",
        source="Poprawne zdanie.",
        expected_output="Poprawne zdanie.",
        tags=("negative",),
        verification="negative",
        tracking_issue=None,
        expected_findings=(),
    )
    monkeypatch.setattr(
        "experiments.real_llm_benchmark.run_benchmark.load_cases",
        lambda _: (case,),
    )
    monkeypatch.setattr(
        "experiments.real_llm_benchmark.run_benchmark.run_cases",
        lambda *_: (
            BenchmarkObservation(
                case=case,
                valid_response=True,
                elapsed_ms=10.0,
                finding_score=FindingScore(0, 0, 0),
                corrected_output=case.source,
            ),
        ),
    )

    assert main(["--model", "local-test", "--corpus", str(CORPUS_PATH)]) == 0

    assert json.loads(capsys.readouterr().out)["safety_eligible"] is True
