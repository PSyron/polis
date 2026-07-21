"""Rules-first orchestration for optional specialist model suggestions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from polis.core import (
    AnalysisTimeoutError,
    BackendUnavailableError,
    Category,
    Confidence,
    Finding,
    InvalidBackendResponseError,
    Severity,
    Source,
    SourceKind,
)
from polis.llm import (
    FiniteCandidate,
    PromptRequest,
    build_inflection_candidate_prompt_request,
    build_proposal_verifier_prompt_request,
    build_specialist_corrected_text_prompt_request,
    derive_text_edits,
    validate_candidate_selection_response,
    validate_corrected_text_response,
    validate_verifier_response,
)
from polis.segmentation import Sentence, segment_sentences

HybridSuggestionStatus = Literal[
    "complete",
    "unavailable",
    "timed_out",
    "invalid_response",
]

_SAFE_FAILURE = "specialist suggestion operation failed"
_UNQUALIFIED_CONFIDENCE = Confidence(0.0)
_URL = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_NUMBER = re.compile(r"(?<!\w)\d[\d.,]*(?!\w)")
_QUOTED = re.compile(r"(?:\"[^\"]*\"|„[^”]*”|«[^»]*»)")


@dataclass(frozen=True, slots=True)
class InflectionTask:
    """Finite candidate selection for one sentence-local source span."""

    candidates: tuple[FiniteCandidate, ...]
    protected_spans: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class SyntaxTask:
    """Bounded corrected-text proposal for one sentence."""

    protected_spans: tuple[tuple[int, int], ...] = ()


type SpecialistTask = InflectionTask | SyntaxTask


@runtime_checkable
class SpecialistTaskRouter(Protocol):
    """Deterministically identify unresolved tasks for one sentence."""

    def tasks(
        self,
        sentence: str,
        *,
        deterministic_findings: tuple[Finding, ...],
    ) -> tuple[SpecialistTask, ...]: ...


@runtime_checkable
class SpecialistBackend(Protocol):
    """Generate one raw response from a model-independent specialist request."""

    @property
    def name(self) -> str: ...

    async def generate(self, request: PromptRequest) -> str: ...


@dataclass(frozen=True, slots=True)
class HybridSuggestionRun:
    """Safe result of one optional specialist suggestion pass."""

    status: HybridSuggestionStatus
    backend: str
    suggestions: tuple[Finding, ...]
    model_calls: int
    operation_versions: tuple[str, ...]
    safe_error: str | None = None


class HybridSuggestionEngine:
    """Run routed specialist tasks without granting automatic correction."""

    def __init__(
        self,
        *,
        backend: SpecialistBackend,
        router: SpecialistTaskRouter,
        calibrated_confidence: Confidence = _UNQUALIFIED_CONFIDENCE,
    ) -> None:
        if not isinstance(backend, SpecialistBackend):
            raise TypeError("backend must implement SpecialistBackend")
        if not isinstance(router, SpecialistTaskRouter):
            raise TypeError("router must implement SpecialistTaskRouter")
        if not isinstance(calibrated_confidence, Confidence):
            raise TypeError("calibrated_confidence must be a Confidence")
        source = Source(SourceKind.LLM, backend.name)
        self._backend = backend
        self._router = router
        self._confidence = calibrated_confidence
        self._source = source

    @property
    def backend_name(self) -> str:
        """Return the safe stable backend identifier."""

        return self._backend.name

    async def suggest(
        self,
        text: str,
        *,
        deterministic_findings: tuple[Finding, ...],
    ) -> HybridSuggestionRun:
        """Return validated reviewable suggestions in original paragraph offsets."""

        if not isinstance(text, str):
            raise TypeError("text must be a string")
        for finding in deterministic_findings:
            if not isinstance(finding, Finding):
                raise TypeError("deterministic_findings must contain Finding values")

        suggestions: list[Finding] = []
        operation_versions: list[str] = []
        call_counter = [0]

        try:
            for sentence in segment_sentences(text):
                local_findings = _findings_for_sentence(
                    deterministic_findings,
                    sentence,
                )
                tasks = self._router.tasks(
                    sentence.text,
                    deterministic_findings=local_findings,
                )
                if not isinstance(tasks, tuple):
                    raise TypeError("router tasks must be a tuple")
                for task in tasks:
                    if isinstance(task, InflectionTask):
                        task_suggestions, versions = await self._run_inflection(
                            sentence,
                            task,
                            call_counter,
                            operation_versions,
                        )
                    elif isinstance(task, SyntaxTask):
                        task_suggestions, versions = await self._run_syntax(
                            sentence,
                            task,
                            call_counter,
                            operation_versions,
                        )
                    else:
                        raise TypeError(
                            "router returned an unsupported specialist task"
                        )
                    suggestions.extend(task_suggestions)
                    _extend_unique(operation_versions, versions)
        except BackendUnavailableError:
            return self._failed_run(
                "unavailable", suggestions, call_counter[0], operation_versions
            )
        except AnalysisTimeoutError:
            return self._failed_run(
                "timed_out", suggestions, call_counter[0], operation_versions
            )
        except (InvalidBackendResponseError, TypeError, ValueError, RuntimeError):
            return self._failed_run(
                "invalid_response", suggestions, call_counter[0], operation_versions
            )

        return HybridSuggestionRun(
            status="complete",
            backend=self.backend_name,
            suggestions=tuple(suggestions),
            model_calls=call_counter[0],
            operation_versions=tuple(operation_versions),
        )

    async def _run_inflection(
        self,
        sentence: Sentence,
        task: InflectionTask,
        call_counter: list[int],
        operation_versions: list[str],
    ) -> tuple[tuple[Finding, ...], tuple[str, ...]]:
        _validate_spans(sentence.text, task.protected_spans)
        request = build_inflection_candidate_prompt_request(
            sentence.text,
            task.candidates,
        )
        raw = await self._generate(request, call_counter, operation_versions)
        selected_id = validate_candidate_selection_response(
            raw,
            candidate_ids=tuple(item.candidate_id for item in task.candidates),
        )
        versions: tuple[str, ...] = (_operation_version(request),)
        if selected_id is None:
            return (), versions

        selected = next(
            candidate
            for candidate in task.candidates
            if candidate.candidate_id == selected_id
        )
        original = sentence.text[selected.start : selected.end]
        if selected.form == original:
            return (), versions
        if _span_overlaps_any(selected.start, selected.end, task.protected_spans):
            raise ValueError("candidate target overlaps a protected source span")

        proposal = (
            sentence.text[: selected.start]
            + selected.form
            + sentence.text[selected.end :]
        )
        verifier = build_proposal_verifier_prompt_request(sentence.text, proposal)
        raw_verdict = await self._generate(
            verifier,
            call_counter,
            operation_versions,
        )
        versions += (_operation_version(verifier),)
        if not validate_verifier_response(raw_verdict):
            return (), versions

        finding = Finding.create(
            category=Category.INFLECTION,
            severity=Severity.SUGGESTION,
            message="Proponowana korekta fleksyjna.",
            explanation=(
                "Wybrano jedną z dostarczonych form i zweryfikowano propozycję."
            ),
            original=original,
            suggestion=selected.form,
            start=sentence.start + selected.start,
            end=sentence.start + selected.end,
            confidence=self._confidence,
            source=self._source,
        )
        return (finding,), versions

    async def _run_syntax(
        self,
        sentence: Sentence,
        task: SyntaxTask,
        call_counter: list[int],
        operation_versions: list[str],
    ) -> tuple[tuple[Finding, ...], tuple[str, ...]]:
        protected_spans = _merge_spans(
            (*task.protected_spans, *_automatic_protected_spans(sentence.text))
        )
        _validate_spans(sentence.text, protected_spans)
        request = build_specialist_corrected_text_prompt_request(
            sentence.text,
            focus="syntax",
        )
        raw = await self._generate(request, call_counter, operation_versions)
        corrected = validate_corrected_text_response(
            raw,
            source_text=sentence.text,
            focus="syntax",
        )
        versions: tuple[str, ...] = (_operation_version(request),)
        if corrected == sentence.text:
            return (), versions

        edits = derive_text_edits(
            sentence.text,
            corrected,
            protected_spans=protected_spans,
        )
        verifier = build_proposal_verifier_prompt_request(sentence.text, corrected)
        raw_verdict = await self._generate(
            verifier,
            call_counter,
            operation_versions,
        )
        versions += (_operation_version(verifier),)
        if not validate_verifier_response(raw_verdict):
            return (), versions

        findings = tuple(
            Finding.create(
                category=Category.SYNTAX,
                severity=Severity.SUGGESTION,
                message="Proponowana korekta składniowa.",
                explanation=(
                    "Minimalną zmianę tekstu zatwierdził ograniczony weryfikator."
                ),
                original=edit.original,
                suggestion=edit.suggestion,
                start=sentence.start + edit.start,
                end=sentence.start + edit.end,
                confidence=self._confidence,
                source=self._source,
            )
            for edit in edits
        )
        return findings, versions

    async def _generate(
        self,
        request: PromptRequest,
        call_counter: list[int],
        operation_versions: list[str],
    ) -> str:
        call_counter[0] += 1
        _extend_unique(operation_versions, (_operation_version(request),))
        return await self._backend.generate(request)

    def _failed_run(
        self,
        status: HybridSuggestionStatus,
        suggestions: list[Finding],
        model_calls: int,
        operation_versions: list[str],
    ) -> HybridSuggestionRun:
        return HybridSuggestionRun(
            status=status,
            backend=self.backend_name,
            suggestions=tuple(suggestions),
            model_calls=model_calls,
            operation_versions=tuple(operation_versions),
            safe_error=_SAFE_FAILURE,
        )


def _findings_for_sentence(
    findings: tuple[Finding, ...],
    sentence: Sentence,
) -> tuple[Finding, ...]:
    local: list[Finding] = []
    for finding in findings:
        if finding.start == finding.end:
            belongs = sentence.start <= finding.start < sentence.end
        else:
            belongs = (
                sentence.start <= finding.start
                and finding.end <= sentence.end
                and finding.start < sentence.end
            )
        if not belongs:
            continue
        local.append(
            Finding.create(
                category=finding.category,
                severity=finding.severity,
                message=finding.message,
                explanation=finding.explanation,
                original=finding.original,
                suggestion=finding.suggestion,
                start=finding.start - sentence.start,
                end=finding.end - sentence.start,
                confidence=finding.confidence,
                source=finding.source,
            )
        )
    return tuple(local)


def _operation_version(request: PromptRequest) -> str:
    return f"{request.protocol_id}/{request.protocol_version}"


def _extend_unique(target: list[str], values: tuple[str, ...]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _automatic_protected_spans(text: str) -> tuple[tuple[int, int], ...]:
    return tuple(
        match.span()
        for pattern in (_URL, _NUMBER, _QUOTED)
        for match in pattern.finditer(text)
    )


def _merge_spans(
    spans: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    if not spans:
        return ()
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return tuple(merged)


def _validate_spans(text: str, spans: tuple[tuple[int, int], ...]) -> None:
    previous_end = -1
    for start, end in spans:
        if start < 0 or end <= start or end > len(text):
            raise ValueError("protected span is outside the sentence")
        if start < previous_end:
            raise ValueError("protected spans must not overlap")
        previous_end = end


def _span_overlaps_any(
    start: int,
    end: int,
    spans: tuple[tuple[int, int], ...],
) -> bool:
    return any(
        max(start, item_start) < min(end, item_end) for item_start, item_end in spans
    )


__all__ = [
    "HybridSuggestionEngine",
    "HybridSuggestionRun",
    "HybridSuggestionStatus",
    "InflectionTask",
    "SpecialistBackend",
    "SpecialistTask",
    "SpecialistTaskRouter",
    "SyntaxTask",
]
