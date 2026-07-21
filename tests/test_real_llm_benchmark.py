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
    RuntimeMetadata,
    TimedResponse,
    _build_client,
    _default_base_url_for_engine,
    _default_runtime_engine,
    classify_case_failure,
    corrected_output_from_findings,
    load_cases,
    main,
    report_as_json,
    run_cases,
    score_case,
    score_findings,
    select_healthy_client,
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
    assert payload["format"]["required"] == ["schema_version", "findings"]
    assert payload["messages"] == [{"content": "strict prompt", "role": "user"}]
    assert payload["model"] == "qwen3:0.6b"
    assert payload["options"] == {"num_predict": 512, "seed": 42, "temperature": 0}
    assert payload["stream"] is False
    assert payload["think"] is False


def test_default_engine_prefers_mlx_on_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "experiments.real_llm_benchmark.run_benchmark.platform.system", lambda: "Darwin"
    )
    assert _default_runtime_engine("auto") == "mlx"


def test_default_base_url_for_mlx_is_compatible_with_local_inference_server() -> None:
    assert _default_base_url_for_engine("mlx").startswith("http://127.0.0.1:")


def test_build_client_supports_mlx_openai_compatible_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {"message": {"content": '{"schema_version":1,"findings": []}'}}
                    ]
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")

    def fake_urlopen(request: object, *, timeout: float) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "experiments.real_llm_benchmark.run_benchmark.urlopen", fake_urlopen
    )
    client = _build_client(
        engine="mlx",
        base_url="http://127.0.0.1:8080",
        model="local-model",
        timeout_seconds=7.0,
    )
    response = client.generate("strict prompt")

    request = cast(Request, captured["request"])
    payload = json.loads(cast(bytes, request.data).decode("utf-8"))
    assert json.loads(response.raw_response) == {"schema_version": 1, "findings": []}
    assert isinstance(payload["max_tokens"], int)
    assert payload["max_tokens"] == 512
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert request.full_url == "http://127.0.0.1:8080/v1/chat/completions"


def test_ollama_preflight_records_loaded_model_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __init__(self, payload: object) -> None:
            self.payload = payload

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        assert timeout == 10.0
        if request.full_url.endswith("/api/version"):
            return FakeResponse({"version": "0.20.7"})
        if request.full_url.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": "qwen3:0.6b"}]})
        assert request.full_url.endswith("/api/ps")
        return FakeResponse({"models": [{"name": "qwen3:0.6b", "size_vram": 522}]})

    monkeypatch.setattr(
        "experiments.real_llm_benchmark.run_benchmark.urlopen", fake_urlopen
    )

    metadata = OllamaClient("http://127.0.0.1:11434", "qwen3:0.6b", 10.0).preflight()

    assert metadata.engine == "ollama"
    assert metadata.model_identifier == "qwen3:0.6b"
    assert metadata.runtime_version == "0.20.7"
    assert metadata.loaded_memory_bytes == 522


def test_ollama_preflight_accepts_an_installed_but_idle_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __init__(self, payload: object) -> None:
            self.payload = payload

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request: Request, *, timeout: float) -> FakeResponse:
        if request.full_url.endswith("/api/version"):
            return FakeResponse({"version": "0.20.7"})
        if request.full_url.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": "qwen3:0.6b"}]})
        assert request.full_url.endswith("/api/ps")
        return FakeResponse({"models": []})

    monkeypatch.setattr(
        "experiments.real_llm_benchmark.run_benchmark.urlopen", fake_urlopen
    )

    metadata = OllamaClient("http://127.0.0.1:11434", "qwen3:0.6b", 10.0).preflight()

    assert metadata.model_identifier == "qwen3:0.6b"
    assert metadata.loaded_memory_bytes is None


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
    assert report.warm_median_latency_ms == 0.0
    assert report.warm_p95_latency_ms == 0.0
    assert report.cold_median_latency_ms == 120.0
    assert report.cold_p95_latency_ms == 120.0


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
    assert observation.status == "invalid_schema"


def test_run_cases_with_cache_probe_records_cold_and_warm_latencies() -> None:
    case = BenchmarkCase(
        case_id="cache_probe",
        source="Jan ma kota.",
        expected_output="Jan ma kota.",
        tags=("negative",),
        verification="negative",
        tracking_issue=None,
        expected_findings=(),
    )

    class RepeatingClient:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, prompt: str) -> TimedResponse:
            self.calls += 1
            return TimedResponse(
                '{"schema_version":1,"findings":[]}',
                10.0 * self.calls,
            )

    observation = run_cases(RepeatingClient(), (case,), cache_probe=True)[0]

    assert observation.valid_response is True
    assert observation.call_count == 2
    assert observation.elapsed_ms == 15.0
    assert observation.cold_elapsed_ms == 10.0
    assert observation.warm_elapsed_ms == 20.0


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

    assert payload["safety_eligible"] is True
    assert payload["median_latency_ms"] == 7.5
    assert payload["p95_latency_ms"] == 7.5
    assert payload["throughput_chars_per_second"] > 0
    assert payload["runtime"] is None
    assert payload["corpus_sha256"] is None
    assert payload["cases"] == [
        {
            "call_count": 1,
            "cold_elapsed_ms": 7.5,
            "elapsed_ms": 7.5,
            "exact_match": True,
            "false_negatives": 0,
            "false_positives": 0,
            "id": "safe",
            "status": "valid",
            "true_positives": 0,
            "valid_response": True,
            "warm_elapsed_ms": 0.0,
        }
    ]
    assert "Poprawne zdanie" not in report_as_json(report)
    assert report_as_json(report) == report_as_json(report)


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
        lambda *_args, **_kwargs: (
            BenchmarkObservation(
                case=case,
                valid_response=True,
                elapsed_ms=10.0,
                finding_score=FindingScore(0, 0, 0),
                corrected_output=case.source,
            ),
        ),
    )

    class HealthyClient:
        def preflight(self) -> RuntimeMetadata:
            return RuntimeMetadata("ollama", "local-test", "test")

        def generate(self, prompt: str) -> TimedResponse:
            raise AssertionError("run_cases is patched")

    healthy = HealthyClient()
    monkeypatch.setattr(
        "experiments.real_llm_benchmark.run_benchmark.select_healthy_client",
        lambda *_: ("ollama", healthy),
    )

    assert main(["--model", "local-test", "--corpus", str(CORPUS_PATH)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["safety_eligible"] is True
    assert payload["runtime"]["engine"] == "ollama"
    assert payload["runtime"]["model_identifier"] == "local-test"
    assert len(payload["corpus_sha256"]) == 64


def test_main_records_memory_reported_after_the_benchmark(
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
        lambda *_args, **_kwargs: (
            BenchmarkObservation(
                case=case,
                valid_response=True,
                elapsed_ms=10.0,
                finding_score=FindingScore(0, 0, 0),
                corrected_output=case.source,
            ),
        ),
    )

    class LoadingClient:
        def __init__(self) -> None:
            self.preflight_calls = 0

        def preflight(self) -> RuntimeMetadata:
            self.preflight_calls += 1
            return RuntimeMetadata(
                "ollama",
                "local-test",
                "test",
                loaded_memory_bytes=1_024 * self.preflight_calls,
            )

        def generate(self, prompt: str) -> TimedResponse:
            raise AssertionError("run_cases is patched")

    loading = LoadingClient()
    monkeypatch.setattr(
        "experiments.real_llm_benchmark.run_benchmark.select_healthy_client",
        lambda *_: ("ollama", loading),
    )

    assert main(["--model", "local-test", "--corpus", str(CORPUS_PATH)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert loading.preflight_calls == 2
    assert payload["runtime"]["loaded_memory_bytes"] == 2_048


def test_main_accepts_an_explicit_loaded_memory_observation(
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
        lambda *_args, **_kwargs: (
            BenchmarkObservation(
                case=case,
                valid_response=True,
                elapsed_ms=10.0,
                finding_score=FindingScore(0, 0, 0),
                corrected_output=case.source,
            ),
        ),
    )

    class HealthyClient:
        def preflight(self) -> RuntimeMetadata:
            return RuntimeMetadata("mlx", "local-test", "test")

        def generate(self, prompt: str) -> TimedResponse:
            raise AssertionError("run_cases is patched")

    healthy = HealthyClient()
    monkeypatch.setattr(
        "experiments.real_llm_benchmark.run_benchmark.select_healthy_client",
        lambda *_: ("mlx", healthy),
    )

    assert (
        main(
            [
                "--model",
                "local-test",
                "--corpus",
                str(CORPUS_PATH),
                "--loaded-memory-bytes",
                "4096",
                "--runtime-version",
                "0.31.3",
                "--operating-system",
                "macOS 15.3.1",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime"]["loaded_memory_bytes"] == 4096
    assert payload["runtime"]["runtime_version"] == "0.31.3"
    assert payload["runtime"]["operating_system"] == "macOS 15.3.1"


def test_category_metrics_attribute_extra_finding_to_its_emitted_category() -> None:
    case = BenchmarkCase(
        case_id="cross-category",
        source="Jan poszedł do dom.",
        expected_output="Jan poszedł do domu.",
        tags=("inflection",),
        verification="llm_planned",
        tracking_issue=48,
        expected_findings=(GoldFinding("inflection", 15, 18, "dom", "domu"),),
    )
    findings = validate_llm_response(
        json.dumps(
            {
                "schema_version": 1,
                "findings": [
                    {
                        "start": 15,
                        "end": 18,
                        "category": "inflection",
                        "severity": "error",
                        "message": "Odmiana.",
                        "explanation": "Dopełniacz.",
                        "original": "dom",
                        "suggestion": "domu",
                        "confidence": 0.9,
                    },
                    {
                        "start": 0,
                        "end": 3,
                        "category": "style",
                        "severity": "suggestion",
                        "message": "Niepotrzebna zmiana.",
                        "explanation": "Test kategorii.",
                        "original": "Jan",
                        "suggestion": "Jaś",
                        "confidence": 0.2,
                    },
                ],
            }
        ),
        source_text=case.source,
        source_name="benchmark-test",
    )

    report = summarize_observations(
        (
            BenchmarkObservation(
                case=case,
                valid_response=True,
                elapsed_ms=20.0,
                finding_score=score_findings(case, findings),
                corrected_output=case.expected_output,
            ),
        )
    )

    assert report.category_metrics["inflection"].false_positives == 0
    assert report.category_metrics["style"].false_positives == 1


def test_negative_case_false_positive_is_attributed_to_emitted_category() -> None:
    case = BenchmarkCase(
        case_id="negative-category",
        source="Anna Kowalska przeczytała raport.",
        expected_output="Anna Kowalska przeczytała raport.",
        tags=("negative", "name"),
        verification="negative",
        tracking_issue=None,
        expected_findings=(),
    )
    findings = validate_llm_response(
        json.dumps(
            {
                "schema_version": 1,
                "findings": [
                    {
                        "start": 0,
                        "end": 4,
                        "category": "style",
                        "severity": "suggestion",
                        "message": "Nieuzasadniona zmiana.",
                        "explanation": "Negatywny przypadek.",
                        "original": "Anna",
                        "suggestion": "Ania",
                        "confidence": 0.2,
                    }
                ],
            }
        ),
        source_text=case.source,
        source_name="benchmark-test",
    )

    report = summarize_observations(
        (
            BenchmarkObservation(
                case=case,
                valid_response=True,
                elapsed_ms=20.0,
                finding_score=score_findings(case, findings),
                corrected_output="Ania Kowalska przeczytała raport.",
            ),
        )
    )

    assert report.category_metrics["style"].false_positives == 1
    assert report.category_metrics["style"].true_positives == 0


def test_failure_classifier_separates_invalid_span_and_conflicting_edits() -> None:
    assert (
        classify_case_failure(ValueError("original must match source range"))
        == "invalid_span"
    )
    assert (
        classify_case_failure(ValueError("selected finding identifiers conflict"))
        == "conflict"
    )


def test_auto_selection_skips_an_unhealthy_preferred_runtime() -> None:
    class UnhealthyClient:
        def preflight(self) -> RuntimeMetadata:
            raise OSError("connection refused")

        def generate(self, prompt: str) -> TimedResponse:
            raise AssertionError("unreachable")

    class HealthyClient:
        def preflight(self) -> RuntimeMetadata:
            return RuntimeMetadata("ollama", "local-test", "test")

        def generate(self, prompt: str) -> TimedResponse:
            return TimedResponse('{"schema_version":1,"findings":[]}', 1.0)

    selected_engine, selected = select_healthy_client(
        "auto",
        (("mlx", UnhealthyClient()), ("ollama", HealthyClient())),
    )

    assert selected_engine == "ollama"
    assert isinstance(selected, HealthyClient)


def test_run_cases_records_duplicate_findings_without_stopping() -> None:
    case = BenchmarkCase(
        case_id="duplicate",
        source="Ala ma kot.",
        expected_output="Ala ma kota.",
        tags=("inflection",),
        verification="llm_planned",
        tracking_issue=48,
        expected_findings=(GoldFinding("inflection", 7, 10, "kot", "kota"),),
    )
    finding = {
        "start": 7,
        "end": 10,
        "category": "inflection",
        "severity": "error",
        "message": "Odmiana.",
        "explanation": "Dopełniacz.",
        "original": "kot",
        "suggestion": "kota",
        "confidence": 0.9,
    }

    class DuplicateClient:
        def generate(self, prompt: str) -> TimedResponse:
            return TimedResponse(
                json.dumps({"schema_version": 1, "findings": [finding, finding]}),
                12.0,
            )

    observation = run_cases(DuplicateClient(), (case,))[0]

    assert observation.status == "duplicate"
    assert observation.valid_response is True
    assert observation.corrected_output == case.source


def test_run_cases_records_conflicting_edits_without_stopping() -> None:
    case = BenchmarkCase(
        case_id="conflict",
        source="Ala ma kota.",
        expected_output="Ola ma kota.",
        tags=("spelling",),
        verification="llm_planned",
        tracking_issue=48,
        expected_findings=(GoldFinding("spelling", 0, 3, "Ala", "Ola"),),
    )

    class ConflictClient:
        def generate(self, prompt: str) -> TimedResponse:
            return TimedResponse(
                json.dumps(
                    {
                        "schema_version": 1,
                        "findings": [
                            {
                                "start": 0,
                                "end": 3,
                                "category": "spelling",
                                "severity": "error",
                                "message": "Pisownia.",
                                "explanation": "Test konfliktu.",
                                "original": "Ala",
                                "suggestion": "Ola",
                                "confidence": 0.9,
                            },
                            {
                                "start": 0,
                                "end": 6,
                                "category": "style",
                                "severity": "suggestion",
                                "message": "Styl.",
                                "explanation": "Test konfliktu.",
                                "original": "Ala ma",
                                "suggestion": "Ola ma",
                                "confidence": 0.2,
                            },
                        ],
                    }
                ),
                12.0,
            )

    observation = run_cases(ConflictClient(), (case,))[0]

    assert observation.status == "conflict"
    assert observation.valid_response is True
    assert observation.corrected_output == case.source


def test_run_cases_records_unexpected_client_failure_without_stopping() -> None:
    case = BenchmarkCase(
        case_id="runtime-error",
        source="Poprawne zdanie.",
        expected_output="Poprawne zdanie.",
        tags=("negative",),
        verification="negative",
        tracking_issue=None,
        expected_findings=(),
    )

    class FailingClient:
        def generate(self, prompt: str) -> TimedResponse:
            raise RuntimeError("unexpected local runtime failure")

    observation = run_cases(FailingClient(), (case,))[0]

    assert observation.status == "application_failure"
    assert observation.valid_response is False


def test_run_cases_records_invalid_span_separately_from_invalid_schema() -> None:
    case = BenchmarkCase(
        case_id="bad-span",
        source="Poprawne zdanie.",
        expected_output="Poprawne zdanie.",
        tags=("negative",),
        verification="negative",
        tracking_issue=None,
        expected_findings=(),
    )

    class InvalidSpanClient:
        def generate(self, prompt: str) -> TimedResponse:
            return TimedResponse(
                json.dumps(
                    {
                        "schema_version": 1,
                        "findings": [
                            {
                                "start": 0,
                                "end": 100,
                                "category": "style",
                                "severity": "suggestion",
                                "message": "Zakres.",
                                "explanation": "Test zakresu.",
                                "original": "Poprawne zdanie.",
                                "suggestion": "Inne zdanie.",
                                "confidence": 0.2,
                            }
                        ],
                    }
                ),
                5.0,
            )

    observation = run_cases(InvalidSpanClient(), (case,))[0]

    assert observation.status == "invalid_span"
    assert observation.valid_response is False
