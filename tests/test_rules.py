from __future__ import annotations

from collections.abc import Iterable
from typing import cast

import pytest

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Source,
    VersionedRule,
)
from polis.core.models import Severity
from polis.correction import SourceBehavior
from polis.rules import (
    AgreementCopulaRule,
    ContextMorphologyTransport,
    ContextualInflectionRule,
    ContextualInflectionRuleConfig,
    DeterministicRuleRegistry,
    DuplicateFindingError,
    DuplicateRuleSourceError,
    IncompatibleRuleOutputError,
    RuleRegistration,
    RuleRegistryError,
    SpellingJestesRule,
    SpellingWlasnieRule,
    SpellingZebyRule,
    SyntaxCommaSpacingRule,
    SyntaxListSpacingRule,
    SyntaxMissingCorrelativeRule,
    SyntaxMissingReflexiveRule,
    SyntaxQuoteSpacingRule,
    SyntaxSentenceSpacingRule,
)


class FakeRule:
    def __init__(
        self,
        source: str,
        findings: Iterable[Finding],
    ) -> None:
        self.source = Source.parse(source)
        self._findings = tuple(findings)
        self.calls: list[str] = []

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        self.calls.append(text)
        return self._findings


class FakeVersionedRule(FakeRule):
    operation = "replace.example"
    behavior_version = "example-rule/1.0"


def make_finding(source: str, *, category: Category, start: int, end: int) -> Finding:
    return Finding.create(
        category=category,
        severity=Severity.ERROR,
        message="test",
        explanation="test",
        original="x",
        suggestion="y",
        start=start,
        end=end,
        confidence=Confidence(0.9),
        source=Source.parse(source),
    )


def test_registry_rejects_duplicate_rule_sources() -> None:
    rule = FakeRule("rule:first", ())

    registration = RuleRegistration(rule=rule)

    second = FakeRule("rule:first", ())

    try:
        DeterministicRuleRegistry((registration, RuleRegistration(rule=second)))
    except DuplicateRuleSourceError as exc:
        assert "duplicate rule source" in str(exc)
    else:
        raise AssertionError("expected DuplicateRuleSourceError")


def test_registry_resolves_behavior_only_from_a_registered_versioned_rule() -> None:
    rule = FakeVersionedRule("rule:example", ())
    registry = DeterministicRuleRegistry((RuleRegistration(rule=rule),))

    assert registry.source_behavior(rule.source) == SourceBehavior(
        source=Source.parse("rule:example"),
        operation="replace.example",
        behavior_version="example-rule/1.0",
    )


def test_registry_returns_no_behavior_for_unversioned_or_unknown_sources() -> None:
    rule = FakeRule("rule:third-party", ())
    registry = DeterministicRuleRegistry((RuleRegistration(rule=rule),))

    assert registry.source_behavior(rule.source) is None
    assert registry.source_behavior(Source.parse("rule:unknown")) is None


@pytest.mark.parametrize(
    ("rule", "operation", "behavior_version"),
    (
        (AgreementCopulaRule(), "replace.copula_form", "agreement-copula/1.0"),
        (SpellingJestesRule(), "replace.common_typo", "spelling-jestes/1.0"),
        (SpellingWlasnieRule(), "replace.common_typo", "spelling-wlasnie/1.0"),
        (SpellingZebyRule(), "replace.common_typo", "spelling-zeby/1.0"),
        (
            ContextualInflectionRule(
                ContextualInflectionRuleConfig(),
                cast(ContextMorphologyTransport, object()),
            ),
            "synthesize.contextual_inflection",
            "languagetool-contextual-inflection/1.0",
        ),
        (
            SyntaxCommaSpacingRule(),
            "normalize.comma_spacing",
            "syntax-comma-space/1.0",
        ),
        (
            SyntaxListSpacingRule(),
            "normalize.list_marker_spacing",
            "syntax-list-space/1.0",
        ),
        (
            SyntaxQuoteSpacingRule(),
            "normalize.quote_spacing",
            "syntax-quote-space/1.0",
        ),
        (
            SyntaxSentenceSpacingRule(),
            "normalize.sentence_spacing",
            "syntax-sentence-space/1.0",
        ),
        (
            SyntaxMissingReflexiveRule(),
            "insert.reflexive_pronoun",
            "syntax-missing-reflexive/1.0",
        ),
        (
            SyntaxMissingCorrelativeRule(),
            "insert.correlative",
            "syntax-missing-correlative/1.0",
        ),
    ),
)
def test_builtin_rules_expose_read_only_behavior_metadata(
    rule: VersionedRule, operation: str, behavior_version: str
) -> None:
    assert rule.operation == operation
    assert rule.behavior_version == behavior_version

    with pytest.raises((AttributeError, TypeError)):
        rule.operation = "replace.changed"


def test_registry_selects_rules_by_category() -> None:
    agreement = FakeRule(
        "rule:agreement",
        (make_finding("rule:agreement", category=Category.AGREEMENT, start=0, end=1),),
    )
    spelling = FakeRule(
        "rule:spelling",
        (make_finding("rule:spelling", category=Category.SPELLING, start=0, end=1),),
    )

    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=agreement, categories=frozenset({Category.AGREEMENT})
            ),
            RuleRegistration(rule=spelling, categories=frozenset({Category.SPELLING})),
        )
    )

    selected = registry.find(
        "x",
        options=AnalysisOptions(categories={Category.AGREEMENT}),
    )

    assert len(selected) == 1
    assert selected[0].category == Category.AGREEMENT


def test_registry_executes_rules_in_stable_order() -> None:
    first = FakeRule(
        "rule:first",
        (make_finding("rule:first", category=Category.SPELLING, start=0, end=1),),
    )
    second = FakeRule(
        "rule:second",
        (make_finding("rule:second", category=Category.SPELLING, start=1, end=2),),
    )

    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(rule=second, categories=frozenset({Category.SPELLING})),
            RuleRegistration(rule=first, categories=frozenset({Category.SPELLING})),
        )
    )

    findings = registry.find("xx", options=AnalysisOptions(categories=None))

    assert findings == (
        make_finding("rule:second", category=Category.SPELLING, start=1, end=2),
        make_finding("rule:first", category=Category.SPELLING, start=0, end=1),
    )


def test_registry_rejects_duplicate_finding_ids() -> None:
    finding = make_finding("rule:first", category=Category.SPELLING, start=0, end=1)
    first = FakeRule("rule:first", (finding, finding))

    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=first, categories=frozenset({Category.SPELLING})),)
    )

    try:
        registry.find("x", options=AnalysisOptions(categories=None))
    except DuplicateFindingError:
        pass
    else:
        raise AssertionError("expected DuplicateFindingError")


def test_registry_rejects_incompatible_rule_output_source() -> None:
    mismatched_source = make_finding(
        "rule:other", category=Category.SPELLING, start=0, end=1
    )

    source_mismatch = FakeRule("rule:spelling", (mismatched_source,))

    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=source_mismatch,
                categories=frozenset({Category.SPELLING}),
            ),
        )
    )

    try:
        registry.find("x", options=AnalysisOptions(categories=None))
    except RuleRegistryError as error:
        assert isinstance(error, IncompatibleRuleOutputError)
    else:
        raise AssertionError("expected incompatible rule output error")


def test_registry_rejects_incompatible_rule_output_category() -> None:
    mismatched_category = make_finding(
        "rule:spelling",
        category=Category.AGREEMENT,
        start=1,
        end=2,
    )

    category_mismatch = FakeRule("rule:spelling", (mismatched_category,))

    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=category_mismatch, categories=frozenset({Category.SPELLING})
            ),
        )
    )

    try:
        registry.find("x", options=AnalysisOptions(categories=None))
    except RuleRegistryError as error:
        assert isinstance(error, IncompatibleRuleOutputError)
    else:
        raise AssertionError("expected incompatible rule output error")
