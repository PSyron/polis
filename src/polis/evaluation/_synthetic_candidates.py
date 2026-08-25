"""Candidate discovery for the development-only synthetic corpus generator."""

from __future__ import annotations

import re
from dataclasses import dataclass

from polis.evaluation._synthetic_types import (
    CorruptionClass,
    MorphologyAnalysis,
    MorphologyForm,
    MorphologyProvider,
)

_TOKEN = re.compile(r"\w+", re.UNICODE)
_DIACRITICS = {
    "ą": "a",
    "ć": "c",
    "ę": "e",
    "ł": "l",
    "ń": "n",
    "ó": "o",
    "ś": "s",
    "ź": "z",
    "ż": "z",
    "Ą": "A",
    "Ć": "C",
    "Ę": "E",
    "Ł": "L",
    "Ń": "N",
    "Ó": "O",
    "Ś": "S",
    "Ź": "Z",
    "Ż": "Z",
}


@dataclass(frozen=True, slots=True)
class Token:
    """One Unicode word span in the clean source."""

    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Candidate:
    """One reversible mutation described in clean-source coordinates."""

    corruption_class: CorruptionClass
    clean_start: int
    clean_end: int
    clean_form: str
    corrupted_form: str
    source_lemma: str | None = None
    generated_forms: tuple[str, ...] = ()


def collect_candidates(
    text: str, provider: MorphologyProvider
) -> dict[CorruptionClass, tuple[Candidate, ...]]:
    """Find safe, non-fabricated mutations in one source text."""

    tokens = tuple(
        Token(match.group(), match.start(), match.end())
        for match in _TOKEN.finditer(text)
    )
    candidates = {
        CorruptionClass.MORPHOLOGY_CASE: _case_candidates(tokens, provider),
        CorruptionClass.AGREEMENT_NUMBER_OR_GENDER: _agreement_candidates(
            tokens, provider
        ),
        CorruptionClass.REMOVED_COMMA: _comma_candidates(text),
        CorruptionClass.REMOVED_DIACRITIC: _diacritic_candidates(text),
    }
    return {category: tuple(items) for category, items in candidates.items()}


def _case_candidates(
    tokens: tuple[Token, ...], provider: MorphologyProvider
) -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    for token in tokens:
        if token.text != token.text.casefold():
            continue
        analyses = _analyses(provider, token.text)
        for analysis in analyses:
            if not analysis.tag.startswith("subst:"):
                continue
            forms = tuple(
                form
                for form in _forms(provider, analysis.lemma)
                if form.lemma == analysis.lemma
                and form.tag.startswith("subst:")
                and form.form != token.text
                and _has_different_case(analysis.tag, form.tag)
            )
            if not forms:
                continue
            candidates.extend(
                Candidate(
                    CorruptionClass.MORPHOLOGY_CASE,
                    token.start,
                    token.end,
                    token.text,
                    form,
                    analysis.lemma,
                    tuple(
                        sorted({item.form for item in _forms(provider, analysis.lemma)})
                    ),
                )
                for form in sorted({item.form for item in forms})
            )
    return _unique(candidates)


def _agreement_candidates(
    tokens: tuple[Token, ...], provider: MorphologyProvider
) -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    for adjective, noun in zip(tokens, tokens[1:], strict=False):
        if adjective.text != adjective.text.casefold():
            continue
        adjective_analyses = _analyses(provider, adjective.text)
        noun_analyses = tuple(
            item
            for item in _analyses(provider, noun.text)
            if item.tag.startswith("subst:")
        )
        if not noun_analyses:
            continue
        for analysis in adjective_analyses:
            if not analysis.tag.startswith("adj:") or not any(
                _agrees_on_number_and_gender(analysis.tag, noun.tag)
                for noun in noun_analyses
            ):
                continue
            forms = tuple(
                form
                for form in _forms(provider, analysis.lemma)
                if form.lemma == analysis.lemma
                and form.tag.startswith("adj:")
                and form.tag.endswith(":pos")
                and form.form != adjective.text
                and _has_different_number_or_gender(analysis.tag, form.tag)
                and all(
                    not _agrees_on_number_and_gender(form.tag, noun.tag)
                    for noun in noun_analyses
                )
            )
            if not forms:
                continue
            generated_forms = tuple(
                sorted({item.form for item in _forms(provider, analysis.lemma)})
            )
            candidates.extend(
                Candidate(
                    CorruptionClass.AGREEMENT_NUMBER_OR_GENDER,
                    adjective.start,
                    adjective.end,
                    adjective.text,
                    form,
                    analysis.lemma,
                    generated_forms,
                )
                for form in sorted({item.form for item in forms})
            )
    return _unique(candidates)


def _comma_candidates(text: str) -> tuple[Candidate, ...]:
    return tuple(
        Candidate(CorruptionClass.REMOVED_COMMA, index, index + 1, ",", "")
        for index, character in enumerate(text)
        if character == ","
    )


def _diacritic_candidates(text: str) -> tuple[Candidate, ...]:
    return tuple(
        Candidate(
            CorruptionClass.REMOVED_DIACRITIC,
            index,
            index + 1,
            char,
            replacement,
        )
        for index, char in enumerate(text)
        if (replacement := _DIACRITICS.get(char)) is not None
    )


def _analyses(
    provider: MorphologyProvider, text: str
) -> tuple[MorphologyAnalysis, ...]:
    return tuple(
        item
        for item in provider.analyse(text)
        if item.surface == text and item.lemma and item.tag
    )


def _forms(provider: MorphologyProvider, lemma: str) -> tuple[MorphologyForm, ...]:
    return tuple(
        item
        for item in provider.generate(lemma)
        if item.lemma == lemma and item.form and item.tag
    )


def _has_different_case(source_tag: str, target_tag: str) -> bool:
    cases = {"nom", "gen", "dat", "acc", "inst", "loc", "voc"}
    source_cases = _tag_parts(source_tag) & cases
    target_cases = _tag_parts(target_tag) & cases
    return bool(source_cases and target_cases and source_cases.isdisjoint(target_cases))


def _has_different_number_or_gender(source_tag: str, target_tag: str) -> bool:
    source_parts = _tag_parts(source_tag)
    target_parts = _tag_parts(target_tag)
    numbers = {"sg", "pl"}
    genders = {"m1", "m2", "m3", "f", "n"}
    return bool(
        (
            source_parts & numbers
            and target_parts & numbers
            and not source_parts & target_parts & numbers
        )
        or (
            source_parts & genders
            and target_parts & genders
            and not source_parts & target_parts & genders
        )
    )


def _agrees_on_number_and_gender(adjective_tag: str, noun_tag: str) -> bool:
    adjective_parts = _tag_parts(adjective_tag)
    noun_parts = _tag_parts(noun_tag)
    numbers = {"sg", "pl"}
    genders = {"m1", "m2", "m3", "f", "n"}
    return bool(
        adjective_parts & noun_parts & numbers
        and adjective_parts & noun_parts & genders
    )


def _tag_parts(tag: str) -> set[str]:
    return {part for segment in tag.split(":") for part in segment.split(".")}


def _unique(candidates: list[Candidate]) -> tuple[Candidate, ...]:
    seen: set[tuple[CorruptionClass, int, str]] = set()
    result: list[Candidate] = []
    for candidate in candidates:
        key = (
            candidate.corruption_class,
            candidate.clean_start,
            candidate.corrupted_form,
        )
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return tuple(result)
