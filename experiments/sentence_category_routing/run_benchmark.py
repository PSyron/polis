"""Privacy-safe sentence benchmark orchestration for issue #69."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import select
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TextIO, cast
from urllib.request import Request, urlopen

from experiments.role_prompt_benchmark.run_benchmark import (
    OllamaClient,
    OpenAICompatibleClient,
)
from polis.core import AnalysisOptions, Category, Finding
from polis.llm import (
    PromptRequest,
    TextEdit,
    build_proposal_verifier_prompt_request,
    validate_verifier_response,
)
from polis.rules.languagetool import LanguageToolRuleConfig, LocalLanguageToolRule

from .experiment import (
    CaseObservation,
    DevelopmentSelection,
    EvaluationCase,
    ModelMetrics,
    Status,
    corpus_sha256,
    load_cases,
    load_experiment_config,
    summarize_observations,
)
from .protocol import build_syntax_request, validate_syntax_response
from .routing import route_sentence


@dataclass(frozen=True, slots=True)
class TimedResponse:
    raw_response: str
    elapsed_ms: float


class GenerationClient(Protocol):
    def generate(self, request: object) -> TimedResponse: ...


class DeterministicChecker(Protocol):
    def check(self, source: str) -> tuple[tuple[Finding, ...], float]: ...


def build_ollama_payload(model: str, request: PromptRequest) -> dict[str, object]:
    """Use JSON mode; application validation remains authoritative."""

    return {
        "model": model,
        "messages": request.messages,
        "stream": False,
        "format": "json",
        "think": False,
        "options": request.generation,
    }


class OllamaJsonClient:
    """Ollama transport that avoids unsupported runtime schema grammars."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self._delegate = OllamaClient(base_url, model, timeout_seconds)
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, request: object) -> TimedResponse:
        if not isinstance(request, PromptRequest):
            raise TypeError("Ollama benchmark transport requires PromptRequest")
        message = Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=json.dumps(
                build_ollama_payload(self.model, request),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        with urlopen(message, timeout=self.timeout_seconds) as response:  # noqa: S310
            raw = json.loads(response.read().decode("utf-8"))
        elapsed_ms = (time.perf_counter() - started) * 1_000
        if not isinstance(raw, dict):
            raise ValueError("Ollama response must be an object")
        envelope = raw.get("message")
        if not isinstance(envelope, dict) or not isinstance(
            envelope.get("content"), str
        ):
            raise ValueError("Ollama response must contain message.content")
        return TimedResponse(envelope["content"], elapsed_ms)

    def preflight(self) -> object:
        return self._delegate.preflight()


class _StdioTransport:
    def __init__(self, command: tuple[str, ...], cwd: Path, timeout_seconds: float):
        self._command = command
        self._cwd = cwd
        self._timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[str] | None = None

    def __enter__(self) -> _StdioTransport:
        self._process = subprocess.Popen(
            self._command,
            cwd=self._cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        return self

    def __exit__(self, *args: object) -> None:
        process = self._process
        if process is None:
            return
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=3)

    def check(
        self, text: str, *, language: str, timeout_seconds: float
    ) -> Mapping[str, object]:
        process = self._require_process()
        stdin = cast(TextIO, process.stdin)
        stdout = cast(TextIO, process.stdout)
        stdin.write(
            json.dumps(
                {"language": language, "text": text},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        stdin.flush()
        ready, _, _ = select.select(
            [stdout], [], [], min(timeout_seconds, self._timeout_seconds)
        )
        if not ready:
            raise TimeoutError("LanguageTool stdio response timed out")
        line = stdout.readline()
        if not line:
            raise OSError("LanguageTool stdio process ended unexpectedly")
        payload: Any = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError("LanguageTool response must be an object")
        return cast(Mapping[str, object], payload)

    def _require_process(self) -> subprocess.Popen[str]:
        if self._process is None or self._process.poll() is not None:
            raise OSError("LanguageTool stdio process is unavailable")
        if self._process.stdin is None or self._process.stdout is None:
            raise OSError("LanguageTool stdio pipes are unavailable")
        return self._process


class LanguageToolStdioChecker:
    """Run the pinned two-rule LanguageTool subset through local stdio."""

    def __init__(self, transport: _StdioTransport, timeout_seconds: float) -> None:
        self._rule = LocalLanguageToolRule(
            LanguageToolRuleConfig(
                "http://127.0.0.1:1", timeout_seconds=timeout_seconds
            ),
            transport,
        )

    def check(self, source: str) -> tuple[tuple[Finding, ...], float]:
        started = time.perf_counter()
        findings = self._rule.find(
            source,
            options=AnalysisOptions(categories=frozenset({Category.PUNCTUATION})),
        )
        return findings, (time.perf_counter() - started) * 1_000


def run_cases(
    cases: tuple[EvaluationCase, ...],
    *,
    checker: DeterministicChecker,
    client: GenerationClient,
) -> tuple[CaseObservation, ...]:
    """Run deterministic analysis before optional residual syntax calls."""

    observations: list[CaseObservation] = []
    for case in cases:
        findings, deterministic_latency_ms = checker.check(case.routing_input.source)
        observations.append(
            run_case(
                case,
                deterministic_findings=findings,
                client=client,
                deterministic_latency_ms=deterministic_latency_ms,
            )
        )
    return tuple(observations)


def run_case(
    case: EvaluationCase,
    *,
    deterministic_findings: tuple[Finding, ...],
    client: GenerationClient,
    deterministic_latency_ms: float = 0.0,
) -> CaseObservation:
    """Run one sentence while keeping model work bounded and suggestion-only."""

    routing_input = case.routing_input.__class__(
        source=case.routing_input.source,
        deterministic_findings=deterministic_findings,
        entity_spans=case.routing_input.entity_spans,
    )
    decision = route_sentence(routing_input)
    punctuation = _finding_edits(decision.deterministic_punctuation)
    inflection = _finding_edits(decision.deterministic_inflection)
    syntax: tuple[TextEdit, ...] = ()
    calls = 0
    if deterministic_latency_ms < 0:
        raise ValueError("deterministic latency must be non-negative")
    latency_ms = deterministic_latency_ms
    status: Status = "valid"
    valid = True

    if decision.syntax_window is not None:
        try:
            response = client.generate(build_syntax_request(case.routing_input.source, decision))
            calls += 1
            latency_ms += response.elapsed_ms
            proposal = validate_syntax_response(
                response.raw_response,
                source=case.routing_input.source,
                decision=decision,
            )
            if proposal is not None:
                verifier = build_proposal_verifier_prompt_request(
                    case.routing_input.source,
                    proposal.corrected_text,
                )
                verdict = client.generate(verifier)
                calls += 1
                latency_ms += verdict.elapsed_ms
                if validate_verifier_response(verdict.raw_response):
                    syntax = proposal.edits
        except TimeoutError:
            status = "timed_out"
            valid = False
        except OSError:
            status = "unavailable"
            valid = False
        except (TypeError, ValueError, RuntimeError, StopIteration):
            status = "invalid_response"
            valid = False

    if calls > 2:
        raise RuntimeError("sentence benchmark exceeded the two-call budget")
    if not valid:
        syntax = ()
    channels = {
        "deterministic_punctuation": punctuation,
        "deterministic_inflection": inflection,
        "model_syntax": syntax,
    }
    actual = _merge_non_conflicting(punctuation, inflection, syntax)
    expected = tuple(
        TextEdit(edit.start, edit.end, edit.original, edit.suggestion)
        for edit in case.gold_edits
    )
    corrected = _apply_edits(case.routing_input.source, actual)
    outcome_hash = hashlib.sha256(
        json.dumps(
            {
                "calls": calls,
                "case_id": case.case_id,
                "edits": [
                    [edit.start, edit.end, edit.original, edit.suggestion]
                    for edit in actual
                ],
                "status": status,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return CaseObservation(
        case_id=case.case_id,
        focus=case.focus,
        protected_negative=case.protected_negative,
        valid_response=valid,
        actual_edits=actual,
        expected_edits=expected,
        channel_edits=channels,
        exact_output_match=corrected == case.expected_output,
        latency_ms=latency_ms,
        call_count=calls,
        status=status,
        source_char_count=len(case.routing_input.source),
        outcome_hash=outcome_hash,
    )


def freeze_selection(
    selection: DevelopmentSelection, config_path: Path, destination: Path
) -> None:
    """Persist an eligible development choice before holdout access."""

    if selection.selected is None:
        raise ValueError("development selection is not holdout-eligible")
    payload = {
        "configuration_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "selected": selection.selected,
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def reserve_holdout_once(
    selection_path: Path, config_path: Path, marker_path: Path
) -> None:
    """Atomically reserve the sole holdout run for the frozen configuration."""

    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {
        "configuration_sha256",
        "selected",
    }:
        raise ValueError("frozen selection has an invalid shape")
    expected_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    if payload["configuration_sha256"] != expected_hash:
        raise ValueError("frozen selection does not match configuration")
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with marker_path.open("x", encoding="utf-8") as marker:
            json.dump(
                {
                    "configuration_sha256": expected_hash,
                    "selected": payload["selected"],
                },
                marker,
                sort_keys=True,
            )
            marker.write("\n")
    except FileExistsError as error:
        raise FileExistsError("holdout run is already reserved") from error


def _finding_edits(findings: tuple[Finding, ...]) -> tuple[TextEdit, ...]:
    return tuple(
        TextEdit(
            finding.start,
            finding.end,
            finding.original,
            finding.suggestion,
        )
        for finding in findings
        if finding.suggestion is not None
    )


def _merge_non_conflicting(*groups: tuple[TextEdit, ...]) -> tuple[TextEdit, ...]:
    selected: list[TextEdit] = []
    for edit in (item for group in groups for item in group):
        if any(_edits_conflict(edit, existing) for existing in selected):
            continue
        selected.append(edit)
    return tuple(sorted(selected, key=lambda item: (item.start, item.end)))


def _edits_conflict(first: TextEdit, second: TextEdit) -> bool:
    first_start = int(first.start)
    first_end = int(first.end)
    second_start = int(second.start)
    second_end = int(second.end)
    first_insertion = first_start == first_end
    second_insertion = second_start == second_end
    if first_insertion and second_insertion:
        return first_start == second_start
    if first_insertion:
        return second_start <= first_start < second_end
    if second_insertion:
        return first_start <= second_start < first_end
    return max(first_start, second_start) < min(first_end, second_end)


def _apply_edits(source: str, edits: tuple[TextEdit, ...]) -> str:
    corrected = source
    for edit in reversed(edits):
        if source[edit.start : edit.end] != edit.original:
            raise ValueError("edit original does not match source")
        corrected = corrected[: edit.start] + edit.suggestion + corrected[edit.end :]
    return corrected


def serialize_metrics(metrics: ModelMetrics) -> dict[str, object]:
    return {
        "model": metrics.model,
        "split": metrics.split,
        "total_cases": metrics.total_cases,
        "valid_responses": metrics.valid_responses,
        "negative_cases": metrics.negative_cases,
        "negative_changes": metrics.negative_changes,
        "true_positive_edits": metrics.true_positive_edits,
        "false_positive_edits": metrics.false_positive_edits,
        "false_negative_edits": metrics.false_negative_edits,
        "exact_output_matches": metrics.exact_output_matches,
        "median_latency_ms": metrics.median_latency_ms,
        "warm_p95_latency_ms": metrics.warm_p95_latency_ms,
        "mean_call_count": metrics.mean_call_count,
        "maximum_call_count": metrics.maximum_call_count,
        "loaded_memory_bytes": metrics.loaded_memory_bytes,
        "swap_delta_bytes": metrics.swap_delta_bytes,
        "process_rss_bytes": metrics.process_rss_bytes,
        "focus_metrics": {
            focus: {
                "true_positive_edits": value.true_positive_edits,
                "false_positive_edits": value.false_positive_edits,
                "false_negative_edits": value.false_negative_edits,
                "edit_precision": value.edit_precision,
                "edit_recall": value.edit_recall,
            }
            for focus, value in metrics.focus_metrics.items()
        },
        "channel_metrics": {
            channel: {
                "true_positive_edits": value.true_positive_edits,
                "false_positive_edits": value.false_positive_edits,
                "false_negative_edits": value.false_negative_edits,
                "edit_precision": value.edit_precision,
                "edit_recall": value.edit_recall,
            }
            for channel, value in metrics.channel_metrics.items()
        },
        "case_evidence": [
            {
                "case_id": item.case_id,
                "focus": item.focus,
                "protected_negative": item.protected_negative,
                "valid_response": item.valid_response,
                "exact_output_match": item.exact_output_match,
                "latency_ms": item.latency_ms,
                "call_count": item.call_count,
                "status": item.status,
                "source_char_count": item.source_char_count,
                "outcome_hash": item.outcome_hash,
                "actual_edit_count": len(item.actual_edits),
                "expected_edit_count": len(item.expected_edits),
                "channel_edit_counts": {
                    channel: len(edits)
                    for channel, edits in item.channel_edits.items()
                },
            }
            for item in metrics.case_evidence
        ],
    }


def _swap_used_bytes() -> int:
    completed = subprocess.run(
        ("sysctl", "-n", "vm.swapusage"),
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"used = ([0-9.]+)([MG])", completed.stdout)
    if match is None:
        raise ValueError("cannot parse macOS swap usage")
    multiplier = 1_048_576 if match.group(2) == "M" else 1_073_741_824
    return int(float(match.group(1)) * multiplier)


def _process_rss_bytes(process_id: int | None) -> int:
    if process_id is None:
        return 0
    completed = subprocess.run(
        ("ps", "-o", "rss=", "-p", str(process_id)),
        check=True,
        capture_output=True,
        text=True,
    )
    return int(completed.stdout.strip()) * 1_024


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("config.json")
    )
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--runtime-model")
    parser.add_argument("--runtime-pid", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split", choices=("development", "holdout"), default="development"
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--module-root", type=Path, default=Path("third_party/languagetool-pl")
    )
    arguments = parser.parse_args(argv)

    config = load_experiment_config(arguments.config)
    corpus_path = Path(config.corpus.path)
    if corpus_sha256(corpus_path) != config.corpus.sha256:
        raise ValueError("corpus hash mismatch")
    model = next(
        (item for item in config.models if item.name == arguments.model_name), None
    )
    if model is None:
        raise ValueError("model-name is not in the frozen matrix")
    runtime_model = arguments.runtime_model or model.identifier
    if model.engine == "mlx":
        client: Any = OpenAICompatibleClient(
            arguments.base_url, runtime_model, arguments.timeout_seconds
        )
    else:
        client = OllamaJsonClient(
            arguments.base_url, runtime_model, arguments.timeout_seconds
        )
    metadata = client.preflight()

    cases = load_cases(corpus_path, split=cast(Any, arguments.split))
    swap_before = _swap_used_bytes()
    module_root = arguments.module_root.resolve()
    transport = _StdioTransport(
        (os.fspath(module_root / "scripts" / "run_stdio.sh"),),
        module_root,
        arguments.timeout_seconds,
    )
    with transport:
        checker = LanguageToolStdioChecker(transport, arguments.timeout_seconds)
        observations = run_cases(cases, checker=checker, client=client)
    process_rss = _process_rss_bytes(arguments.runtime_pid)
    metadata = client.preflight()
    loaded_memory = metadata.loaded_memory_bytes or process_rss
    metrics = summarize_observations(
        model.name,
        arguments.split,
        observations,
        loaded_memory_bytes=loaded_memory,
        swap_delta_bytes=max(0, _swap_used_bytes() - swap_before),
        process_rss_bytes=process_rss,
    )
    payload = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "configuration_sha256": hashlib.sha256(
            arguments.config.read_bytes()
        ).hexdigest(),
        "environment": {
            "hardware": platform.machine(),
            "operating_system": platform.platform(),
            "runtime_engine": metadata.engine,
            "runtime_version": metadata.runtime_version,
            "model_identifier": model.identifier,
            "model_revision": model.revision,
        },
        "metrics": serialize_metrics(metrics),
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(arguments.output)
    return 0


__all__ = [
    "DeterministicChecker",
    "GenerationClient",
    "LanguageToolStdioChecker",
    "OllamaJsonClient",
    "TimedResponse",
    "freeze_selection",
    "build_ollama_payload",
    "reserve_holdout_once",
    "run_case",
    "run_cases",
    "serialize_metrics",
]


if __name__ == "__main__":
    raise SystemExit(main())
