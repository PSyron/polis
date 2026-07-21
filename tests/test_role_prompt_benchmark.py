from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import pytest
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from experiments.role_prompt_benchmark.run_benchmark import (
    ProtocolRequest,
    RoleBenchmarkCase,
    RoleBenchmarkObservation,
    RoleBenchmarkReport,
    RuntimeMetadata,
    TimedResponse,
    _default_runtime_engine,
    _infer_focus,
    load_cases,
    main,
    report_as_json,
    run_cases,
    run_protocol_matrix,
    select_healthy_client,
    summarize_observations,
)

from polis.evaluation.correction_corpus import CorpusEdit, CorpusUsageError


class _HealthyClient:
    def __init__(self, *, engine: str, model: str) -> None:
        self._metadata = RuntimeMetadata(engine, model, "0.1.0")
        self.preflight_calls = 0
        self.generate_calls = 0

    def preflight(self) -> RuntimeMetadata:
        self.preflight_calls += 1
        return self._metadata

    def generate(self, request: object) -> TimedResponse:
        self.generate_calls += 1
        return TimedResponse('{"corrected_text":"Ala ma kota."}', 1.0)


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = (
    ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"
)


def _make_case(
    *,
    case_id: str,
    source: str,
    expected_output: str,
    tags: tuple[str, ...],
    verification: str,
    split: str = "development",
    focus: str = "syntax",
    edits: tuple[tuple[int, int, str, str, str], ...] = (),
) -> RoleBenchmarkCase:

    return RoleBenchmarkCase(
        case_id=case_id,
        source=source,
        expected_output=expected_output,
        tags=tags,
        verification="negative" if verification == "negative" else "positive",
        split=cast(Literal["development", "holdout"], split),
        focus=cast(Literal["inflection", "syntax", "punctuation"], focus),
        edits=tuple(
            CorpusEdit(
                category="inflection",
                start=start,
                end=end,
                original=original,
                suggestion=suggestion,
                rationale="",
            )
            for start, end, original, suggestion, _ in edits
        ),
    )


class CapturingClient:
    def __init__(self, response: str, *, latency_ms: float = 12.0) -> None:
        self.response = response
        self.latency_ms = latency_ms
        self.calls: list[object] = []

    def generate(self, request: object) -> TimedResponse:
        self.calls.append(request)
        return TimedResponse(raw_response=self.response, elapsed_ms=self.latency_ms)


def test_infers_focus_for_common_tag_sets() -> None:
    assert _infer_focus(("name", "surname"), "hard_negative") == "inflection"
    assert _infer_focus(("word_order",), "hard_negative") == "syntax"
    assert _infer_focus(("quotation",), "hard_negative") == "punctuation"
    assert _infer_focus(("agreement", "inflection"), "inflection") == "inflection"
    assert _infer_focus(("focus",), "syntax") == "syntax"


def test_load_cases_uses_human_reviewed_development_split() -> None:
    cases = load_cases(CORPUS_PATH)

    assert cases
    assert all(case.split == "development" for case in cases)
    assert any(case.verification == "negative" for case in cases)
    assert any(case.verification == "positive" for case in cases)


def test_load_cases_rejects_invalid_corpus_schema(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid_corpus.json"
    invalid_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="corpus"):
        load_cases(invalid_path)


def test_load_cases_loads_split_all() -> None:
    with pytest.raises(CorpusUsageError, match="frozen holdout"):
        load_cases(CORPUS_PATH, split="all")


def test_run_cases_validates_schema_and_records_exact_match() -> None:
    case = _make_case(
        case_id="inflection_001",
        source="Jan był z Anią na pikniku.",
        expected_output="Jan był z Anią na pikniku.",
        tags=("inflection", "name", "grammar"),
        verification="positive",
        focus="inflection",
    )
    client = CapturingClient('{"corrected_text":"Jan był z Anią na pikniku."}')

    observations = run_cases(client, "specialist", (case,))

    assert len(observations) == 1
    observation = observations[0]
    assert observation == RoleBenchmarkObservation(
        case=case,
        protocol="specialist",
        valid_response=True,
        elapsed_ms=12.0,
        exact_output_match=True,
        exact_edit_match=True,
        corrected_output="Jan był z Anią na pikniku.",
        status="valid_empty",
        call_count=1,
    )
    request = client.calls[0]
    request = cast(ProtocolRequest, request)
    assert request.messages[0]["role"] == "system"
    assert request.messages[1]["role"] == "user"
    assert request.prompt_hash


def test_run_cases_marks_invalid_schema_as_failed() -> None:
    case = _make_case(
        case_id="invalid_schema",
        source="Anna poszła do kina.",
        expected_output="Anna poszła do kina.",
        tags=("syntax",),
        verification="negative",
        focus="syntax",
    )
    client = CapturingClient("not json")

    observation = run_cases(client, "finding", (case,))[0]

    assert observation.valid_response is False
    assert observation.status == "invalid_schema"
    assert observation.corrected_output == case.source


def test_summarize_observations_tracks_negative_case_changes() -> None:
    negative_case = _make_case(
        case_id="negative",
        source="Poprawne zdanie.",
        expected_output="Poprawne zdanie.",
        tags=("hard_negative",),
        verification="negative",
        focus="syntax",
    )
    positive_case = _make_case(
        case_id="positive",
        source="Zobaczyłem Jana.",
        expected_output="Zobaczyłem Jana.",
        tags=("inflection",),
        verification="positive",
        focus="inflection",
    )

    report = summarize_observations(
        (
            RoleBenchmarkObservation(
                case=negative_case,
                protocol="specialist",
                valid_response=True,
                elapsed_ms=8.0,
                exact_output_match=False,
                exact_edit_match=False,
                corrected_output="Błędne zdanie.",
                status="valid",
            ),
            RoleBenchmarkObservation(
                case=positive_case,
                protocol="specialist",
                valid_response=True,
                elapsed_ms=16.0,
                exact_output_match=True,
                exact_edit_match=True,
                corrected_output="Zobaczyłem Jana.",
                status="valid",
            ),
        )
    )

    assert report.total_responses == 2
    assert report.valid_responses == 2
    assert report.negative_cases_changed == 1
    assert report.safety_eligible is False
    assert report.exact_output_matches == 1


def test_report_as_json_keeps_text_out_of_evidence() -> None:
    case = _make_case(
        case_id="safe",
        source="Ala ma kota.",
        expected_output="Ala ma kota.",
        tags=("syntax",),
        verification="positive",
        focus="syntax",
    )
    report = RoleBenchmarkReport(
        protocol="specialist",
        valid_responses=1,
        total_responses=1,
        negative_cases_changed=0,
        median_latency_ms=1.0,
        p95_latency_ms=1.0,
        throughput_chars_per_second=1000.0,
        exact_output_matches=1,
        exact_edit_matches=1,
        precision=1.0,
        recall=1.0,
        f1=1.0,
        edit_precision=1.0,
        edit_recall=1.0,
        edit_f1=1.0,
        schema_valid_rate=1.0,
        focus_metrics={
            "syntax": {
                "output_precision": 1.0,
                "output_recall": 1.0,
                "output_f1": 1.0,
                "output_true_positives": 1,
                "output_false_positives": 0,
                "output_false_negatives": 0,
                "edit_precision": 1.0,
                "edit_recall": 1.0,
                "edit_f1": 1.0,
                "edit_true_positives": 1,
                "edit_false_positives": 0,
                "edit_false_negatives": 0,
                "invalid": 0,
                "total": 1,
                "edit_total": 1,
            }
        },
        case_evidence=(
            RoleBenchmarkObservation(
                case=case,
                protocol="specialist",
                valid_response=True,
                elapsed_ms=1.0,
                exact_output_match=True,
                exact_edit_match=True,
                corrected_output="Ala ma kota.",
                status="valid",
            ),
        ),
    )

    payload = report_as_json(report)

    assert "Ala ma kota" not in payload
    assert "Ala ma kota." not in payload
    assert "runtime" in payload


def test_auto_client_selection_for_incompatible_url_is_not_used() -> None:
    class Healthy:
        def preflight(self) -> RuntimeMetadata:
            return RuntimeMetadata("ollama", "local-test", "0.20.7")

        def generate(self, request: object) -> TimedResponse:
            return TimedResponse('{"corrected_text":"Ala ma kota."}', 1.0)

    cases = (
        _make_case(
            case_id="safe",
            source="Ala ma kota.",
            expected_output="Ala ma kota.",
            tags=("syntax",),
            verification="positive",
            focus="syntax",
        ),
    )

    report = summarize_observations(
        (
            RoleBenchmarkObservation(
                case=cases[0],
                protocol="specialist",
                valid_response=True,
                elapsed_ms=1.0,
                exact_output_match=True,
                exact_edit_match=True,
                corrected_output="Ala ma kota.",
                status="valid",
            ),
        )
    )
    assert report.protocol == "specialist"


def test_main_returns_zero_and_prints_report(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    case = _make_case(
        case_id="safe",
        source="Ala ma kota.",
        expected_output="Ala ma kota.",
        tags=("syntax",),
        verification="positive",
        focus="syntax",
    )

    monkeypatch.setattr(
        "experiments.role_prompt_benchmark.run_benchmark.load_cases",
        lambda *_args, **_kwargs: (case,),
    )

    class FakeClient:
        def preflight(self) -> RuntimeMetadata:
            return RuntimeMetadata("ollama", "local-test", "0.20.7")

        def generate(self, request: object) -> TimedResponse:
            return TimedResponse('{"corrected_text":"Ala ma kota."}', 1.0)

    class FakeBuilder:
        def __call__(self, *args: object, **kwargs: object) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr(
        "experiments.role_prompt_benchmark.run_benchmark._build_client",
        FakeBuilder(),
    )

    assert (
        main(
            [
                "--model",
                "local-test",
                "--protocol",
                "specialist",
                "--corpus",
                str(CORPUS_PATH),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "safe" in output


def test_default_runtime_engine_prefers_mlx_on_darwin() -> None:
    assert _default_runtime_engine("auto") in {"mlx", "ollama"}


def test_select_healthy_client_picks_the_first_configured_service() -> None:
    candidates = (
        ("ollama", _HealthyClient(engine="ollama", model="local-ollama")),
        ("mlx", _HealthyClient(engine="mlx", model="local-mlx")),
    )
    selected_name, selected = select_healthy_client("auto", candidates)
    assert selected_name == "ollama"
    assert selected and cast(_HealthyClient, selected).preflight_calls == 1


def test_run_protocol_matrix_includes_runtime_metadata() -> None:
    cases = (
        _make_case(
            case_id="m1",
            source="Ala ma kota.",
            expected_output="Ala ma kota.",
            tags=("syntax",),
            verification="positive",
            split="development",
            focus="syntax",
        ),
    )

    client = _HealthyClient(engine="mlx", model="bielik-1.5b")
    matrix = run_protocol_matrix(
        client,
        ("specialist",),
        (("development", cases),),
        include_cases=True,
    )

    assert "development/specialist" in matrix
    payload = cast(dict[str, object], matrix["development/specialist"])
    runtime_payload = cast(dict[str, object], payload["runtime"])
    assert runtime_payload["model_identifier"] == "bielik-1.5b"
