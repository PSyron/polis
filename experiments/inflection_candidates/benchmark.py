"""Validation and scoring helpers for LanguageTool inflection candidates."""

from __future__ import annotations

import json
import hashlib
import math
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from polis.evaluation.correction_corpus import load_correction_corpus_json

CandidateClass = Literal["ordinary", "first_name", "surname"]
UnsupportedReason = Literal["no-analysis", "unsupported-pos", "no-alternatives"]
_TOKEN = re.compile(r"[^\W\d_]+(?:[.'’\-][^\W\d_]+)*\Z", re.UNICODE)


@dataclass(frozen=True)
class InflectionCandidate:
    """One context-free form synthesized from a source span."""

    candidate_id: str
    start: int
    end: int
    lemma: str | None
    form: str
    features: tuple[str, ...]


@dataclass(frozen=True)
class CandidateSpanResult:
    """All finite candidates and status for one requested source span."""

    start: int
    end: int
    surface: str
    unsupported_reason: UnsupportedReason | None
    candidates: tuple[InflectionCandidate, ...]


@dataclass(frozen=True)
class AuthoredCase:
    """One authored morphology probe that is independent from corpus gold."""

    case_id: str
    source: str
    start: int
    end: int
    surface: str
    candidate_class: CandidateClass
    expected_forms: tuple[str, ...]
    coverage: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkCase:
    """One independent candidate-recall probe."""

    case_id: str
    source: str
    start: int
    end: int
    surface: str
    candidate_class: CandidateClass
    expected_forms: tuple[str, ...]
    split: str


@dataclass(frozen=True)
class BenchmarkObservation:
    """One validated generator result with local wall-clock latency."""

    case: BenchmarkCase
    result: CandidateSpanResult
    elapsed_ms: float


@dataclass(frozen=True)
class TimedCandidateResponse:
    """One validated local response and its wall-clock time."""

    result: CandidateSpanResult
    elapsed_ms: float


class CandidateClient(Protocol):
    """Minimal transport used by the deterministic benchmark."""

    def generate(self, case: BenchmarkCase) -> TimedCandidateResponse:
        """Generate independent candidates for one explicit source span."""


@dataclass(frozen=True)
class CandidateClassMetrics:
    """Recall and finite-set size for one candidate class."""

    cases: int
    expected_forms: int
    expected_form_hits: int
    expected_form_recall: float
    mean_ambiguity: float
    p95_ambiguity: float
    unsupported_cases: int
    unchanged_coverage: float


@dataclass(frozen=True)
class CandidateCaseEvidence:
    """Non-text evidence safe to include in a report."""

    id: str
    candidate_class: CandidateClass
    expected_form_hits: int
    expected_form_count: int
    ambiguity: int
    unsupported: bool
    unchanged_covered: bool
    elapsed_ms: float


@dataclass(frozen=True)
class CandidateBenchmarkReport:
    """Aggregate morphology evidence without source or gold text."""

    total_cases: int
    classes: dict[CandidateClass, CandidateClassMetrics]
    expected_form_recall: float
    unchanged_coverage: float
    unsupported_cases: int
    warm_p50_ms: float
    warm_p95_ms: float
    cases: tuple[CandidateCaseEvidence, ...]


def _require_exact_keys(
    payload: dict[str, object], expected: frozenset[str], label: str
) -> None:
    if frozenset(payload) != expected:
        raise ValueError(f"{label} must contain exactly {sorted(expected)!r}")


def _require_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    return value


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not value:
        raise ValueError(f"{label} must not be empty")
    return value


def _parse_candidate(
    payload: object, *, start: int, end: int
) -> InflectionCandidate:
    if not isinstance(payload, dict):
        raise TypeError("candidate must be an object")
    candidate_payload = cast(dict[str, object], payload)
    _require_exact_keys(
        candidate_payload,
        frozenset({"candidate_id", "start", "end", "lemma", "form", "features"}),
        "candidate",
    )
    candidate_id = _require_str(candidate_payload["candidate_id"], "candidate_id")
    if not candidate_id.startswith("ltpl:"):
        raise ValueError("candidate_id must use the ltpl namespace")
    candidate_start = _require_int(candidate_payload["start"], "candidate start")
    candidate_end = _require_int(candidate_payload["end"], "candidate end")
    if (candidate_start, candidate_end) != (start, end):
        raise ValueError("candidate offsets must match the requested span")
    lemma_payload = candidate_payload["lemma"]
    if lemma_payload is not None and not isinstance(lemma_payload, str):
        raise TypeError("candidate lemma must be a string or null")
    form = _require_str(candidate_payload["form"], "candidate form")
    features_payload = candidate_payload["features"]
    if not isinstance(features_payload, list) or not all(
        isinstance(item, str) and item for item in features_payload
    ):
        raise TypeError("candidate features must be non-empty strings")
    features = tuple(cast(list[str], features_payload))
    if features != tuple(sorted(set(features))):
        raise ValueError("candidate features must be sorted and unique")
    expected_id = stable_candidate_id(
        start=candidate_start,
        end=candidate_end,
        lemma=lemma_payload,
        form=form,
        features=features,
    )
    if candidate_id != expected_id:
        raise ValueError("candidate_id does not match the visible candidate record")
    return InflectionCandidate(
        candidate_id=candidate_id,
        start=candidate_start,
        end=candidate_end,
        lemma=lemma_payload,
        form=form,
        features=features,
    )


def stable_candidate_id(
    *,
    start: int,
    end: int,
    lemma: str | None,
    form: str,
    features: tuple[str, ...],
) -> str:
    """Derive the public ID from every visible candidate field."""

    signature = "\0".join(
        (str(start), str(end), lemma or "", form, *features)
    ).encode("utf-8")
    return "ltpl:" + hashlib.sha256(signature).hexdigest()


def validate_response(
    raw: str,
    *,
    source_text: str,
    requested_spans: tuple[tuple[int, int], ...],
) -> tuple[CandidateSpanResult, ...]:
    """Validate a synthesis response against the original local request."""

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("synthesis response must be an object")
    response = cast(dict[str, object], payload)
    _require_exact_keys(
        response, frozenset({"operation", "language", "results"}), "response"
    )
    if response["operation"] != "synthesize" or response["language"] != "pl-PL":
        raise ValueError("response operation and language must match the request")
    raw_results = response["results"]
    if not isinstance(raw_results, list) or len(raw_results) != len(requested_spans):
        raise ValueError("response must contain one result per requested span")

    parsed: list[CandidateSpanResult] = []
    seen_candidate_ids: set[str] = set()
    for raw_result, requested_span in zip(raw_results, requested_spans, strict=True):
        if not isinstance(raw_result, dict):
            raise TypeError("span result must be an object")
        result_payload = cast(dict[str, object], raw_result)
        _require_exact_keys(
            result_payload,
            frozenset(
                {"start", "end", "surface", "unsupported_reason", "candidates"}
            ),
            "span result",
        )
        start = _require_int(result_payload["start"], "result start")
        end = _require_int(result_payload["end"], "result end")
        if (start, end) != requested_span:
            raise ValueError("result offsets must preserve requested span order")
        if start < 0 or end <= start or end > len(source_text):
            raise ValueError("result span is outside source text")
        surface = _require_str(result_payload["surface"], "surface")
        if source_text[start:end] != surface:
            raise ValueError("surface must equal the original source span")
        reason_payload = result_payload["unsupported_reason"]
        if reason_payload not in {None, "no-analysis", "unsupported-pos", "no-alternatives"}:
            raise ValueError("unsupported_reason is unknown")
        raw_candidates = result_payload["candidates"]
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise ValueError("every span result must contain a candidate")
        candidates = tuple(
            _parse_candidate(item, start=start, end=end) for item in raw_candidates
        )
        for candidate in candidates:
            if candidate.candidate_id in seen_candidate_ids:
                raise ValueError(f"duplicate candidate_id: {candidate.candidate_id!r}")
            seen_candidate_ids.add(candidate.candidate_id)
        if surface not in {candidate.form for candidate in candidates}:
            raise ValueError("candidate set must preserve the unchanged surface")
        parsed.append(
            CandidateSpanResult(
                start=start,
                end=end,
                surface=surface,
                unsupported_reason=reason_payload,
                candidates=candidates,
            )
        )
    return tuple(parsed)


def load_authored_cases(path: Path) -> tuple[AuthoredCase, ...]:
    """Load project-authored probes for morphology edge behavior."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("authored cases require schema_version 1")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("authored cases must be a non-empty list")
    cases: list[AuthoredCase] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise TypeError("authored case must be an object")
        case = cast(dict[str, object], raw_case)
        source = _require_str(case.get("source"), "case source")
        start = _require_int(case.get("start"), "case start")
        end = _require_int(case.get("end"), "case end")
        surface = _require_str(case.get("surface"), "case surface")
        if start < 0 or end <= start or end > len(source) or source[start:end] != surface:
            raise ValueError("authored case span must select its surface")
        candidate_class = case.get("candidate_class")
        if candidate_class not in {"ordinary", "first_name", "surname"}:
            raise ValueError("authored candidate_class is invalid")
        expected_forms = case.get("expected_forms")
        coverage = case.get("coverage")
        if not isinstance(expected_forms, list) or not all(
            isinstance(item, str) and item for item in expected_forms
        ):
            raise TypeError("expected_forms must contain strings")
        if not isinstance(coverage, list) or not all(
            isinstance(item, str) and item for item in coverage
        ):
            raise TypeError("coverage must contain strings")
        cases.append(
            AuthoredCase(
                case_id=_require_str(case.get("id"), "case id"),
                source=source,
                start=start,
                end=end,
                surface=surface,
                candidate_class=candidate_class,
                expected_forms=tuple(cast(list[str], expected_forms)),
                coverage=tuple(cast(list[str], coverage)),
            )
        )
    return tuple(cases)


def load_corpus_cases(
    path: Path, *, split: Literal["development", "holdout"]
) -> tuple[BenchmarkCase, ...]:
    """Select eligible inflection spans while keeping gold only as an oracle."""

    corpus = load_correction_corpus_json(path)
    if corpus.holdout_state != "frozen":
        raise ValueError("candidate benchmark requires the frozen corpus")
    selected: list[BenchmarkCase] = []
    for corpus_case in corpus.cases:
        if (
            corpus_case.split != split
            or corpus_case.stratum != "inflection"
            or corpus_case.review.status != "human-reviewed"
        ):
            continue
        candidate_class: CandidateClass
        if "surname" in corpus_case.tags:
            candidate_class = "surname"
        elif "name" in corpus_case.tags:
            candidate_class = "first_name"
        else:
            candidate_class = "ordinary"
        for edit_index, edit in enumerate(corpus_case.edits, start=1):
            if (
                edit.category != "inflection"
                or _TOKEN.fullmatch(edit.original) is None
                or _TOKEN.fullmatch(edit.suggestion) is None
            ):
                continue
            if corpus_case.input[edit.start : edit.end] != edit.original:
                raise ValueError(f"corpus edit span mismatch in {corpus_case.id}")
            selected.append(
                BenchmarkCase(
                    case_id=f"{corpus_case.id}:{edit_index}",
                    source=corpus_case.input,
                    start=edit.start,
                    end=edit.end,
                    surface=edit.original,
                    candidate_class=candidate_class,
                    expected_forms=(edit.suggestion,),
                    split=split,
                )
            )
    return tuple(selected)


def authored_benchmark_cases(path: Path) -> tuple[BenchmarkCase, ...]:
    """Convert authored edge probes to the common benchmark contract."""

    return tuple(
        BenchmarkCase(
            case_id=case.case_id,
            source=case.source,
            start=case.start,
            end=case.end,
            surface=case.surface,
            candidate_class=case.candidate_class,
            expected_forms=case.expected_forms,
            split="authored",
        )
        for case in load_authored_cases(path)
    )


def build_request_payload(case: BenchmarkCase) -> dict[str, object]:
    """Build the only data sent to the local morphology process."""

    return {
        "operation": "synthesize",
        "language": "pl-PL",
        "text": case.source,
        "spans": [{"start": case.start, "end": case.end}],
    }


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _case_evidence(observation: BenchmarkObservation) -> CandidateCaseEvidence:
    forms = {candidate.form for candidate in observation.result.candidates}
    hits = sum(form in forms for form in observation.case.expected_forms)
    return CandidateCaseEvidence(
        id=observation.case.case_id,
        candidate_class=observation.case.candidate_class,
        expected_form_hits=hits,
        expected_form_count=len(observation.case.expected_forms),
        ambiguity=len(forms),
        unsupported=observation.result.unsupported_reason is not None,
        unchanged_covered=observation.case.surface in forms,
        elapsed_ms=observation.elapsed_ms,
    )


def _class_metrics(
    evidence: tuple[CandidateCaseEvidence, ...], candidate_class: CandidateClass
) -> CandidateClassMetrics:
    selected = tuple(
        item for item in evidence if item.candidate_class == candidate_class
    )
    expected_forms = sum(item.expected_form_count for item in selected)
    expected_hits = sum(item.expected_form_hits for item in selected)
    ambiguities = [float(item.ambiguity) for item in selected]
    return CandidateClassMetrics(
        cases=len(selected),
        expected_forms=expected_forms,
        expected_form_hits=expected_hits,
        expected_form_recall=expected_hits / expected_forms if expected_forms else 0.0,
        mean_ambiguity=statistics.fmean(ambiguities) if ambiguities else 0.0,
        p95_ambiguity=_nearest_rank(ambiguities, 0.95),
        unsupported_cases=sum(item.unsupported for item in selected),
        unchanged_coverage=(
            sum(item.unchanged_covered for item in selected) / len(selected)
            if selected
            else 0.0
        ),
    )


def summarize_observations(
    observations: tuple[BenchmarkObservation, ...],
    *,
    exclude_first_latency: bool = False,
) -> CandidateBenchmarkReport:
    """Aggregate recall, ambiguity, safety, and warm latency."""

    if not observations:
        raise ValueError("candidate benchmark requires observations")
    evidence = tuple(_case_evidence(observation) for observation in observations)
    expected_forms = sum(item.expected_form_count for item in evidence)
    expected_hits = sum(item.expected_form_hits for item in evidence)
    latency_evidence = evidence[1:] if exclude_first_latency else evidence
    latencies = [item.elapsed_ms for item in latency_evidence]
    return CandidateBenchmarkReport(
        total_cases=len(evidence),
        classes={
            candidate_class: _class_metrics(evidence, candidate_class)
            for candidate_class in ("ordinary", "first_name", "surname")
        },
        expected_form_recall=expected_hits / expected_forms if expected_forms else 0.0,
        unchanged_coverage=sum(item.unchanged_covered for item in evidence)
        / len(evidence),
        unsupported_cases=sum(item.unsupported for item in evidence),
        warm_p50_ms=statistics.median(latencies) if latencies else 0.0,
        warm_p95_ms=_nearest_rank(latencies, 0.95),
        cases=evidence,
    )


def run_cases(
    client: CandidateClient, cases: tuple[BenchmarkCase, ...]
) -> tuple[BenchmarkObservation, ...]:
    """Run cases sequentially against one warm local process."""

    observations: list[BenchmarkObservation] = []
    for case in cases:
        response = client.generate(case)
        observations.append(
            BenchmarkObservation(
                case=case,
                result=response.result,
                elapsed_ms=response.elapsed_ms,
            )
        )
    return tuple(observations)


def report_as_json(report: CandidateBenchmarkReport) -> str:
    """Serialize aggregate and case-ID evidence without analyzed text."""

    return json.dumps(asdict(report), ensure_ascii=False, sort_keys=True)


__all__ = [
    "AuthoredCase",
    "BenchmarkCase",
    "BenchmarkObservation",
    "CandidateBenchmarkReport",
    "CandidateClass",
    "CandidateClient",
    "CandidateSpanResult",
    "InflectionCandidate",
    "TimedCandidateResponse",
    "UnsupportedReason",
    "authored_benchmark_cases",
    "build_request_payload",
    "load_authored_cases",
    "load_corpus_cases",
    "report_as_json",
    "run_cases",
    "stable_candidate_id",
    "summarize_observations",
    "validate_response",
]
