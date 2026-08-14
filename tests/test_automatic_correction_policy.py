"""Regression tests for the exact automatic-correction policy key."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from polis.core import Category, Confidence, Finding, Severity, Source, SourceKind
from polis.correction.policy import (
    SOURCE_POLICY_VERSION,
    SourceBehavior,
    SourcePolicyKey,
    is_automatic_correction_eligible,
)

_AUTOMATIC_BEHAVIORS = (
    (
        Source(SourceKind.RULE, "agreement.copula"),
        Category.AGREEMENT,
        "replace.copula_form",
        "agreement-copula/1.0",
        0.9,
    ),
    (
        Source(SourceKind.RULE, "spelling.jestes"),
        Category.SPELLING,
        "replace.common_typo",
        "spelling-jestes/1.0",
        0.9,
    ),
    (
        Source(SourceKind.RULE, "spelling.wlasnie"),
        Category.SPELLING,
        "replace.common_typo",
        "spelling-wlasnie/1.0",
        0.9,
    ),
    (
        Source(SourceKind.RULE, "spelling.zeby"),
        Category.SPELLING,
        "replace.common_typo",
        "spelling-zeby/1.0",
        0.9,
    ),
    (
        Source(SourceKind.RULE, "syntax.comma_space"),
        Category.PUNCTUATION,
        "normalize.comma_spacing",
        "syntax-comma-space/1.0",
        0.9,
    ),
    (
        Source(SourceKind.RULE, "syntax.list_space"),
        Category.SYNTAX,
        "normalize.list_marker_spacing",
        "syntax-list-space/1.0",
        0.9,
    ),
    (
        Source(SourceKind.RULE, "syntax.quote_space"),
        Category.PUNCTUATION,
        "normalize.quote_spacing",
        "syntax-quote-space/1.0",
        0.9,
    ),
    (
        Source(SourceKind.RULE, "syntax.sentence_space"),
        Category.PUNCTUATION,
        "normalize.sentence_spacing",
        "syntax-sentence-space/1.0",
        0.9,
    ),
)


def _finding(
    source: Source,
    category: Category,
    confidence: float,
) -> Finding:
    return Finding.create(
        category=category,
        severity=Severity.SUGGESTION,
        message="Known correction.",
        explanation="Policy test finding.",
        original="x",
        suggestion="y",
        start=0,
        end=1,
        confidence=Confidence(confidence),
        source=source,
    )


def test_policy_identity_values_are_equal_immutable_and_slotted() -> None:
    source = Source(SourceKind.RULE, "spelling.zeby")
    behavior = SourceBehavior(
        source=source,
        operation="replace.common_typo",
        behavior_version="spelling-zeby/1.0",
    )
    key = SourcePolicyKey(
        source=source,
        category=Category.SPELLING,
        operation="replace.common_typo",
        behavior_version="spelling-zeby/1.0",
        source_policy_version="1.2",
    )

    assert behavior == SourceBehavior(
        source=source,
        operation="replace.common_typo",
        behavior_version="spelling-zeby/1.0",
    )
    assert key == SourcePolicyKey(
        source=source,
        category=Category.SPELLING,
        operation="replace.common_typo",
        behavior_version="spelling-zeby/1.0",
        source_policy_version="1.2",
    )
    assert not hasattr(behavior, "__dict__")
    assert not hasattr(key, "__dict__")
    with pytest.raises(FrozenInstanceError):
        behavior.operation = "replace.other_typo"
    with pytest.raises(FrozenInstanceError):
        key.operation = "replace.other_typo"


@pytest.mark.parametrize(
    ("source", "category", "operation", "behavior_version", "minimum_confidence"),
    _AUTOMATIC_BEHAVIORS,
)
def test_each_exact_known_key_is_eligible_at_its_minimum_confidence(
    source: Source,
    category: Category,
    operation: str,
    behavior_version: str,
    minimum_confidence: float,
) -> None:
    behavior = SourceBehavior(source, operation, behavior_version)

    assert SOURCE_POLICY_VERSION == "1.2"
    assert is_automatic_correction_eligible(
        _finding(source, category, minimum_confidence), behavior
    )


@pytest.mark.parametrize(
    ("finding", "behavior", "source_policy_version"),
    (
        (
            _finding(
                Source(SourceKind.RULE, "spelling.unknown"),
                Category.SPELLING,
                0.9,
            ),
            SourceBehavior(
                Source(SourceKind.RULE, "spelling.unknown"),
                "replace.common_typo",
                "spelling-zeby/1.0",
            ),
            SOURCE_POLICY_VERSION,
        ),
        (
            _finding(Source(SourceKind.RULE, "spelling.zeby"), Category.SYNTAX, 0.9),
            SourceBehavior(
                Source(SourceKind.RULE, "spelling.zeby"),
                "replace.common_typo",
                "spelling-zeby/1.0",
            ),
            SOURCE_POLICY_VERSION,
        ),
        (
            _finding(Source(SourceKind.RULE, "spelling.zeby"), Category.SPELLING, 0.9),
            SourceBehavior(
                Source(SourceKind.RULE, "spelling.zeby"),
                "replace.different_typo",
                "spelling-zeby/1.0",
            ),
            SOURCE_POLICY_VERSION,
        ),
        (
            _finding(Source(SourceKind.RULE, "spelling.zeby"), Category.SPELLING, 0.9),
            SourceBehavior(
                Source(SourceKind.RULE, "spelling.zeby"),
                "replace.common_typo",
                "spelling-zeby/2.0",
            ),
            SOURCE_POLICY_VERSION,
        ),
        (
            _finding(Source(SourceKind.RULE, "spelling.zeby"), Category.SPELLING, 0.9),
            SourceBehavior(
                Source(SourceKind.RULE, "spelling.zeby"),
                "replace.common_typo",
                "spelling-zeby/1.0",
            ),
            "1.3",
        ),
    ),
)
def test_each_changed_policy_key_dimension_is_ineligible(
    finding: Finding,
    behavior: SourceBehavior,
    source_policy_version: str,
) -> None:
    assert not is_automatic_correction_eligible(
        finding,
        behavior,
        source_policy_version=source_policy_version,
    )


def test_below_threshold_unknown_or_missing_behavior_is_ineligible() -> None:
    source = Source(SourceKind.RULE, "spelling.zeby")
    behavior = SourceBehavior(
        source,
        "replace.common_typo",
        "spelling-zeby/1.0",
    )

    assert not is_automatic_correction_eligible(
        _finding(source, Category.SPELLING, 0.89), behavior
    )
    assert not is_automatic_correction_eligible(
        _finding(source, Category.SPELLING, 0.9), None
    )


def test_llm_finding_is_ineligible_at_full_confidence() -> None:
    source = Source(SourceKind.LLM, "spelling.zeby")
    behavior = SourceBehavior(
        source,
        "replace.common_typo",
        "spelling-zeby/1.0",
    )

    assert not is_automatic_correction_eligible(
        _finding(source, Category.SPELLING, 1.0), behavior
    )


def test_nominal_group_ta_nowy_ksiazka_full_policy_key_remains_review_only() -> None:
    source = Source(SourceKind.RULE, "agreement.nominal_group_ta_nowy_ksiazka")
    behavior = SourceBehavior(
        source,
        "replace.adjective_gender",
        (
            "agreement-nominal-group-ta-nowy-ksiazka/1.0+"
            "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
            "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
        ),
    )

    assert SOURCE_POLICY_VERSION == "1.2"
    assert not is_automatic_correction_eligible(
        _finding(source, Category.AGREEMENT, 0.9),
        behavior,
        source_policy_version=SOURCE_POLICY_VERSION,
    )


def test_government_szukac_klucz_full_policy_key_remains_review_only() -> None:
    source = Source(SourceKind.RULE, "inflection.government_szukac_klucz")
    behavior = SourceBehavior(
        source,
        "replace.governed_form",
        (
            "inflection-government-szukac-klucz/1.0+"
            "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
            "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
        ),
    )

    assert SOURCE_POLICY_VERSION == "1.2"
    assert not is_automatic_correction_eligible(
        _finding(source, Category.INFLECTION, 0.9),
        behavior,
        source_policy_version=SOURCE_POLICY_VERSION,
    )


def test_przygladac_sie_nowy_budynek_full_policy_key_remains_review_only() -> None:
    source = Source(SourceKind.RULE, "inflection.przygladac_sie_nowy_budynek")
    behavior = SourceBehavior(
        source,
        "replace.governed_nominal_group",
        (
            "inflection-przygladac-sie-nowy-budynek/1.0+"
            "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
            "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
        ),
    )

    assert SOURCE_POLICY_VERSION == "1.2"
    assert not is_automatic_correction_eligible(
        _finding(source, Category.INFLECTION, 0.9),
        behavior,
        source_policy_version=SOURCE_POLICY_VERSION,
    )


def test_subject_verb_my_czyta_full_policy_key_remains_review_only() -> None:
    source = Source(SourceKind.RULE, "agreement.subject_verb_my_czyta")
    behavior = SourceBehavior(
        source,
        "replace.subject_verb_number",
        (
            "agreement-subject-verb-my-czyta/1.0+"
            "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
            "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
        ),
    )

    assert SOURCE_POLICY_VERSION == "1.2"
    assert not is_automatic_correction_eligible(
        _finding(source, Category.AGREEMENT, 0.9),
        behavior,
        source_policy_version=SOURCE_POLICY_VERSION,
    )


def test_initial_temporal_comma_full_policy_key_remains_review_only() -> None:
    source = Source(SourceKind.RULE, "syntax.initial_temporal_comma")
    behavior = SourceBehavior(
        source,
        "insert.temporal_clause_comma",
        "syntax-initial-temporal-comma/1.0",
    )

    assert SOURCE_POLICY_VERSION == "1.2"
    assert not is_automatic_correction_eligible(
        _finding(source, Category.SYNTAX, 0.9),
        behavior,
        source_policy_version=SOURCE_POLICY_VERSION,
    )


def test_wogole_full_policy_key_remains_review_only() -> None:
    source = Source(SourceKind.RULE, "spelling.wogole")
    behavior = SourceBehavior(
        source,
        "replace.common_typo",
        "spelling-wogole/1.0",
    )

    assert SOURCE_POLICY_VERSION == "1.2"
    assert not is_automatic_correction_eligible(
        _finding(source, Category.SPELLING, 0.98),
        behavior,
        source_policy_version=SOURCE_POLICY_VERSION,
    )


def test_narazie_full_policy_key_remains_review_only() -> None:
    source = Source(SourceKind.RULE, "spelling.narazie")
    behavior = SourceBehavior(
        source,
        "replace.common_typo",
        "spelling-narazie/1.0",
    )

    assert SOURCE_POLICY_VERSION == "1.2"
    assert not is_automatic_correction_eligible(
        _finding(source, Category.SPELLING, 0.98),
        behavior,
        source_policy_version=SOURCE_POLICY_VERSION,
    )


def test_wziasc_full_policy_key_remains_review_only() -> None:
    source = Source(SourceKind.RULE, "spelling.wziasc")
    behavior = SourceBehavior(
        source,
        "replace.common_typo",
        "spelling-wziasc/1.0",
    )

    assert SOURCE_POLICY_VERSION == "1.2"
    assert not is_automatic_correction_eligible(
        _finding(source, Category.SPELLING, 0.98),
        behavior,
        source_policy_version=SOURCE_POLICY_VERSION,
    )


def test_language_tool_behavior_is_no_longer_eligible() -> None:
    source = Source(SourceKind.RULE, "languagetool.pl")
    behavior = SourceBehavior(
        source,
        "check.allowlisted_comma",
        "pl-6.8-five-rule-comma/1.0",
    )

    assert not is_automatic_correction_eligible(
        _finding(source, Category.PUNCTUATION, 1.0), behavior
    )


@pytest.mark.parametrize("value", ("", " ", "\t"))
def test_policy_identity_rejects_blank_operation_and_versions(value: str) -> None:
    source = Source(SourceKind.RULE, "spelling.zeby")

    with pytest.raises(ValueError):
        SourceBehavior(source, value, "spelling-zeby/1.0")
    with pytest.raises(ValueError):
        SourceBehavior(source, "replace.common_typo", value)
    with pytest.raises(ValueError):
        SourcePolicyKey(
            source,
            Category.SPELLING,
            "replace.common_typo",
            "spelling-zeby/1.0",
            value,
        )
