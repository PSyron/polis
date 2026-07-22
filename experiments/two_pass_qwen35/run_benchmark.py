"""Execute the local constrained Qwen3.5 two-pass benchmark for issue #68."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Protocol

from experiments.inflection_candidates.benchmark import BenchmarkCase
from experiments.inflection_candidates.run_benchmark import LocalStdioClient
from experiments.role_prompt_benchmark.run_benchmark import (
    OllamaClient,
    TimedResponse,
    _infer_focus,
)
from experiments.two_pass_qwen35.experiment import (
    CaseObservation,
    ExperimentConfig,
    VariantMetrics,
    load_experiment_config,
    select_development_variant,
    summarize_observations,
)
from polis.evaluation.correction_corpus import (
    CorrectionCorpusCase,
    load_correction_corpus_json,
    select_cases_for_purpose,
)
from polis.llm import (
    DiagnosticPromptVariant,
    FiniteCandidate,
    PromptRequest,
    TextEdit,
    build_diagnostic_prompt_request,
    build_evidence_bound_corrected_text_prompt_request,
    build_inflection_candidate_prompt_request,
    derive_text_edits,
    validate_candidate_selection_response,
    validate_diagnostic_response,
    validate_evidence_bound_corrected_text_response,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).with_name("config.json")
DEFAULT_MODULE_ROOT = ROOT / "third_party" / "languagetool-pl"
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class PromptClient(Protocol):
    def generate(self, request: object) -> TimedResponse:
        """Run one local structured prompt."""


class CandidateProvider(Protocol):
    def generate(
        self, source_text: str, start: int, end: int
    ) -> tuple[FiniteCandidate, ...]:
        """Return finite forms for one exact source token."""


@dataclass(frozen=True, slots=True)
class TwoPassResult:
    corrected_text: str
    valid_response: bool
    status: Literal[
        "valid", "invalid_response", "unavailable", "timed_out", "unsupported"
    ]
    call_count: int
    elapsed_ms: float
    routed_focus: str | None


@dataclass(frozen=True, slots=True)
class FrozenSelection:
    experiment_id: str
    variant: str
    prompt_hash: str
    model_digest: str
    corpus_sha256: str
    configuration_sha256: str


@dataclass(frozen=True)
class OllamaPromptClient:
    """Pinned loopback-only Ollama transport using native JSON schema output."""

    base_url: str
    model: str
    digest: str
    timeout_seconds: float

    def __post_init__(self) -> None:
        from urllib.parse import urlparse

        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in _LOOPBACK_HOSTS:
            raise ValueError("Ollama URL must use an HTTP loopback host")
        if len(self.digest) != 64:
            raise ValueError("model digest must be a full SHA-256")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def generate(self, request: object) -> TimedResponse:
        if not isinstance(request, PromptRequest):
            raise TypeError("benchmark transport requires PromptRequest")
        return OllamaClient(
            self.base_url, self.model, self.timeout_seconds
        ).generate(request)

    def preflight(self) -> tuple[str, int | None]:
        """Verify runtime version, installed digest, and current loaded memory."""

        from urllib.request import Request, urlopen

        def get(path: str) -> dict[str, object]:
            request = Request(f"{self.base_url.rstrip('/')}{path}", method="GET")
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                value = json.loads(response.read().decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("Ollama metadata must be an object")
            return value

        version_payload = get("/api/version")
        tags = get("/api/tags")
        processes = get("/api/ps")
        version = version_payload.get("version")
        if not isinstance(version, str):
            raise ValueError("Ollama version is unavailable")
        models = tags.get("models")
        if not isinstance(models, list) or not any(
            isinstance(item, dict)
            and item.get("name") == self.model
            and item.get("digest") == self.digest
            for item in models
        ):
            raise OSError("pinned Ollama model digest is unavailable")
        loaded = None
        process_models = processes.get("models")
        if isinstance(process_models, list):
            selected = next(
                (
                    item
                    for item in process_models
                    if isinstance(item, dict) and item.get("name") == self.model
                ),
                None,
            )
            if isinstance(selected, dict):
                value = selected.get("size_vram", selected.get("size"))
                if isinstance(value, int) and not isinstance(value, bool):
                    loaded = value
        return version, loaded


class LanguageToolCandidateProvider:
    """Adapt the pinned Polish synthesizer to diagnostic source spans."""

    def __init__(self, client: LocalStdioClient) -> None:
        self._client = client

    def generate(
        self, source_text: str, start: int, end: int
    ) -> tuple[FiniteCandidate, ...]:
        response = self._client.generate(
            BenchmarkCase(
                case_id="diagnostic",
                source=source_text,
                start=start,
                end=end,
                surface=source_text[start:end],
                candidate_class="ordinary",
                expected_forms=(),
                split="runtime",
            )
        )
        if response.result.unsupported_reason is not None:
            return ()
        return tuple(
            FiniteCandidate(
                candidate.candidate_id,
                candidate.start,
                candidate.end,
                candidate.form,
                candidate.lemma,
                candidate.features,
            )
            for candidate in response.result.candidates
        )


def run_two_pass_text(
    client: PromptClient,
    candidates: CandidateProvider,
    source_text: str,
    *,
    variant: DiagnosticPromptVariant,
    protected_spans: tuple[tuple[int, int], ...] = (),
) -> TwoPassResult:
    """Run at most two model calls and fail closed on every invalid result."""

    call_count = 0
    elapsed_ms = 0.0
    try:
        diagnostic_request = build_diagnostic_prompt_request(
            source_text, variant=variant
        )
        call_count += 1
        diagnostic_response = client.generate(diagnostic_request)
        elapsed_ms += diagnostic_response.elapsed_ms
        route = validate_diagnostic_response(
            diagnostic_response.raw_response, source_text=source_text
        )
        if route.decision == "unchanged":
            return TwoPassResult(source_text, True, "valid", 1, elapsed_ms, None)
        if (
            route.focus is None
            or route.evidence is None
            or route.evidence_start is None
            or route.evidence_end is None
        ):
            raise ValueError("inspect route is incomplete")

        if route.focus == "inflection":
            finite = candidates.generate(
                source_text, route.evidence_start, route.evidence_end
            )
            if not finite:
                return TwoPassResult(
                    source_text, True, "unsupported", 1, elapsed_ms, route.focus
                )
            request = build_inflection_candidate_prompt_request(source_text, finite)
            call_count += 1
            response = client.generate(request)
            elapsed_ms += response.elapsed_ms
            selected = validate_candidate_selection_response(
                response.raw_response,
                candidate_ids=tuple(item.candidate_id for item in finite),
            )
            if selected is None:
                corrected = source_text
            else:
                candidate = next(item for item in finite if item.candidate_id == selected)
                if any(
                    candidate.start < protected_end and candidate.end > protected_start
                    for protected_start, protected_end in protected_spans
                ):
                    raise ValueError("candidate overlaps a protected span")
                corrected = (
                    source_text[: candidate.start]
                    + candidate.form
                    + source_text[candidate.end :]
                )
            return TwoPassResult(
                corrected, True, "valid", call_count, elapsed_ms, route.focus
            )

        request = build_evidence_bound_corrected_text_prompt_request(
            source_text, focus=route.focus, evidence=route.evidence
        )
        call_count += 1
        response = client.generate(request)
        elapsed_ms += response.elapsed_ms
        corrected = validate_evidence_bound_corrected_text_response(
            response.raw_response,
            source_text=source_text,
            focus=route.focus,
            evidence=route.evidence,
            protected_spans=protected_spans,
        )
        return TwoPassResult(
            corrected, True, "valid", call_count, elapsed_ms, route.focus
        )
    except TimeoutError:
        return TwoPassResult(
            source_text, False, "timed_out", call_count, elapsed_ms, None
        )
    except (OSError, ConnectionError):
        return TwoPassResult(
            source_text, False, "unavailable", call_count, elapsed_ms, None
        )
    except Exception:
        return TwoPassResult(
            source_text, False, "invalid_response", call_count, elapsed_ms, None
        )


def freeze_development_selection(
    config: ExperimentConfig,
    metrics: VariantMetrics,
    output_path: Path,
) -> FrozenSelection:
    """Persist an eligible development choice before any holdout access."""

    selection = select_development_variant(config.selection, (metrics,))
    if selection.selected != metrics.variant:
        raise ValueError("development variant is not holdout-eligible")
    frozen = FrozenSelection(
        config.experiment_id,
        metrics.variant,
        metrics.prompt_hash,
        config.model.digest,
        config.corpus.sha256,
        _configuration_sha256(config),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(frozen), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return frozen


def reserve_holdout_run(
    config: ExperimentConfig,
    selection_path: Path,
    sentinel_path: Path,
) -> FrozenSelection:
    """Validate the frozen selection and irreversibly reserve its sole holdout run."""

    raw = json.loads(selection_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != set(FrozenSelection.__annotations__):
        raise ValueError("frozen selection fields are invalid")
    frozen = FrozenSelection(**raw)
    if (
        frozen.experiment_id != config.experiment_id
        or frozen.model_digest != config.model.digest
        or frozen.corpus_sha256 != config.corpus.sha256
        or frozen.configuration_sha256 != _configuration_sha256(config)
    ):
        raise ValueError("frozen selection does not match experiment configuration")
    expected = next(
        (item for item in config.prompt_variants if item.name == frozen.variant), None
    )
    if expected is None or expected.prompt_hash != frozen.prompt_hash:
        raise ValueError("frozen prompt selection is not predeclared")
    sentinel_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sentinel_path.open("x", encoding="utf-8") as stream:
            stream.write(frozen.configuration_sha256 + "\n")
    except FileExistsError:
        raise FileExistsError("holdout run is already reserved") from None
    return frozen


def _configuration_sha256(config: ExperimentConfig) -> str:
    return hashlib.sha256(
        json.dumps(asdict(config), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def verify_prompt_hashes(config: ExperimentConfig) -> None:
    """Fail closed when any recorded prompt differs from its implementation."""

    for variant in config.prompt_variants:
        actual = build_diagnostic_prompt_request(
            "hash probe", variant=variant.name
        ).prompt_hash
        if actual != variant.prompt_hash:
            raise ValueError("diagnostic prompt hash mismatch")
    source = "Idę z Lis."
    start = source.index("Lis")
    operations = {
        "inflection_candidate": build_inflection_candidate_prompt_request(
            source,
            (
                FiniteCandidate("c0", start, start + 3, "Lis"),
                FiniteCandidate("c1", start, start + 3, "Lisem"),
            ),
        ).prompt_hash,
        "syntax_correction": build_evidence_bound_corrected_text_prompt_request(
            "Chcę jutro spotkamy się.",
            focus="syntax",
            evidence="jutro spotkamy",
        ).prompt_hash,
        "punctuation_correction": build_evidence_bound_corrected_text_prompt_request(
            "Sądzę że zdążymy.", focus="punctuation", evidence="że"
        ).prompt_hash,
    }
    if operations != config.operation_prompt_hashes:
        raise ValueError("operation prompt hash mismatch")


def _expected_edits(case: CorrectionCorpusCase) -> tuple[TextEdit, ...]:
    return tuple(
        TextEdit(edit.start, edit.end, edit.original, edit.suggestion)
        for edit in case.edits
    )


def _case_observation(
    case: CorrectionCorpusCase, result: TwoPassResult
) -> CaseObservation:
    try:
        actual = derive_text_edits(case.input, result.corrected_text)
    except ValueError:
        actual = ()
    expected = _expected_edits(case)
    focus = _infer_focus(case.tags, case.stratum)
    return CaseObservation(
        case_id=case.id,
        focus=focus,
        protected_negative=case.protected_phenomenon is not None,
        valid_response=result.valid_response,
        actual_edits=actual,
        expected_edits=expected,
        exact_output_match=result.corrected_text == case.expected_output,
        latency_ms=result.elapsed_ms,
        call_count=result.call_count,
        outcome_hash=hashlib.sha256(result.corrected_text.encode()).hexdigest(),
        status=result.status,
        source_char_count=len(case.input),
    )


def _swap_used_bytes() -> int:
    result = subprocess.run(
        ("sysctl", "-n", "vm.swapusage"),
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    match = re.search(r"used = ([0-9.]+)([MG])", result.stdout)
    if match is None:
        raise RuntimeError("cannot parse macOS swap usage")
    multiplier = 1024**2 if match.group(2) == "M" else 1024**3
    return round(float(match.group(1)) * multiplier)


def _ollama_process_rss_bytes(model: str) -> int:
    result = subprocess.run(
        ("ps", "-axo", "rss=,command="),
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    marker = f"--model {model}"
    values = []
    for line in result.stdout.splitlines():
        if "ollama runner" not in line or marker not in line:
            continue
        rss, _, _ = line.strip().partition(" ")
        if rss.isdigit():
            values.append(int(rss) * 1_024)
    return max(values, default=0)


def _safe_metrics(metrics: VariantMetrics) -> dict[str, object]:
    payload = asdict(metrics)
    payload["case_evidence"] = [
        {
            "case_id": item.case_id,
            "focus": item.focus,
            "protected_negative": item.protected_negative,
            "valid_response": item.valid_response,
            "exact_output_match": item.exact_output_match,
            "latency_ms": item.latency_ms,
            "call_count": item.call_count,
            "outcome_hash": item.outcome_hash,
            "status": item.status,
            "source_char_count": item.source_char_count,
            "actual_edit_count": len(item.actual_edits),
            "expected_edit_count": len(item.expected_edits),
        }
        for item in metrics.case_evidence
    ]
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "holdout"), default="development")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--module-root", type=Path, default=DEFAULT_MODULE_ROOT)
    arguments = parser.parse_args(argv)

    config = load_experiment_config(arguments.config)
    verify_prompt_hashes(config)
    corpus_path = ROOT / config.corpus.path
    if hashlib.sha256(corpus_path.read_bytes()).hexdigest() != config.corpus.sha256:
        raise ValueError("corpus hash mismatch")
    client = OllamaPromptClient(
        arguments.base_url,
        config.model.identifier,
        config.model.digest,
        arguments.timeout_seconds,
    )
    runtime_version, _ = client.preflight()
    if runtime_version != config.runtime.version:
        raise ValueError("Ollama runtime version mismatch")

    corpus = load_correction_corpus_json(corpus_path)
    if arguments.split == "development":
        cases = select_cases_for_purpose(corpus, purpose="benchmark")
        variants = tuple(item.name for item in config.prompt_variants)
    else:
        frozen = reserve_holdout_run(
            config,
            arguments.work_dir / "selection.json",
            arguments.work_dir / "holdout.started",
        )
        cases = select_cases_for_purpose(corpus, purpose="quality_gate")
        variants = (frozen.variant,)

    arguments.work_dir.mkdir(parents=True, exist_ok=True)
    runner = arguments.module_root / "scripts" / "run_stdio.sh"
    swap_before = _swap_used_bytes()
    all_metrics: list[VariantMetrics] = []
    with LocalStdioClient(
        command=(os.fspath(runner),),
        cwd=arguments.module_root,
        timeout_seconds=arguments.timeout_seconds,
    ) as lt_client:
        provider = LanguageToolCandidateProvider(lt_client)
        for variant_name in variants:
            variant = next(
                item for item in config.prompt_variants if item.name == variant_name
            )
            observations = []
            for case in cases:
                protected = tuple(
                    (span.start, span.end) for span in case.entity_spans
                )
                result = run_two_pass_text(
                    client,
                    provider,
                    case.input,
                    variant=variant.name,
                    protected_spans=(protected if _infer_focus(case.tags, case.stratum) != "inflection" else ()),
                )
                observations.append(_case_observation(case, result))
            _, loaded_memory = client.preflight()
            all_metrics.append(
                summarize_observations(
                    variant.name,
                    variant.prompt_hash,
                    arguments.split,
                    observations,
                    loaded_memory_bytes=loaded_memory or 0,
                    swap_delta_bytes=max(0, _swap_used_bytes() - swap_before),
                    process_rss_bytes=_ollama_process_rss_bytes(
                        config.model.identifier
                    ),
                )
            )

    selection = select_development_variant(config.selection, all_metrics)
    payload = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "configuration_sha256": _configuration_sha256(config),
        "split": arguments.split,
        "environment": {
            "hardware": platform.machine(),
            "operating_system": platform.platform(),
            "runtime_version": runtime_version,
            "model_digest": config.model.digest,
        },
        "metrics": [_safe_metrics(item) for item in all_metrics],
        "selection": asdict(selection),
    }
    output = arguments.work_dir / f"{arguments.split}.json"
    output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if arguments.split == "development" and selection.selected is not None:
        selected_metrics = next(
            item for item in all_metrics if item.variant == selection.selected
        )
        freeze_development_selection(
            config, selected_metrics, arguments.work_dir / "selection.json"
        )
    print(output)
    return 0 if selection.selected is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FrozenSelection",
    "LanguageToolCandidateProvider",
    "OllamaPromptClient",
    "TwoPassResult",
    "freeze_development_selection",
    "main",
    "reserve_holdout_run",
    "run_two_pass_text",
    "verify_prompt_hashes",
]
