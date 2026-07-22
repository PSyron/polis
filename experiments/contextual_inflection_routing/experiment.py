"""Source-only target detection and finite-form contextual ranking."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

EvidenceKind = Literal[
    "surname_agreement",
    "bez_government",
    "reflexive_dative",
    "gratitude_dative",
]
TargetClass = Literal["ordinary", "first_name", "surname"]

_WORD = re.compile(r"[^\W\d_]+(?:[.'’\-][^\W\d_]+)*", re.UNICODE)
_CASES = frozenset({"nom", "gen", "dat", "acc", "inst", "loc", "voc"})
_NUMBERS = frozenset({"sg", "pl"})
_GENDERS = frozenset({"m1", "m2", "m3", "f", "n1", "n2", "p1", "p2", "p3"})


@dataclass(frozen=True, slots=True)
class RoutingInput:
    source: str


@dataclass(frozen=True, slots=True)
class Token:
    start: int
    end: int
    surface: str


@dataclass(frozen=True, slots=True)
class ContextEvidence:
    kind: EvidenceKind
    spans: tuple[tuple[int, int], ...]
    target_class: TargetClass
    desired_case: str | None


@dataclass(frozen=True, slots=True)
class ContextualProposal:
    start: int
    end: int
    original: str
    suggestion: str
    candidate_id: str
    evidence_kind: EvidenceKind
    target_class: TargetClass


@dataclass(frozen=True, slots=True)
class ContextCandidate:
    candidate_id: str
    start: int
    end: int
    lemma: str | None
    form: str
    features: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContextSpanResult:
    start: int
    end: int
    surface: str
    unsupported_reason: str | None
    candidates: tuple[ContextCandidate, ...]


def validate_context_response(
    raw: str,
    *,
    source_text: str,
    requested_spans: tuple[tuple[int, int], ...],
) -> tuple[ContextSpanResult, ...]:
    """Validate the tag-preserving experimental synthesis response."""

    payload: Any = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != {
        "operation",
        "language",
        "results",
    }:
        raise ValueError("context synthesis response shape is invalid")
    if (
        payload["operation"] != "synthesize_context"
        or payload["language"] != "pl-PL"
        or not isinstance(payload["results"], list)
        or len(payload["results"]) != len(requested_spans)
    ):
        raise ValueError("context synthesis response identity is invalid")
    parsed: list[ContextSpanResult] = []
    for raw_result, span in zip(payload["results"], requested_spans, strict=True):
        if not isinstance(raw_result, dict) or set(raw_result) != {
            "start",
            "end",
            "surface",
            "unsupported_reason",
            "candidates",
        }:
            raise ValueError("context span result shape is invalid")
        start, end = span
        if (raw_result["start"], raw_result["end"]) != span:
            raise ValueError("context span offsets do not match request")
        surface = raw_result["surface"]
        if not isinstance(surface, str) or source_text[start:end] != surface:
            raise ValueError("context span surface does not match source")
        reason = raw_result["unsupported_reason"]
        if reason not in {None, "no-analysis", "unsupported-pos", "no-alternatives"}:
            raise ValueError("context span unsupported reason is invalid")
        raw_candidates = raw_result["candidates"]
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise ValueError("context span candidates are invalid")
        candidates = tuple(
            _parse_context_candidate(item, start=start, end=end)
            for item in raw_candidates
        )
        if surface not in {item.form for item in candidates}:
            raise ValueError("context candidates must preserve source surface")
        parsed.append(ContextSpanResult(start, end, surface, reason, candidates))
    return tuple(parsed)


def _parse_context_candidate(
    raw: object, *, start: int, end: int
) -> ContextCandidate:
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
    if (raw["start"], raw["end"]) != (start, end):
        raise ValueError("context candidate offsets do not match span")
    lemma = raw["lemma"]
    form = raw["form"]
    features = raw["features"]
    tags = raw["tags"]
    if lemma is not None and not isinstance(lemma, str):
        raise ValueError("context candidate lemma is invalid")
    if not isinstance(form, str) or not form:
        raise ValueError("context candidate form is invalid")
    if not _sorted_strings(features) or not _sorted_strings(tags):
        raise ValueError("context candidate features and tags must be sorted")
    feature_tuple = tuple(features)
    tag_tuple = tuple(tags)
    candidate_id = raw["candidate_id"]
    expected_id = stable_context_candidate_id(
        start, end, lemma, form, feature_tuple, tag_tuple
    )
    if candidate_id != expected_id:
        raise ValueError("context candidate ID does not match visible record")
    return ContextCandidate(
        candidate_id, start, end, lemma, form, feature_tuple, tag_tuple
    )


def stable_context_candidate_id(
    start: int,
    end: int,
    lemma: str | None,
    form: str,
    features: tuple[str, ...],
    tags: tuple[str, ...],
) -> str:
    signature = "\0".join(
        (str(start), str(end), lemma or "", form, *features, *tags)
    ).encode("utf-8")
    return "ltpl:" + hashlib.sha256(signature).hexdigest()


def _sorted_strings(raw: object) -> bool:
    return (
        isinstance(raw, list)
        and all(isinstance(item, str) and item for item in raw)
        and raw == sorted(set(raw))
    )


def detect_evidence(routing_input: RoutingInput) -> tuple[ContextEvidence, ...]:
    """Detect only predeclared sentence-local relations from source text."""

    source = routing_input.source
    tokens = tuple(
        Token(match.start(), match.end(), match.group())
        for match in _WORD.finditer(source)
    )
    evidence: set[ContextEvidence] = set()

    for left, right in zip(tokens, tokens[1:], strict=False):
        if (
            left.surface[0].isupper()
            and right.surface[0].isupper()
            and _space_only(source, left.end, right.start)
        ):
            evidence.add(
                ContextEvidence(
                    "surname_agreement",
                    ((left.start, left.end), (right.start, right.end)),
                    "surname",
                    None,
                )
            )

    for index, token in enumerate(tokens):
        lowered = token.surface.casefold()
        if lowered == "bez":
            phrase = _following_phrase(source, tokens, index + 1)
            if phrase:
                evidence.add(
                    ContextEvidence(
                        "bez_government",
                        tuple((item.start, item.end) for item in phrase),
                        "ordinary",
                        "gen",
                    )
                )
        if lowered.startswith("przygląd") and index + 1 < len(tokens):
            reflexive = tokens[index + 1]
            if (
                reflexive.surface.casefold() == "się"
                and _space_only(source, token.end, reflexive.start)
            ):
                phrase = _following_phrase(source, tokens, index + 2)
                if phrase:
                    evidence.add(
                        ContextEvidence(
                            "reflexive_dative",
                            tuple((item.start, item.end) for item in phrase),
                            "ordinary",
                            "dat",
                        )
                    )
        if lowered.startswith("podzięk") and index + 1 < len(tokens):
            target = tokens[index + 1]
            if (
                target.surface[0].isupper()
                and _space_only(source, token.end, target.start)
            ):
                evidence.add(
                    ContextEvidence(
                        "gratitude_dative",
                        ((target.start, target.end),),
                        "first_name",
                        "dat",
                    )
                )

    return tuple(
        sorted(evidence, key=lambda item: (item.spans[0][0], item.kind, item.spans))
    )


def rank_evidence(
    source: str,
    evidence: ContextEvidence,
    results: tuple[ContextSpanResult, ...],
) -> tuple[ContextualProposal, ...]:
    """Select unique finite forms satisfying explicit contextual constraints."""

    if tuple((item.start, item.end) for item in results) != evidence.spans:
        raise ValueError("candidate results do not match evidence spans")
    if any(source[item.start : item.end] != item.surface for item in results):
        raise ValueError("candidate surface does not match source")
    if any(item.unsupported_reason is not None for item in results):
        return ()

    if evidence.kind == "surname_agreement":
        return _rank_surname(source, evidence, results)
    if evidence.kind in {"bez_government", "reflexive_dative"}:
        return _rank_government(source, evidence, results)
    if evidence.kind == "gratitude_dative":
        return _rank_single_noun(source, evidence, results[0])
    raise AssertionError("unhandled evidence kind")


def _rank_surname(
    source: str,
    evidence: ContextEvidence,
    results: tuple[ContextSpanResult, ...],
) -> tuple[ContextualProposal, ...]:
    if len(results) != 2:
        return ()
    reference, target = results
    reference_features = _surface_features(reference, required_pos="subst")
    cases = reference_features & _CASES
    numbers = reference_features & _NUMBERS
    genders = reference_features & _GENDERS
    if not cases or len(numbers) != 1 or not genders:
        return ()
    candidate = _unique_candidate(
        target,
        cases=cases,
        numbers=numbers,
        genders=genders,
        allowed_pos=frozenset({"subst", "adj"}),
        require_positive_for_adjective=True,
    )
    return _proposal(source, evidence, target, candidate)


def _rank_government(
    source: str,
    evidence: ContextEvidence,
    results: tuple[ContextSpanResult, ...],
) -> tuple[ContextualProposal, ...]:
    if not 1 <= len(results) <= 2 or evidence.desired_case is None:
        return ()
    head = results[-1]
    head_features = _surface_features(head, required_pos="subst")
    numbers = head_features & _NUMBERS
    genders = head_features & _GENDERS
    if len(numbers) != 1 or not genders:
        return ()
    proposals: list[ContextualProposal] = []
    for index, result in enumerate(results):
        is_head = index == len(results) - 1
        candidate = _unique_candidate(
            result,
            cases=frozenset({evidence.desired_case}),
            numbers=numbers,
            genders=genders,
            allowed_pos=frozenset({"subst"}) if is_head else frozenset({"adj"}),
            require_positive_for_adjective=not is_head,
        )
        if candidate is None:
            if not _surface_matches(
                result,
                cases=frozenset({evidence.desired_case}),
                numbers=numbers,
                genders=genders,
                allowed_pos=(
                    frozenset({"subst"}) if is_head else frozenset({"adj"})
                ),
                require_positive_for_adjective=not is_head,
            ):
                return ()
            continue
        proposal = _proposal(source, evidence, result, candidate)
        if proposal:
            proposals.extend(proposal)
    return tuple(proposals)


def _rank_single_noun(
    source: str, evidence: ContextEvidence, result: ContextSpanResult
) -> tuple[ContextualProposal, ...]:
    if evidence.desired_case is None:
        return ()
    current = _surface_features(result, required_pos="subst")
    numbers = current & _NUMBERS
    genders = current & _GENDERS
    if len(numbers) != 1 or not genders:
        return ()
    candidate = _unique_candidate(
        result,
        cases=frozenset({evidence.desired_case}),
        numbers=numbers,
        genders=genders,
        allowed_pos=frozenset({"subst"}),
        require_positive_for_adjective=False,
    )
    return _proposal(source, evidence, result, candidate)


def _unique_candidate(
    result: ContextSpanResult,
    *,
    cases: frozenset[str],
    numbers: frozenset[str],
    genders: frozenset[str],
    allowed_pos: frozenset[str],
    require_positive_for_adjective: bool,
) -> ContextCandidate | None:
    current_matches = [
        item
        for item in result.candidates
        if item.form == result.surface
        and _candidate_matches(
            item,
            cases=cases,
            numbers=numbers,
            genders=genders,
            allowed_pos=allowed_pos,
            require_positive_for_adjective=require_positive_for_adjective,
        )
    ]
    if current_matches:
        return None
    matching = [
        item
        for item in result.candidates
        if item.form != result.surface
        and _candidate_matches(
            item,
            cases=cases,
            numbers=numbers,
            genders=genders,
            allowed_pos=allowed_pos,
            require_positive_for_adjective=require_positive_for_adjective,
        )
    ]
    by_form: dict[str, ContextCandidate] = {}
    for item in matching:
        by_form.setdefault(item.form, item)
    return next(iter(by_form.values())) if len(by_form) == 1 else None


def _surface_matches(
    result: ContextSpanResult,
    *,
    cases: frozenset[str],
    numbers: frozenset[str],
    genders: frozenset[str],
    allowed_pos: frozenset[str],
    require_positive_for_adjective: bool,
) -> bool:
    return any(
        item.form == result.surface
        and _candidate_matches(
            item,
            cases=cases,
            numbers=numbers,
            genders=genders,
            allowed_pos=allowed_pos,
            require_positive_for_adjective=require_positive_for_adjective,
        )
        for item in result.candidates
    )


def _candidate_matches(
    candidate: ContextCandidate,
    *,
    cases: frozenset[str],
    numbers: frozenset[str],
    genders: frozenset[str],
    allowed_pos: frozenset[str],
    require_positive_for_adjective: bool,
) -> bool:
    return any(
        _features_match(
            tag_features,
            cases=cases,
            numbers=numbers,
            genders=genders,
            allowed_pos=allowed_pos,
            require_positive_for_adjective=require_positive_for_adjective,
        )
        for tag_features in _tag_feature_sets(candidate)
    )


def _features_match(
    features: frozenset[str],
    *,
    cases: frozenset[str],
    numbers: frozenset[str],
    genders: frozenset[str],
    allowed_pos: frozenset[str],
    require_positive_for_adjective: bool,
) -> bool:
    if not features & cases or not features & numbers or not features & genders:
        return False
    if not features & allowed_pos:
        return False
    return not (
        require_positive_for_adjective
        and "adj" in features
        and "pos" not in features
    )


def _surface_features(
    result: ContextSpanResult, *, required_pos: str
) -> frozenset[str]:
    features: set[str] = set()
    for item in result.candidates:
        expanded = _expanded_features(item)
        if item.form == result.surface and required_pos in expanded:
            features.update(expanded)
    return frozenset(features)


def _expanded_features(candidate: ContextCandidate) -> frozenset[str]:
    return frozenset(
        part
        for feature in candidate.features
        for part in feature.split(".")
        if part
    )


def _tag_feature_sets(
    candidate: ContextCandidate,
) -> tuple[frozenset[str], ...]:
    return tuple(
        frozenset(
            part
            for feature in tag.split(":")
            for part in feature.split(".")
            if part
        )
        for tag in candidate.tags
    )


def _proposal(
    source: str,
    evidence: ContextEvidence,
    result: ContextSpanResult,
    candidate: ContextCandidate | None,
) -> tuple[ContextualProposal, ...]:
    if candidate is None or candidate.form == result.surface:
        return ()
    return (
        ContextualProposal(
            result.start,
            result.end,
            source[result.start : result.end],
            candidate.form,
            candidate.candidate_id,
            evidence.kind,
            evidence.target_class,
        ),
    )


def _following_phrase(
    source: str, tokens: tuple[Token, ...], start_index: int
) -> tuple[Token, ...]:
    if start_index >= len(tokens):
        return ()
    selected = [tokens[start_index]]
    if start_index + 1 < len(tokens) and _space_only(
        source, tokens[start_index].end, tokens[start_index + 1].start
    ):
        selected.append(tokens[start_index + 1])
    return tuple(selected)


def _space_only(source: str, start: int, end: int) -> bool:
    return start < end and source[start:end].isspace()


__all__ = [
    "ContextEvidence",
    "ContextCandidate",
    "ContextSpanResult",
    "ContextualProposal",
    "RoutingInput",
    "detect_evidence",
    "rank_evidence",
    "stable_context_candidate_id",
    "validate_context_response",
]
