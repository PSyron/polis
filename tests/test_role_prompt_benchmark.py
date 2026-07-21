from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, cast

import pytest
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from experiments.role_prompt_benchmark.run_benchmark import (
    ProtocolName,
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


class _UnavailableClient:
    def __init__(self) -> None:
        self.preflight_calls = 0

    def preflight(self) -> RuntimeMetadata:
        self.preflight_calls += 1
        raise OSError("service unavailable")

    def generate(self, request: object) -> TimedResponse:
        raise AssertionError("generate must not be called when preflight fails")


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
        latencies_ms=(12.0,),
    )
    request = client.calls[0]
    request = cast(ProtocolRequest, request)
    assert request.messages[0]["role"] == "system"
    assert request.messages[1]["role"] == "user"
    assert request.prompt_hash


def test_run_cases_with_multiple_repetitions_reports_cold_and_warm_metrics() -> None:
    case = _make_case(
        case_id="repeated",
        source="Ala ma kota.",
        expected_output="Ala ma kota.",
        tags=("syntax",),
        verification="positive",
        focus="syntax",
    )

    class RepeatingClient:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, request: object) -> TimedResponse:
            self.calls += 1
            return TimedResponse('{"corrected_text":"Ala ma kota."}', 10.0 * self.calls)

    observations = run_cases(RepeatingClient(), "specialist", (case,), repetitions=3)
    observation = observations[0]

    assert observation.latencies_ms == (10.0, 20.0, 30.0)
    assert observation.call_count == 3
    assert observation.elapsed_ms == 20.0

    report = summarize_observations(observations)
    assert report.repetitions == 3
    assert report.cold_latency_ms == 10.0
    assert report.warm_latency_ms == 25.0
    assert report.cold_p95_latency_ms == 10.0
    assert report.warm_p95_latency_ms == 30.0
    assert report.throughput_chars_per_second == pytest.approx(
        len(case.source) * 3 * 1000.0 / 60.0
    )


def test_run_cases_proposal_protocol_uses_two_steps_only_when_text_changes() -> None:
    case = _make_case(
        case_id="proposal_two_step",
        source="Idzie na spotkanie.",
        expected_output="Idzie na spotkanie.",
        tags=("syntax",),
        verification="positive",
        focus="syntax",
    )

    class SingleStepClient:
        def __init__(self) -> None:
            self.responses = iter([('{"corrected_text":"Idzie na spotkanie."}', 18.0)])
            self.calls = 0

        def generate(self, request: object) -> TimedResponse:
            self.calls += 1
            response = next(self.responses)
            return TimedResponse(raw_response=response[0], elapsed_ms=response[1])

    single_observation = run_cases(SingleStepClient(), "proposal", (case,))[0]
    assert single_observation.call_count == 1
    assert single_observation.corrected_output == case.source


def test_run_cases_proposal_protocol_changes_require_verification_step() -> None:
    case = _make_case(
        case_id="proposal_verification",
        source="Idziemy na spotkanie",
        expected_output="Idziemy na spotkanie!",
        tags=("punctuation",),
        verification="positive",
        focus="punctuation",
    )

    class TwoStepClient:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, request: object) -> TimedResponse:
            self.calls += 1
            if self.calls == 1:
                return TimedResponse(
                    raw_response='{"corrected_text":"Idziemy na spotkanie!"}',
                    elapsed_ms=8.0,
                )
            return TimedResponse(raw_response='{"decision":"accept"}', elapsed_ms=9.0)

    two_step_client = TwoStepClient()
    two_step_observation = run_cases(
        two_step_client, "proposal", (case,), repetitions=1
    )[0]
    assert two_step_observation.call_count == 2
    assert two_step_observation.corrected_output == "Idziemy na spotkanie!"

    assert two_step_observation.latencies_ms == (17.0,)


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

    payload = json.loads(report_as_json(report))

    assert "Ala ma kota" not in payload
    assert "Ala ma kota." not in payload
    assert "runtime" in payload
    assert payload["calls_per_case"] == 1.0


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


def test_select_healthy_client_skips_unavailable_engine_for_requested_profile() -> None:
    candidates = (
        ("ollama", _UnavailableClient()),
        ("mlx", _HealthyClient(engine="mlx", model="local-mlx")),
    )

    selected_name, selected = select_healthy_client("auto", candidates)
    assert selected_name == "mlx"
    assert isinstance(selected, _HealthyClient)
    assert selected.preflight_calls == 1


def test_select_healthy_client_respects_requested_engine() -> None:
    candidates = (
        ("ollama", _HealthyClient(engine="ollama", model="local-ollama")),
        ("mlx", _HealthyClient(engine="mlx", model="local-mlx")),
    )

    selected_name, selected = select_healthy_client("mlx", candidates)
    assert selected_name == "mlx"
    assert selected and isinstance(selected, _HealthyClient)
    assert selected._metadata.model_identifier == "local-mlx"


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


def test_main_runs_all_protocols_on_all_splits(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    dev_case = _make_case(
        case_id="dev-1",
        source="Ala ma kota.",
        expected_output="Ala ma kota.",
        tags=("syntax",),
        verification="positive",
        split="development",
        focus="syntax",
    )
    holdout_case = _make_case(
        case_id="holdout-1",
        source="Jan z Jadwiga.",
        expected_output="Jan z Jadwigą.",
        tags=("inflection", "name"),
        verification="positive",
        split="holdout",
        focus="inflection",
    )

    def fake_load_cases(
        path: Path, *, split: str = "development"
    ) -> tuple[RoleBenchmarkCase, ...]:
        if split == "development":
            return (dev_case,)
        if split == "holdout":
            return (holdout_case,)
        raise ValueError(f"unexpected split: {split!r}")

    def fake_generate(self: object, request: object) -> TimedResponse:
        return TimedResponse('{"corrected_text":"Ala ma kota."}', 5.0)

    class FakeClient:
        def __init__(self) -> None:
            self.preflight_calls = 0

        def preflight(self) -> RuntimeMetadata:
            self.preflight_calls += 1
            return RuntimeMetadata(
                engine="mlx",
                model_identifier="mlx-test-model",
                runtime_version="0.0.0",
            )

        def generate(self, request: object) -> TimedResponse:
            return fake_generate(self, request)

    class FakeBuilder:
        def __call__(self, *args: object, **kwargs: object) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr(
        "experiments.role_prompt_benchmark.run_benchmark.load_cases", fake_load_cases
    )
    monkeypatch.setattr(
        "experiments.role_prompt_benchmark.run_benchmark._build_client", FakeBuilder()
    )

    assert (
        main(
            [
                "--model",
                "mlx-test-model",
                "--protocol",
                "all",
                "--split",
                "all",
                "--engine",
                "mlx",
                "--base-url",
                "http://127.0.0.1:8080",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    protocols = {
        "finding",
        "one_field",
        "specialist",
        "candidate",
        "proposal",
    }

    assert payload["development"].keys() >= protocols
    assert payload["holdout"].keys() >= protocols
    assert set(payload["development"].keys()) == protocols
    assert set(payload["holdout"].keys()) == protocols
    for protocol_payload in payload["development"].values():
        protocol_payload = cast(dict[str, object], protocol_payload)
        assert protocol_payload["protocol"] in protocols
        assert protocol_payload["corpus_sha256"] is not None


def test_main_respects_repetitions_argument(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    case = _make_case(
        case_id="safe",
        source="Ala ma kota.",
        expected_output="Ala ma kota.",
        tags=("syntax",),
        verification="positive",
        split="development",
        focus="syntax",
    )

    def fake_run_cases(
        client: object,
        protocol: ProtocolName,
        cases: tuple[RoleBenchmarkCase, ...],
        *,
        repetitions: int = 1,
    ) -> tuple[RoleBenchmarkObservation, ...]:
        assert repetitions == 3
        assert len(cases) == 1
        assert cases[0] == case
        return (
            RoleBenchmarkObservation(
                case=case,
                protocol=protocol,
                valid_response=True,
                elapsed_ms=2.0,
                exact_output_match=True,
                exact_edit_match=True,
                corrected_output="Ala ma kota.",
                status="valid",
                call_count=3,
                latencies_ms=(1.0, 2.0, 3.0),
            ),
        )

    monkeypatch.setattr(
        "experiments.role_prompt_benchmark.run_benchmark.load_cases",
        lambda *_args, **_kwargs: (case,),
    )

    class FakeClient:
        def preflight(self) -> RuntimeMetadata:
            return RuntimeMetadata(
                engine="ollama",
                model_identifier="local-test",
                runtime_version="0.0.0",
            )

        def generate(self, request: object) -> TimedResponse:
            raise AssertionError("run_cases is monkeypatched in this test")

    class FakeBuilder:
        def __call__(self, *args: object, **kwargs: object) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr(
        "experiments.role_prompt_benchmark.run_benchmark._build_client", FakeBuilder()
    )
    monkeypatch.setattr(
        "experiments.role_prompt_benchmark.run_benchmark.run_cases", fake_run_cases
    )

    assert (
        main(
            [
                "--model",
                "local-test",
                "--protocol",
                "specialist",
                "--repetitions",
                "3",
                "--corpus",
                str(CORPUS_PATH),
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["repetitions"] == 3
    assert payload["cold_latency_ms"] == 1.0
    assert payload["warm_latency_ms"] == 2.5
    assert payload["cold_p95_latency_ms"] == 1.0
    assert payload["warm_p95_latency_ms"] == 3.0
