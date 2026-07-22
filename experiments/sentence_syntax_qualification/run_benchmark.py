"""Run one privacy-safe Qwen3 sentence syntax prompt variant for issue #74."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from experiments.role_prompt_benchmark.run_benchmark import OpenAICompatibleClient
from experiments.sentence_category_routing.experiment import (
    CaseObservation,
    EvaluationCase,
    Status,
    corpus_sha256,
    load_cases,
    summarize_observations,
)
from experiments.sentence_category_routing.protocol import validate_syntax_response
from experiments.sentence_category_routing.run_benchmark import (
    GenerationClient,
    TimedResponse,
    serialize_metrics,
)
from polis.llm import (
    TextEdit,
    build_proposal_verifier_prompt_request,
    validate_verifier_response,
)

from .experiment import (
    QualificationInput,
    Variant,
    load_qualification_config,
)
from .protocol import (
    build_correction_request,
    build_diagnostic_request,
    build_evidence_verifier_request,
    build_proposal_request,
    normalize_proposal,
    prepare_decision,
    validate_correction_response,
    validate_diagnostic_response,
    validate_evidence_verdict,
    validate_proposal_response,
)


def run_case(
    case: EvaluationCase,
    *,
    variant: Variant,
    client: GenerationClient,
) -> CaseObservation:
    """Run at most two model calls for one independently routed sentence."""

    source = case.routing_input.source
    decision = prepare_decision(QualificationInput(source))
    syntax: tuple[TextEdit, ...] = ()
    latency_ms = 0.0
    calls = 0
    status: Status = "valid"
    valid = True
    try:
        if decision.syntax_window is not None:
            if variant == "diagnose_then_correct-v1":
                first = client.generate(build_diagnostic_request(source, decision))
                calls += 1
                latency_ms += first.elapsed_ms
                diagnostic = validate_diagnostic_response(first.raw_response)
                if diagnostic.decision == "change":
                    second = client.generate(
                        build_correction_request(source, decision, diagnostic)
                    )
                    calls += 1
                    latency_ms += second.elapsed_ms
                    proposal = validate_correction_response(
                        second.raw_response,
                        source=source,
                        decision=decision,
                    )
                    syntax = () if proposal is None else proposal.edits
            else:
                first = client.generate(
                    build_proposal_request(source, decision, variant=variant)
                )
                calls += 1
                latency_ms += first.elapsed_ms
                if variant == "generic_verified-v1":
                    proposal = validate_syntax_response(
                        first.raw_response,
                        source=source,
                        decision=decision,
                    )
                    if proposal is not None:
                        proposal = normalize_proposal(source, proposal, decision)
                else:
                    proposal = validate_proposal_response(
                        first.raw_response,
                        source=source,
                        decision=decision,
                    )
                if proposal is not None:
                    verifier_request = (
                        build_proposal_verifier_prompt_request(
                            source, proposal.corrected_text
                        )
                        if variant == "generic_verified-v1"
                        else build_evidence_verifier_request(
                            source, proposal.corrected_text, decision
                        )
                    )
                    second = client.generate(verifier_request)
                    calls += 1
                    latency_ms += second.elapsed_ms
                    accepted = (
                        validate_verifier_response(second.raw_response)
                        if variant == "generic_verified-v1"
                        else validate_evidence_verdict(second.raw_response)
                    )
                    if accepted:
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
        raise RuntimeError("sentence qualification exceeded the two-call budget")
    if not valid:
        syntax = ()
    expected = tuple(
        TextEdit(edit.start, edit.end, edit.original, edit.suggestion)
        for edit in case.gold_edits
    )
    corrected = _apply_edits(source, syntax)
    outcome_hash = hashlib.sha256(
        json.dumps(
            {
                "calls": calls,
                "case_id": case.case_id,
                "edits": [
                    [edit.start, edit.end, edit.original, edit.suggestion]
                    for edit in syntax
                ],
                "status": status,
                "variant": variant,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return CaseObservation(
        case.case_id,
        case.focus,
        case.protected_negative,
        valid,
        syntax,
        expected,
        {
            "deterministic_punctuation": (),
            "deterministic_inflection": (),
            "model_syntax": syntax,
        },
        corrected == case.expected_output,
        latency_ms,
        calls,
        status,
        len(source),
        outcome_hash,
    )


def run_cases(
    cases: tuple[EvaluationCase, ...],
    *,
    variant: Variant,
    client: GenerationClient,
) -> tuple[CaseObservation, ...]:
    return tuple(run_case(case, variant=variant, client=client) for case in cases)


class StaticClient:
    """Small fake used by fast orchestration tests."""

    def __init__(self, responses: Sequence[TimedResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate(self, request: object) -> TimedResponse:
        del request
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _apply_edits(source: str, edits: tuple[TextEdit, ...]) -> str:
    corrected = source
    for edit in reversed(edits):
        if source[edit.start : edit.end] != edit.original:
            raise ValueError("edit original does not match source")
        corrected = corrected[: edit.start] + edit.suggestion + corrected[edit.end :]
    return corrected


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
    parser.add_argument("--variant", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--runtime-model")
    parser.add_argument("--runtime-pid", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split", choices=("development", "holdout"), default="development"
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    arguments = parser.parse_args(argv)
    config = load_qualification_config(arguments.config)
    if arguments.variant not in config.variants:
        raise ValueError("variant is not in the frozen qualification configuration")
    corpus_path = Path(config.corpus.path)
    if corpus_sha256(corpus_path) != config.corpus.sha256:
        raise ValueError("corpus hash mismatch")
    runtime_model = arguments.runtime_model or config.model.identifier
    runtime_client = OpenAICompatibleClient(
        arguments.base_url, runtime_model, arguments.timeout_seconds
    )
    metadata = runtime_client.preflight()
    client = cast(GenerationClient, runtime_client)
    cases = load_cases(corpus_path, split=arguments.split)
    swap_before = _swap_used_bytes()
    observations = run_cases(
        cases,
        variant=arguments.variant,
        client=client,
    )
    process_rss = _process_rss_bytes(arguments.runtime_pid)
    metrics = summarize_observations(
        arguments.variant,
        arguments.split,
        observations,
        loaded_memory_bytes=process_rss,
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
            "runtime_name": config.runtime.name,
            "runtime_version": config.runtime.version,
            "framework": config.runtime.framework,
            "framework_version": config.runtime.framework_version,
            "model_identifier": config.model.identifier,
            "model_revision": config.model.revision,
            "chat_template_args": config.runtime.chat_template_args,
        },
        "metrics": serialize_metrics(metrics),
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["StaticClient", "run_case", "run_cases"]
