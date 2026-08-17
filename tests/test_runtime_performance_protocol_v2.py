from __future__ import annotations

import io
import json
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Any

import pytest

from polis.evaluation.runtime_performance_protocol import (
    RuntimePerformanceProtocolError,
    run_isolated_measurement,
    run_worker,
)

REQUEST = "polis.runtime-performance.request"


def _line(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"


def test_worker_strict_round_trip_without_dataset_import() -> None:
    dataset_module_before = sys.modules.get("polis.evaluation.quality_dataset")
    stdin = io.StringIO(
        _line(
            {
                "schema_id": REQUEST,
                "schema_version": 2,
                "operation": "start",
                "profile": "morphology",
            }
        )
        + _line(
            {
                "schema_id": REQUEST,
                "schema_version": 2,
                "operation": "analyze",
                "sequence": 0,
                "text": "Wogole nie wiem.",
            }
        )
        + _line(
            {
                "schema_id": REQUEST,
                "schema_version": 2,
                "operation": "measurement_start",
            }
        )
        + _line({"schema_id": REQUEST, "schema_version": 2, "operation": "finish"})
    )
    stdout = io.StringIO()
    assert run_worker(stdin, stdout) == 0
    responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [response["operation"] for response in responses] == [
        "started",
        "analyzed",
        "measurement_started",
        "finished",
    ]
    assert responses[0]["profile"] == "morphology"
    assert responses[0]["morphology_provider"]["provider"] == "morfeusz2"
    assert responses[1]["sequence"] == 0
    assert responses[1]["findings"][0]["source"] == "rule:spelling.wogole"
    assert responses[1]["duration_ns"] >= 0
    assert (
        responses[2]["measurement_start_rss_bytes"] >= responses[0]["startup_rss_bytes"]
    )
    assert responses[3]["peak_rss_bytes"] >= responses[2]["measurement_start_rss_bytes"]
    assert sys.modules.get("polis.evaluation.quality_dataset") is dataset_module_before


def test_worker_rejects_unknown_fields_fail_closed() -> None:
    stdin = io.StringIO(
        _line(
            {
                "schema_id": REQUEST,
                "schema_version": 2,
                "operation": "start",
                "profile": "morphology",
                "unexpected": True,
            }
        )
    )
    with pytest.raises(RuntimePerformanceProtocolError, match="fields mismatch"):
        run_worker(stdin, io.StringIO())


def test_worker_rejects_unknown_operation_fail_closed() -> None:
    stdin = io.StringIO(
        _line(
            {
                "schema_id": REQUEST,
                "schema_version": 2,
                "operation": "start",
                "profile": "morphology",
            }
        )
        + _line(
            {
                "schema_id": REQUEST,
                "schema_version": 2,
                "operation": "not_supported",
            }
        )
    )
    with pytest.raises(
        RuntimePerformanceProtocolError, match="unsupported worker operation"
    ):
        run_worker(stdin, io.StringIO())


def test_worker_rejects_malformed_measurement_start_request() -> None:
    stdin = io.StringIO(
        _line(
            {
                "schema_id": REQUEST,
                "schema_version": 2,
                "operation": "start",
                "profile": "morphology",
            }
        )
        + _line(
            {
                "schema_id": REQUEST,
                "schema_version": 2,
                "operation": "measurement_start",
                "unexpected": True,
            }
        )
    )
    with pytest.raises(RuntimePerformanceProtocolError, match="fields mismatch"):
        run_worker(stdin, io.StringIO())


@pytest.mark.parametrize(
    ("operations", "message"),
    [
        (("finish",), "finish requires measurement start checkpoint"),
        (
            ("measurement_start", "measurement_start"),
            "measurement start checkpoint already recorded",
        ),
    ],
)
def test_worker_enforces_single_measurement_start_before_finish(
    operations: tuple[str, ...], message: str
) -> None:
    requests = _line(
        {
            "schema_id": REQUEST,
            "schema_version": 2,
            "operation": "start",
            "profile": "morphology",
        }
    )
    requests += "".join(
        _line(
            {
                "schema_id": REQUEST,
                "schema_version": 2,
                "operation": operation,
            }
        )
        for operation in operations
    )
    with pytest.raises(RuntimePerformanceProtocolError, match=message):
        run_worker(io.StringIO(requests), io.StringIO())


def test_worker_module_exits_two_for_malformed_input() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "polis.evaluation.runtime_performance_worker"],
        input="{}\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 2
    assert "error:" in completed.stderr


class _FakeStdout:
    def __init__(self, initial: list[str]) -> None:
        self._lines = deque(initial)

    def push(self, value: dict[str, object]) -> None:
        self._lines.append(_line(value))

    def readline(self) -> str:
        return self._lines.popleft()


class _FakeStdin:
    def __init__(self, stdout: _FakeStdout, events: list[dict[str, Any]]) -> None:
        self._stdout = stdout
        self.events = events

    def write(self, value: str) -> int:
        request = json.loads(value)
        assert isinstance(request, dict)
        self.events.append(request)
        operation = request["operation"]
        if operation == "analyze":
            self._stdout.push(
                {
                    "schema_id": "polis.runtime-performance.response",
                    "schema_version": 2,
                    "operation": "analyzed",
                    "sequence": request["sequence"],
                    "duration_ns": 1,
                    "findings": [],
                }
            )
        elif operation == "measurement_start":
            self._stdout.push(
                {
                    "schema_id": "polis.runtime-performance.response",
                    "schema_version": 2,
                    "operation": "measurement_started",
                    "measurement_start_rss_bytes": 20,
                }
            )
        elif operation == "finish":
            self._stdout.push(
                {
                    "schema_id": "polis.runtime-performance.response",
                    "schema_version": 2,
                    "operation": "finished",
                    "peak_rss_bytes": 30,
                }
            )
        return len(value)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeProcess:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        stdout = _FakeStdout(
            [
                _line(
                    {
                        "schema_id": "polis.runtime-performance.response",
                        "schema_version": 2,
                        "operation": "started",
                        "profile": "default",
                        "environment": {"python_version": "3.13.12"},
                        "morphology_provider": None,
                        "startup_rss_bytes": 10,
                    }
                )
            ]
        )
        self.stdin = _FakeStdin(stdout, events)
        self.stdout = stdout
        self.stderr = io.StringIO()

    def wait(self, *, timeout: float) -> int:
        assert timeout == 30
        return 0


def test_parent_requests_checkpoint_between_warmup_and_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, Any]] = []
    process = _FakeProcess(events)

    def popen(*_args: object, **_kwargs: object) -> _FakeProcess:
        return process

    monkeypatch.setattr(
        "polis.evaluation.runtime_performance_protocol.subprocess.Popen", popen
    )

    measurement = run_isolated_measurement(
        python=sys.executable,
        profile="default",
        texts=("tekst",),
        warmup_repetitions=1,
        measured_repetitions=2,
    )

    assert [event["operation"] for event in events] == [
        "start",
        "analyze",
        "measurement_start",
        "analyze",
        "analyze",
        "finish",
    ]
    assert measurement.measurement_start_rss_bytes == 20


def test_parent_client_measures_deterministically_in_fresh_worker() -> None:
    measurement = run_isolated_measurement(
        python=sys.executable,
        profile="morphology",
        texts=("Wogole nie wiem.", "To zdanie jest poprawne."),
        warmup_repetitions=1,
        measured_repetitions=2,
    )
    assert measurement.profile == "morphology"
    assert measurement.environment["python_version"]
    assert measurement.morphology_provider == {
        "provider": "morfeusz2",
        "package_version": "1.99.15",
        "dictionary_id": "pl.sgjp.sgjp-2026.06.01",
        "dictionary_notice_sha256": (
            "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
        ),
    }
    assert measurement.startup_rss_bytes > 0
    assert measurement.measurement_start_rss_bytes >= measurement.startup_rss_bytes
    assert measurement.peak_rss_bytes >= measurement.measurement_start_rss_bytes
    assert len(measurement.durations_ns) == 4
    assert len(measurement.findings_by_case) == 2
    assert len(measurement.findings_sha256) == 64
    assert measurement.findings_by_case[0][0]["source"] == "rule:spelling.wogole"


def test_worker_source_contains_no_dataset_or_scoring_import() -> None:
    worker = Path("src/polis/evaluation/runtime_performance_worker.py").read_text(
        encoding="utf-8"
    )
    protocol = Path("src/polis/evaluation/runtime_performance_protocol.py").read_text(
        encoding="utf-8"
    )
    banned = (
        "quality_dataset",
        "load_quality_dataset",
        "evaluate_baseline",
        "quality_report",
    )
    assert all(name not in worker for name in banned)
    # Parent/client module may own orchestration; the worker loop must not
    # import or retain dataset/scoring state.
    worker_loop = protocol[
        protocol.index("def run_worker") : protocol.index(
            "def run_isolated_measurement"
        )
    ]
    assert all(name not in worker_loop for name in banned)
