from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, Protocol

from polis.evaluation._synthetic_corpus_sources import (
    SourceFinding,
    SourceText,
    protected_spans,
)
from polis.evaluation._synthetic_corpus_validation import validate_single_edit

type ErrorClass = Literal["case", "agreement", "punctuation", "diacritics"]

_WORD_PATTERN: Final = re.compile(r"(?u)(?<!\w)[^\W\d_]+(?!\w)")
_DIACRITIC_BASE: Final = str.maketrans(
    "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
    "acelnoszzACELNOSZZ",
)
_CASE_FEATURES: Final = frozenset({"nom", "gen", "dat", "acc", "inst", "loc", "voc"})
_PROTECTED_STRATA: Final = frozenset({"quotation-or-literal", "conflict-or-abstention"})
_PROTECTED_FEATURES: Final = frozenset(
    {"conflict", "abstention", "proper_name", "proper-name"}
)
_PUNCTUATION_FAMILIES: Final = ("rule:syntax.", "rule:punctuation.")
_PUNCTUATION_CHARS: Final = frozenset(",.;:!?-—…")


class MorphologyBackend(Protocol):
    def analyse(self, text: str) -> Sequence[tuple[object, ...]]: ...

    def generate(self, lemma: str) -> Sequence[tuple[object, ...]]: ...


@dataclass(frozen=True, slots=True)
class Candidate:
    error_class: ErrorClass
    correct_text: str
    incorrect_text: str
    start: int
    end: int
    original: str
    suggestion: str
    source_dataset: str
    source_case_id: str
    lemma: str | None = None
    generated_tag: str | None = None

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.error_class,
            self.correct_text,
            self.incorrect_text,
            self.start,
            self.end,
            self.original,
            self.suggestion,
        )


def build_candidates(
    sources: Sequence[SourceText], backend: MorphologyBackend
) -> tuple[Candidate, ...]:
    candidates: dict[tuple[object, ...], Candidate] = {}
    for source in sources:
        for candidate in _case_candidates(source, backend):
            candidates.setdefault(candidate.key, candidate)
        for candidate in _agreement_candidates(source, backend):
            candidates.setdefault(candidate.key, candidate)
        for candidate in _punctuation_candidates(source):
            candidates.setdefault(candidate.key, candidate)
        for candidate in _diacritic_candidates(source):
            candidates.setdefault(candidate.key, candidate)
    return tuple(
        sorted(
            candidates.values(),
            key=lambda item: (
                item.error_class,
                item.source_dataset,
                item.source_case_id,
                item.start,
                item.end,
                item.original,
                item.suggestion,
            ),
        )
    )


def build_validated_candidates(sources: Sequence[SourceText]) -> tuple[Candidate, ...]:
    candidates: dict[tuple[object, ...], Candidate] = {}
    for source in sources:
        candidate = _validated_candidate(source)
        if candidate is not None:
            candidates.setdefault(candidate.key, candidate)
    return tuple(
        sorted(
            candidates.values(),
            key=lambda item: (
                item.error_class,
                item.source_dataset,
                item.source_case_id,
                item.start,
                item.end,
                item.original,
                item.suggestion,
            ),
        )
    )


def _validated_candidate(source: SourceText) -> Candidate | None:
    if _validated_rejection_reason(source) is not None:
        return None
    error = source.controlled_error
    if error is None:
        return None
    finding = error.findings[0]
    error_class = _validated_error_class(error.category or error.phenomenon, finding)
    if error_class is None:
        return None
    return Candidate(
        error_class=error_class,
        correct_text=source.text,
        incorrect_text=error.text,
        start=finding.start,
        end=finding.end,
        original=finding.original,
        suggestion=finding.suggestion,
        source_dataset=source.metadata.dataset_id,
        source_case_id=source.case_id,
    )


def _validated_rejection_reason(source: SourceText) -> str | None:
    if source.kind != "correct":
        return "non_correct_source"
    error = source.paired_error
    if error is None:
        return "no_controlled_pair"
    if len(error.findings) != 1:
        return "multiple_findings"
    finding = error.findings[0]
    if (
        source.shape_strata & _PROTECTED_STRATA
        or error.shape_strata & _PROTECTED_STRATA
        or source.features & _PROTECTED_FEATURES
        or error.features & _PROTECTED_FEATURES
        or protected_spans(source.text)
    ):
        return "protected_context"
    if _is_protected(error.text, finding.start, finding.end):
        return "protected_context"
    if source.controlled_error is None:
        if finding.start > len(error.text) or finding.end > len(error.text):
            return "inconsistent_reconstruction"
        if error.text[finding.start : finding.end] != finding.original:
            return "inconsistent_reconstruction"
        reconstructed = (
            error.text[: finding.start] + finding.suggestion + error.text[finding.end :]
        )
        if reconstructed != source.text:
            return "inconsistent_reconstruction"
    if not validate_single_edit(
        error.text,
        source.text,
        start=finding.start,
        end=finding.end,
        original=finding.original,
        suggestion=finding.suggestion,
    ):
        return "inconsistent_reconstruction"
    if _validated_error_class(error.category or error.phenomenon, finding) is None:
        return "unsupported_operator"
    return None


def _validated_error_class(
    category: str | None, finding: SourceFinding
) -> ErrorClass | None:
    if category == "agreement" and _is_single_agreement_change(
        finding.original, finding.suggestion
    ):
        return "agreement"
    if category in {"inflection", "rection"}:
        return "case"
    if category in {"punctuation", "syntax"} and _is_rule_punctuation(finding):
        return "punctuation"
    if category == "spelling" and _is_single_diacritic_change(
        finding.original, finding.suggestion
    ):
        return "diacritics"
    return None


def _is_protected(text: str, start: int, end: int) -> bool:
    for span in protected_spans(text):
        if start == end:
            if span.start <= start < span.end:
                return True
        elif start < span.end and end > span.start:
            return True
    return False


def _is_single_agreement_change(original: str, suggestion: str) -> bool:
    original_words = tuple(match.group() for match in _WORD_PATTERN.finditer(original))
    suggestion_words = tuple(
        match.group() for match in _WORD_PATTERN.finditer(suggestion)
    )
    return (
        len(original_words) == len(suggestion_words)
        and _WORD_PATTERN.sub("\x00", original) == _WORD_PATTERN.sub("\x00", suggestion)
        and sum(
            left != right
            for left, right in zip(original_words, suggestion_words, strict=True)
        )
        == 1
    )


def _is_rule_punctuation(finding: SourceFinding) -> bool:
    if finding.rule_family is None or not finding.rule_family.startswith(
        _PUNCTUATION_FAMILIES
    ):
        return False
    changed = finding.original + finding.suggestion
    return (
        bool(changed)
        and all(
            character.isspace() or character in _PUNCTUATION_CHARS
            for character in changed
        )
        and any(character in _PUNCTUATION_CHARS for character in changed)
    )


def _is_single_diacritic_change(original: str, suggestion: str) -> bool:
    if len(original) != len(suggestion):
        return False
    differences = [
        (left, right)
        for left, right in zip(original, suggestion, strict=True)
        if left != right
    ]
    if len(differences) != 1:
        return False
    left, right = differences[0]
    left_normalized = unicodedata.normalize("NFD", left)
    right_normalized = unicodedata.normalize("NFD", right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized[0].casefold() != right_normalized[0].casefold():
        return False
    left_marks = left_normalized[1:]
    right_marks = right_normalized[1:]
    return left_marks != right_marks and bool(left_marks or right_marks)


def _case_candidates(
    source: SourceText, backend: MorphologyBackend
) -> tuple[Candidate, ...]:
    result: list[Candidate] = []
    for match in _WORD_PATTERN.finditer(source.text):
        surface = match.group()
        source_analyses = _analyses_with_prefix(backend.analyse(surface), "subst")
        for lemma, source_tag in source_analyses:
            for form, tag in _generated_forms(backend.generate(lemma), lemma, "subst:"):
                if form == surface or not _is_case_only_change(source_tag, tag):
                    continue
                result.append(
                    Candidate(
                        error_class="case",
                        correct_text=source.text,
                        incorrect_text=_replace(
                            source.text, match.start(), match.end(), form
                        ),
                        start=match.start(),
                        end=match.start() + len(form),
                        original=form,
                        suggestion=surface,
                        source_dataset=source.metadata.dataset_id,
                        source_case_id=source.case_id,
                        lemma=lemma,
                        generated_tag=tag,
                    )
                )
    return tuple(result)


def _agreement_candidates(
    source: SourceText, backend: MorphologyBackend
) -> tuple[Candidate, ...]:
    words = tuple(_WORD_PATTERN.finditer(source.text))
    result: list[Candidate] = []
    for adjective, noun in zip(words, words[1:], strict=False):
        adjective_analyses = _analyses_with_prefix(
            backend.analyse(adjective.group()), "adj"
        )
        noun_tags = tuple(
            tag
            for _lemma, tag in _analyses_with_prefix(
                backend.analyse(noun.group()), "subst"
            )
        )
        if not adjective_analyses or not noun_tags:
            continue
        for lemma, _source_tag in adjective_analyses:
            for form, tag in _generated_forms(backend.generate(lemma), lemma, "adj"):
                if form == adjective.group() or not _agreement_mismatch(tag, noun_tags):
                    continue
                result.append(
                    Candidate(
                        error_class="agreement",
                        correct_text=source.text,
                        incorrect_text=_replace(
                            source.text, adjective.start(), adjective.end(), form
                        ),
                        start=adjective.start(),
                        end=adjective.start() + len(form),
                        original=form,
                        suggestion=adjective.group(),
                        source_dataset=source.metadata.dataset_id,
                        source_case_id=source.case_id,
                        lemma=lemma,
                        generated_tag=tag,
                    )
                )
    return tuple(result)


def _punctuation_candidates(source: SourceText) -> tuple[Candidate, ...]:
    return tuple(
        Candidate(
            error_class="punctuation",
            correct_text=source.text,
            incorrect_text=_replace(source.text, index, index + 1, ""),
            start=index,
            end=index,
            original="",
            suggestion=",",
            source_dataset=source.metadata.dataset_id,
            source_case_id=source.case_id,
        )
        for index, character in enumerate(source.text)
        if character == ","
    )


def _diacritic_candidates(source: SourceText) -> tuple[Candidate, ...]:
    result: list[Candidate] = []
    for index, character in enumerate(source.text):
        replacement = character.translate(_DIACRITIC_BASE)
        if replacement == character:
            continue
        result.append(
            Candidate(
                error_class="diacritics",
                correct_text=source.text,
                incorrect_text=_replace(source.text, index, index + 1, replacement),
                start=index,
                end=index + 1,
                original=replacement,
                suggestion=character,
                source_dataset=source.metadata.dataset_id,
                source_case_id=source.case_id,
            )
        )
    return tuple(result)


def _is_case_only_change(source_tag: str, generated_tag: str) -> bool:
    source_features = _tag_features(source_tag)
    generated_features = _tag_features(generated_tag)
    source_cases = source_features & _CASE_FEATURES
    generated_cases = generated_features & _CASE_FEATURES
    return (
        bool(source_cases and generated_cases)
        and source_cases.isdisjoint(generated_cases)
        and source_features - _CASE_FEATURES == generated_features - _CASE_FEATURES
    )


def _tag_features(tag: str) -> frozenset[str]:
    return frozenset(part for token in tag.split(":") for part in token.split("."))


def _analyses_with_prefix(
    rows: Sequence[tuple[object, ...]], prefix: str
) -> tuple[tuple[str, str], ...]:
    analyses = {
        (interpretation[1], interpretation[2])
        for interpretation in (_interpretation(row) for row in rows)
        if interpretation is not None and interpretation[2].startswith(f"{prefix}:")
    }
    return tuple(sorted(analyses))


def _generated_forms(
    rows: Sequence[tuple[object, ...]], lemma: str, prefix: str
) -> tuple[tuple[str, str], ...]:
    forms = {
        (row[0], row[2])
        for row in rows
        if len(row) >= 3
        and isinstance(row[0], str)
        and isinstance(row[1], str)
        and isinstance(row[2], str)
        and row[1] == lemma
        and row[0]
        and row[2].startswith(prefix)
    }
    return tuple(sorted(forms))


def _interpretation(row: tuple[object, ...]) -> tuple[str, str, str] | None:
    if len(row) < 3 or not isinstance(row[2], tuple) or len(row[2]) < 3:
        return None
    interpretation = row[2]
    lemma, tag = interpretation[1], interpretation[2]
    if not isinstance(lemma, str) or not isinstance(tag, str):
        return None
    return (str(interpretation[0]), lemma, tag)


def _agreement_mismatch(tag: str, noun_tags: Sequence[str]) -> bool:
    return all(
        _feature(tag, "sg") != _feature(noun_tag, "sg")
        or _feature(tag, "pl") != _feature(noun_tag, "pl")
        or _gender(tag) != _gender(noun_tag)
        for noun_tag in noun_tags
    )


def _feature(tag: str, value: str) -> bool:
    return value in tag.split(":")


def _gender(tag: str) -> frozenset[str]:
    return frozenset(
        part for part in tag.split(":") if part in {"m1", "m2", "m3", "f", "n"}
    )


def _replace(text: str, start: int, end: int, replacement: str) -> str:
    return text[:start] + replacement + text[end:]
