from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from urllib.request import Request

import pytest
from experiments.real_llm_benchmark.run_benchmark import (
    BenchmarkCase,
    OllamaClient,
    load_cases,
    score_case,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.json"


def test_loader_uses_planned_llm_and_negative_v2_cases() -> None:
    cases = load_cases(CORPUS_PATH)

    assert {case.verification for case in cases} == {"llm_planned", "negative"}
    assert all(case.expected_output for case in cases)


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


def test_client_posts_deterministic_json_to_local_generate_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"response":"{\\"schema_version\\":1,\\"findings\\":[]}"}'

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
    assert request.full_url == "http://127.0.0.1:11434/api/generate"
    assert request.data is not None
    payload = json.loads(cast(bytes, request.data).decode("utf-8"))
    assert payload == {
        "format": "json",
        "model": "qwen3:0.6b",
        "options": {"seed": 42, "temperature": 0},
        "prompt": "strict prompt",
        "stream": False,
    }


def test_negative_finding_disqualifies_candidate() -> None:
    case = BenchmarkCase(
        case_id="correct-name",
        source="Rozmawiałem z Anną Kowalską.",
        expected_output="Rozmawiałem z Anną Kowalską.",
        tags=("negative", "name"),
        verification="negative",
        tracking_issue=None,
    )

    score = score_case(
        case,
        corrected_output="Rozmawiałem z Anną Kowalską!",
        valid_response=True,
        elapsed_ms=12.0,
    )

    assert score.disqualified is True
    assert score.exact_match is False
