"""Reviewable sentence-local inflection suggestions from finite local forms."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)
from polis.correction import findings_conflict
from polis.segmentation import segment_sentences

EvidenceKind = Literal[
    "surname_agreement",
    "bez_government",
    "reflexive_dative",
    "gratitude_dative",
]

_SOURCE = Source(SourceKind.RULE, "languagetool.contextual_inflection")
_WORD = re.compile(r"[^\W\d_]+(?:[.'’\-][^\W\d_]+)*", re.UNICODE)
_CASES = frozenset({"nom", "gen", "dat", "acc", "inst", "loc", "voc"})
_NUMBERS = frozenset({"sg", "pl"})
_GENDERS = frozenset({"m1", "m2", "m3", "f", "n1", "n2", "p1", "p2", "p3"})


class ContextMorphologyTransport(Protocol):
    """Injected local transport for the tag-preserving synthesis contract."""

    def synthesize_context(
        self,
        text: str,
        *,
        spans: tuple[tuple[int, int], ...],
        timeout_seconds: float,
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class StdioContextMorphologyTransport:
    """Run one explicit local stdio bridge invocation without a shell."""

    executable: Path

    def __post_init__(self) -> None:
        if not self.executable.is_absolute():
            raise ValueError("contextual inflection executable must be absolute")
        if not self.executable.is_file() or not os.access(self.executable, os.X_OK):
            raise ValueError("contextual inflection executable must be executable")

    def synthesize_context(
        self,
        text: str,
        *,
        spans: tuple[tuple[int, int], ...],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        request = json.dumps(
            {
                "operation": "synthesize_context",
                "language": "pl-PL",
                "text": text,
                "spans": [{"start": start, "end": end} for start, end in spans],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            completed = subprocess.run(
                (os.fspath(self.executable),),
                input=request,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout_seconds,
                check=True,
                cwd=self.executable.parent,
            )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError("context synthesis timed out") from error
        except subprocess.CalledProcessError as error:
            raise OSError("context synthesis process failed") from error
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict):
            raise ValueError("context synthesis response must be an object")
        return cast(Mapping[str, object], payload)


@dataclass(frozen=True, slots=True)
class ContextualInflectionRuleConfig:
    timeout_seconds: float = 1.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds <= 0
        ):
            raise ValueError("contextual inflection timeout must be positive")


@dataclass(frozen=True, slots=True)
class _Token:
    start: int
    end: int
    surface: str


@dataclass(frozen=True, slots=True)
class _Evidence:
    kind: EvidenceKind
    spans: tuple[tuple[int, int], ...]
    desired_case: str | None


@dataclass(frozen=True, slots=True)
class _Candidate:
    candidate_id: str
    start: int
    end: int
    lemma: str | None
    form: str
    features: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _SpanResult:
    start: int
    end: int
    surface: str
    unsupported_reason: str | None
    candidates: tuple[_Candidate, ...]


@dataclass(frozen=True, slots=True)
class _Proposal:
    start: int
    end: int
    original: str
    suggestion: str
    candidate_id: str
    evidence_kind: EvidenceKind


@dataclass(frozen=True, slots=True)
class ContextualInflectionRule:
    """Suggest only uniquely constrained forms from source-local evidence."""

    config: ContextualInflectionRuleConfig
    transport: ContextMorphologyTransport
    source: Source = _SOURCE

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if (
            options.categories is not None
            and Category.INFLECTION not in options.categories
        ):
            return ()
        if len(segment_sentences(text)) != 1:
            return ()
        evidence = _detect_evidence(text)
        if not evidence:
            return ()
        spans = tuple(sorted({span for item in evidence for span in item.spans}))
        try:
            payload = self.transport.synthesize_context(
                text,
                spans=spans,
                timeout_seconds=self.config.timeout_seconds,
            )
            results = _validate_response(payload, source=text, spans=spans)
            by_span = {(item.start, item.end): item for item in results}
            proposals = _normalize_proposals(
                tuple(
                    proposal
                    for item in evidence
                    for proposal in _rank(
                        text,
                        item,
                        tuple(by_span[span] for span in item.spans),
                    )
                )
            )
        except (OSError, TimeoutError, TypeError, ValueError):
            return ()
        findings = tuple(
            Finding.create(
                category=Category.INFLECTION,
                severity=Severity.SUGGESTION,
                message="Forma fleksyjna nie zgadza się z kontekstem zdania.",
                explanation=(
                    f"Kandydat {item.candidate_id} spełnia relację "
                    f"{item.evidence_kind}; zmiana wymaga zatwierdzenia."
                ),
                original=item.original,
                suggestion=item.suggestion,
                start=item.start,
                end=item.end,
                confidence=Confidence(0.95),
                source=self.source,
            )
            for item in proposals
        )
        return tuple(
            finding
            for index, finding in enumerate(findings)
            if not any(
                findings_conflict(finding, other)
                for other_index, other in enumerate(findings)
                if index != other_index
            )
        )


def stable_context_candidate_id(
    start: int,
    end: int,
    lemma: str | None,
    form: str,
    features: tuple[str, ...],
    tags: tuple[str, ...],
) -> str:
    """Derive the candidate ID from every visible contextual record field."""

    signature = "\0".join(
        (str(start), str(end), lemma or "", form, *features, *tags)
    ).encode("utf-8")
    return "ltpl:" + hashlib.sha256(signature).hexdigest()


def _detect_evidence(source: str) -> tuple[_Evidence, ...]:
    tokens = tuple(
        _Token(match.start(), match.end(), match.group())
        for match in _WORD.finditer(source)
    )
    evidence: set[_Evidence] = set()
    for left, right in zip(tokens, tokens[1:], strict=False):
        if (
            left.surface[0].isupper()
            and right.surface[0].isupper()
            and _space_only(source, left.end, right.start)
        ):
            evidence.add(
                _Evidence(
                    "surname_agreement",
                    ((left.start, left.end), (right.start, right.end)),
                    None,
                )
            )
    for index, token in enumerate(tokens):
        lowered = token.surface.casefold()
        if lowered == "bez":
            phrase = _following_phrase(source, tokens, index + 1)
            if phrase:
                evidence.add(
                    _Evidence(
                        "bez_government",
                        tuple((item.start, item.end) for item in phrase),
                        "gen",
                    )
                )
        if lowered.startswith("przygląd") and index + 1 < len(tokens):
            reflexive = tokens[index + 1]
            if reflexive.surface.casefold() == "się" and _space_only(
                source, token.end, reflexive.start
            ):
                phrase = _following_phrase(source, tokens, index + 2)
                if phrase:
                    evidence.add(
                        _Evidence(
                            "reflexive_dative",
                            tuple((item.start, item.end) for item in phrase),
                            "dat",
                        )
                    )
        if lowered.startswith("podzięk") and index + 1 < len(tokens):
            target = tokens[index + 1]
            if target.surface[0].isupper() and _space_only(
                source, token.end, target.start
            ):
                evidence.add(
                    _Evidence(
                        "gratitude_dative",
                        ((target.start, target.end),),
                        "dat",
                    )
                )
    return tuple(
        sorted(evidence, key=lambda item: (item.spans[0][0], item.kind, item.spans))
    )


def _validate_response(
    payload: Mapping[str, object],
    *,
    source: str,
    spans: tuple[tuple[int, int], ...],
) -> tuple[_SpanResult, ...]:
    if set(payload) != {"operation", "language", "results"}:
        raise ValueError("context synthesis response shape is invalid")
    raw_results = payload["results"]
    if (
        payload["operation"] != "synthesize_context"
        or payload["language"] != "pl-PL"
        or not isinstance(raw_results, list)
        or len(raw_results) != len(spans)
    ):
        raise ValueError("context synthesis response identity is invalid")
    results: list[_SpanResult] = []
    for raw_result, span in zip(raw_results, spans, strict=True):
        if not isinstance(raw_result, dict) or set(raw_result) != {
            "start",
            "end",
            "surface",
            "unsupported_reason",
            "candidates",
        }:
            raise ValueError("context span result shape is invalid")
        start, end = span
        surface = raw_result["surface"]
        if (
            (raw_result["start"], raw_result["end"]) != span
            or not isinstance(surface, str)
            or source[start:end] != surface
        ):
            raise ValueError("context span does not match source")
        reason = raw_result["unsupported_reason"]
        if reason not in {None, "no-analysis", "unsupported-pos", "no-alternatives"}:
            raise ValueError("context unsupported reason is invalid")
        raw_candidates = raw_result["candidates"]
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise ValueError("context candidates are invalid")
        candidates = tuple(
            _parse_candidate(item, start=start, end=end) for item in raw_candidates
        )
        if surface not in {item.form for item in candidates}:
            raise ValueError("context candidates must preserve source")
        results.append(
            _SpanResult(start, end, surface, cast(str | None, reason), candidates)
        )
    return tuple(results)


def _parse_candidate(raw: object, *, start: int, end: int) -> _Candidate:
    if not isinstance(raw, dict) or set(raw) != {
        "candidate_id",
        "start",
        "end",
        "lemma",
        "form",
        "features",
        "tags",
    }:
        raise ValueError("context candidate shape is invalid")
    lemma = raw["lemma"]
    form = raw["form"]
    features = raw["features"]
    tags = raw["tags"]
    if (
        (raw["start"], raw["end"]) != (start, end)
        or (lemma is not None and not isinstance(lemma, str))
        or not isinstance(form, str)
        or not form
        or not _sorted_strings(features)
        or not _sorted_strings(tags)
    ):
        raise ValueError("context candidate record is invalid")
    feature_tuple = tuple(cast(list[str], features))
    tag_tuple = tuple(cast(list[str], tags))
    expected = stable_context_candidate_id(
        start, end, lemma, form, feature_tuple, tag_tuple
    )
    if raw["candidate_id"] != expected:
        raise ValueError("context candidate ID is invalid")
    return _Candidate(
        expected,
        start,
        end,
        lemma,
        form,
        feature_tuple,
        tag_tuple,
    )


def _rank(
    source: str, evidence: _Evidence, results: tuple[_SpanResult, ...]
) -> tuple[_Proposal, ...]:
    if any(item.unsupported_reason is not None for item in results):
        return ()
    if evidence.kind == "surname_agreement":
        return _rank_surname(source, evidence, results)
    if evidence.kind in {"bez_government", "reflexive_dative"}:
        return _rank_government(source, evidence, results)
    if evidence.kind == "gratitude_dative" and evidence.desired_case is not None:
        return _rank_single(source, evidence, results[0], evidence.desired_case)
    return ()


def _rank_surname(
    source: str, evidence: _Evidence, results: tuple[_SpanResult, ...]
) -> tuple[_Proposal, ...]:
    if len(results) != 2:
        return ()
    reference, target = results
    reference_features = _surface_features(reference, "subst")
    cases = reference_features & _CASES
    numbers = reference_features & _NUMBERS
    genders = reference_features & _GENDERS
    if not cases or len(numbers) != 1 or not genders:
        return ()
    candidate = _unique_candidate(
        target, cases, numbers, genders, frozenset({"subst", "adj"}), True
    )
    return _proposal(source, evidence, target, candidate)


def _rank_government(
    source: str, evidence: _Evidence, results: tuple[_SpanResult, ...]
) -> tuple[_Proposal, ...]:
    if not 1 <= len(results) <= 2 or evidence.desired_case is None:
        return ()
    head_features = _surface_features(results[-1], "subst")
    numbers = head_features & _NUMBERS
    genders = head_features & _GENDERS
    if len(numbers) != 1 or not genders:
        return ()
    proposals: list[_Proposal] = []
    cases = frozenset({evidence.desired_case})
    for index, result in enumerate(results):
        head = index == len(results) - 1
        positions = frozenset({"subst"}) if head else frozenset({"adj"})
        candidate = _unique_candidate(
            result, cases, numbers, genders, positions, not head
        )
        if candidate is None:
            if not _surface_matches(
                result, cases, numbers, genders, positions, not head
            ):
                return ()
            continue
        proposals.extend(_proposal(source, evidence, result, candidate))
    return tuple(proposals)


def _rank_single(
    source: str, evidence: _Evidence, result: _SpanResult, desired_case: str
) -> tuple[_Proposal, ...]:
    current = _surface_features(result, "subst")
    numbers = current & _NUMBERS
    genders = current & _GENDERS
    if len(numbers) != 1 or not genders:
        return ()
    candidate = _unique_candidate(
        result,
        frozenset({desired_case}),
        numbers,
        genders,
        frozenset({"subst"}),
        False,
    )
    return _proposal(source, evidence, result, candidate)


def _unique_candidate(
    result: _SpanResult,
    cases: frozenset[str],
    numbers: frozenset[str],
    genders: frozenset[str],
    positions: frozenset[str],
    positive_adjective: bool,
) -> _Candidate | None:
    if _surface_matches(result, cases, numbers, genders, positions, positive_adjective):
        return None
    matching = [
        item
        for item in result.candidates
        if item.form != result.surface
        and _candidate_matches(
            item, cases, numbers, genders, positions, positive_adjective
        )
    ]
    by_form: dict[str, _Candidate] = {}
    for item in matching:
        by_form.setdefault(item.form, item)
    return next(iter(by_form.values())) if len(by_form) == 1 else None


def _surface_matches(
    result: _SpanResult,
    cases: frozenset[str],
    numbers: frozenset[str],
    genders: frozenset[str],
    positions: frozenset[str],
    positive_adjective: bool,
) -> bool:
    return any(
        item.form == result.surface
        and _candidate_matches(
            item, cases, numbers, genders, positions, positive_adjective
        )
        for item in result.candidates
    )


def _candidate_matches(
    candidate: _Candidate,
    cases: frozenset[str],
    numbers: frozenset[str],
    genders: frozenset[str],
    positions: frozenset[str],
    positive_adjective: bool,
) -> bool:
    return any(
        bool(features & cases)
        and bool(features & numbers)
        and bool(features & genders)
        and bool(features & positions)
        and not (positive_adjective and "adj" in features and "pos" not in features)
        for features in _tag_features(candidate)
    )


def _surface_features(result: _SpanResult, position: str) -> frozenset[str]:
    return frozenset(
        feature
        for item in result.candidates
        if item.form == result.surface
        for features in _tag_features(item)
        if position in features
        for feature in features
    )


def _tag_features(candidate: _Candidate) -> tuple[frozenset[str], ...]:
    return tuple(
        frozenset(
            part for feature in tag.split(":") for part in feature.split(".") if part
        )
        for tag in candidate.tags
    )


def _proposal(
    source: str,
    evidence: _Evidence,
    result: _SpanResult,
    candidate: _Candidate | None,
) -> tuple[_Proposal, ...]:
    if candidate is None or candidate.form == result.surface:
        return ()
    return (
        _Proposal(
            result.start,
            result.end,
            source[result.start : result.end],
            candidate.form,
            candidate.candidate_id,
            evidence.kind,
        ),
    )


def _normalize_proposals(proposals: tuple[_Proposal, ...]) -> tuple[_Proposal, ...]:
    unique = tuple(
        sorted(
            set(proposals),
            key=lambda item: (item.start, item.end, item.suggestion, item.candidate_id),
        )
    )
    conflicts: set[int] = set()
    for index, left in enumerate(unique):
        for other_index, right in enumerate(unique[index + 1 :], start=index + 1):
            if left.start < right.end and right.start < left.end:
                conflicts.update((index, other_index))
    return tuple(item for index, item in enumerate(unique) if index not in conflicts)


def _following_phrase(
    source: str, tokens: tuple[_Token, ...], start: int
) -> tuple[_Token, ...]:
    if start >= len(tokens):
        return ()
    selected = [tokens[start]]
    if start + 1 < len(tokens) and _space_only(
        source, tokens[start].end, tokens[start + 1].start
    ):
        selected.append(tokens[start + 1])
    return tuple(selected)


def _space_only(source: str, start: int, end: int) -> bool:
    return start < end and source[start:end].isspace()


def _sorted_strings(raw: object) -> bool:
    return (
        isinstance(raw, list)
        and all(isinstance(item, str) and item for item in raw)
        and raw == sorted(set(raw))
    )


__all__ = [
    "ContextMorphologyTransport",
    "ContextualInflectionRule",
    "ContextualInflectionRuleConfig",
    "StdioContextMorphologyTransport",
    "stable_context_candidate_id",
]
