from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import cast

import pytest
from tests.generative import (
    UNICODE_FAMILIES,
    Replay,
    assert_structural_invariant,
    generate_unicode_text_cases,
)

from polis.core import AnalysisOptions, Category, Confidence, Finding, Source
from polis.core.models import Severity
from polis.rules import (
    DeterministicRuleRegistry,
    DuplicateFindingError,
    DuplicateRuleSourceError,
    IncompatibleRuleOutputError,
    RuleRegistration,
    RuleRegistryError,
)

_CATEGORIES = (
    Category.AGREEMENT,
    Category.INFLECTION,
    Category.SYNTAX,
    Category.SPELLING,
    Category.PUNCTUATION,
    Category.STYLE,
)


@dataclass(frozen=True, slots=True)
class _RuleSpec:
    source: Source
    category: Category
    findings: tuple[Finding, ...]


class _GeneratedRule:
    def __init__(
        self,
        *,
        source: Source,
        findings: tuple[Finding, ...],
        execution_log: list[Source],
    ) -> None:
        self._source = source
        self._findings = findings
        self._execution_log = execution_log

    @property
    def source(self) -> Source:
        return self._source

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        self._execution_log.append(self._source)
        return self._findings


def test_generated_registry_order_and_category_subsets_are_deterministic() -> None:
    _assert_registry_order_properties()


def test_generated_registry_invalid_output_fails_closed_without_text() -> None:
    _assert_generated_fail_closed_properties()


def test_registry_error_capture_failures_are_replay_safe() -> None:
    case = generate_unicode_text_cases(count=2)[1]
    actions = (
        (_no_error_action, "registry.capture.missing"),
        (_text_error_action(case.text), "registry.capture.type"),
    )

    for action, expected_invariant in actions:
        with pytest.raises(AssertionError) as failure:
            _capture_registry_error(
                DuplicateRuleSourceError,
                action,
                invariant="registry.capture",
                replay=case.replay,
            )

        assert_structural_invariant(
            str(failure.value)
            == f"structural invariant failed: {expected_invariant}; {case.replay}",
            invariant="registry.capture.failure_message",
            replay=case.replay,
        )
        assert_structural_invariant(
            case.text not in str(failure.value),
            invariant="registry.capture.privacy",
            replay=case.replay,
        )


def _assert_registry_order_properties() -> None:
    cases = generate_unicode_text_cases()
    assert_structural_invariant(
        frozenset().union(*(case.families for case in cases)) == UNICODE_FAMILIES,
        invariant="registry.order.families",
        replay=cases[-1].replay,
    )

    for case in cases:
        specifications = _specifications_for(case.replay)
        requested = _requested_categories(specifications, case.replay)

        for ordered_specs in _registration_orders(specifications, case.replay):
            expected_rules = tuple(spec.source for spec in ordered_specs)
            expected_selected = tuple(
                spec.source for spec in ordered_specs if spec.category in requested
            )
            expected_findings = tuple(
                finding.id
                for spec in ordered_specs
                if spec.category in requested
                for finding in spec.findings
            )
            expected_finding_sources = tuple(
                finding.source
                for spec in ordered_specs
                if spec.category in requested
                for finding in spec.findings
            )
            assert_structural_invariant(
                len(expected_selected) >= 2,
                invariant="registry.selection.multiple_selected",
                replay=case.replay,
            )
            assert_structural_invariant(
                len(ordered_specs) - len(expected_selected) >= 1,
                invariant="registry.selection.excludes_rule",
                replay=case.replay,
            )
            registry, execution_log = _registry_for(ordered_specs)

            for _ in range(2):
                assert_structural_invariant(
                    tuple(rule.source for rule in registry.rules()) == expected_rules,
                    invariant="registry.order.rules",
                    replay=case.replay,
                )
                assert_structural_invariant(
                    tuple(rule.source for rule in registry.selected_rules(requested))
                    == expected_selected,
                    invariant="registry.selection.relative_order",
                    replay=case.replay,
                )

            first_findings = registry.find(
                case.text,
                options=AnalysisOptions(categories=requested),
            )
            second_findings = registry.find(
                case.text,
                options=AnalysisOptions(categories=requested),
            )
            assert_structural_invariant(
                tuple(finding.id for finding in first_findings) == expected_findings,
                invariant="registry.find.finding_order",
                replay=case.replay,
            )
            assert_structural_invariant(
                tuple(finding.source for finding in first_findings)
                == expected_finding_sources,
                invariant="registry.find.cross_rule_order",
                replay=case.replay,
            )
            assert_structural_invariant(
                tuple(finding.id for finding in second_findings) == expected_findings,
                invariant="registry.find.repeated_order",
                replay=case.replay,
            )
            assert_structural_invariant(
                execution_log == list(expected_selected) * 2,
                invariant="registry.find.execution_order",
                replay=case.replay,
            )


def _assert_generated_fail_closed_properties() -> None:
    for case in generate_unicode_text_cases()[1:]:
        specification = _specifications_for(case.replay)[0]
        duplicate_source = _GeneratedRule(
            source=specification.source,
            findings=specification.findings,
            execution_log=[],
        )
        duplicate_source_error = _capture_registry_error(
            DuplicateRuleSourceError,
            _duplicate_source_action(specification, duplicate_source),
            invariant="registry.fail_closed.duplicate_source",
            replay=case.replay,
        )
        _assert_safe_registry_error(
            duplicate_source_error,
            expected_type=DuplicateRuleSourceError,
            text=case.text,
            invariant="registry.fail_closed.duplicate_source",
            replay=case.replay,
        )

        duplicate_finding_registry = DeterministicRuleRegistry(
            (
                RuleRegistration(
                    rule=_GeneratedRule(
                        source=specification.source,
                        findings=(specification.findings[0], specification.findings[0]),
                        execution_log=[],
                    ),
                    categories=frozenset({specification.category}),
                ),
            )
        )
        duplicate_finding_error = _capture_registry_error(
            DuplicateFindingError,
            _find_action(duplicate_finding_registry, case.text),
            invariant="registry.fail_closed.duplicate_finding",
            replay=case.replay,
        )
        _assert_safe_registry_error(
            duplicate_finding_error,
            expected_type=DuplicateFindingError,
            text=case.text,
            invariant="registry.fail_closed.duplicate_finding",
            replay=case.replay,
        )

        incompatible_source = Source.parse(
            f"rule:property-incompatible-source-{case.replay.case_index}"
        )
        incompatible_source_registry = DeterministicRuleRegistry(
            (
                RuleRegistration(
                    rule=_GeneratedRule(
                        source=specification.source,
                        findings=(
                            _finding(
                                incompatible_source,
                                specification.category,
                                suggestion="source",
                            ),
                        ),
                        execution_log=[],
                    ),
                    categories=frozenset({specification.category}),
                ),
            )
        )
        incompatible_source_error = _capture_registry_error(
            IncompatibleRuleOutputError,
            _find_action(incompatible_source_registry, case.text),
            invariant="registry.fail_closed.incompatible_source",
            replay=case.replay,
        )
        _assert_safe_registry_error(
            incompatible_source_error,
            expected_type=IncompatibleRuleOutputError,
            text=case.text,
            invariant="registry.fail_closed.incompatible_source",
            replay=case.replay,
        )

        incompatible_category = _next_category(specification.category)
        incompatible_category_registry = DeterministicRuleRegistry(
            (
                RuleRegistration(
                    rule=_GeneratedRule(
                        source=specification.source,
                        findings=(
                            _finding(
                                specification.source,
                                incompatible_category,
                                suggestion="category",
                            ),
                        ),
                        execution_log=[],
                    ),
                    categories=frozenset({specification.category}),
                ),
            )
        )
        incompatible_category_error = _capture_registry_error(
            IncompatibleRuleOutputError,
            _find_action(incompatible_category_registry, case.text),
            invariant="registry.fail_closed.incompatible_category",
            replay=case.replay,
        )
        _assert_safe_registry_error(
            incompatible_category_error,
            expected_type=IncompatibleRuleOutputError,
            text=case.text,
            invariant="registry.fail_closed.incompatible_category",
            replay=case.replay,
        )


def _specifications_for(replay: Replay) -> tuple[_RuleSpec, ...]:
    digest = _digest(replay)
    count = 3 + digest[1] % 2
    specifications: list[_RuleSpec] = []
    for index in range(count):
        source = Source.parse(f"rule:property-{replay.case_index}-{index}")
        category = _CATEGORIES[(replay.case_index + index) % len(_CATEGORIES)]
        findings = (
            _finding(source, category, suggestion=f"finding-{index}-first"),
            _finding(source, category, suggestion=f"finding-{index}-second"),
        )
        specifications.append(_RuleSpec(source, category, findings))
    return tuple(specifications)


def _registration_orders(
    specifications: tuple[_RuleSpec, ...], replay: Replay
) -> tuple[tuple[_RuleSpec, ...], ...]:
    original = specifications
    reverse = tuple(reversed(specifications))
    digest = _digest(replay)
    permutation = tuple(
        specifications[index]
        for index in sorted(
            range(len(specifications)),
            key=lambda index: (digest[8 + index], index),
        )
    )
    if permutation == original or permutation == reverse:
        permutation = specifications[1:] + specifications[:1]
    return original, reverse, permutation


def _requested_categories(
    specifications: tuple[_RuleSpec, ...], replay: Replay
) -> frozenset[Category]:
    digest = _digest(replay)
    first_index = digest[0] % len(specifications)
    second_index = (first_index + 1 + digest[2] % (len(specifications) - 1)) % len(
        specifications
    )
    return frozenset(
        {
            specifications[first_index].category,
            specifications[second_index].category,
        }
    )


def _registry_for(
    specifications: tuple[_RuleSpec, ...],
) -> tuple[DeterministicRuleRegistry, list[Source]]:
    execution_log: list[Source] = []
    registrations = tuple(
        RuleRegistration(
            rule=_GeneratedRule(
                source=specification.source,
                findings=specification.findings,
                execution_log=execution_log,
            ),
            categories=frozenset({specification.category}),
        )
        for specification in specifications
    )
    return DeterministicRuleRegistry(registrations), execution_log


def _finding(source: Source, category: Category, *, suggestion: str) -> Finding:
    return Finding.create(
        category=category,
        severity=Severity.ERROR,
        message="synthetic registry finding",
        explanation="synthetic structural test finding",
        original="x",
        suggestion=suggestion,
        start=0,
        end=1,
        confidence=Confidence(0.9),
        source=source,
    )


def _next_category(category: Category) -> Category:
    category_index = _CATEGORIES.index(category)
    return _CATEGORIES[(category_index + 1) % len(_CATEGORIES)]


def _digest(replay: Replay) -> bytes:
    return sha256(
        (
            f"{replay.generator_version}:{replay.seed}:{replay.case_index}:"
            "rule-registry-properties"
        ).encode("ascii")
    ).digest()


def _capture_registry_error(
    expected_type: type[RuleRegistryError],
    action: Callable[[], object],
    *,
    invariant: str,
    replay: Replay,
) -> RuleRegistryError:
    try:
        action()
    except RuleRegistryError as error:
        assert_structural_invariant(
            isinstance(error, expected_type),
            invariant=f"{invariant}.type",
            replay=replay,
        )
        return error
    except Exception:
        assert_structural_invariant(
            False,
            invariant=f"{invariant}.type",
            replay=replay,
        )
        raise AssertionError("unreachable") from None

    assert_structural_invariant(
        False,
        invariant=f"{invariant}.missing",
        replay=replay,
    )
    raise AssertionError("unreachable")


def _no_error_action() -> None:
    return None


def _text_error_action(text: str) -> Callable[[], object]:
    def action() -> object:
        raise ValueError(text)

    return action


def _find_action(
    registry: DeterministicRuleRegistry, text: str
) -> Callable[[], tuple[Finding, ...]]:
    def action() -> tuple[Finding, ...]:
        return cast(
            tuple[Finding, ...],
            registry.find(text, options=AnalysisOptions(categories=None)),
        )

    return action


def _duplicate_source_action(
    specification: _RuleSpec, duplicate_source: _GeneratedRule
) -> Callable[[], DeterministicRuleRegistry]:
    def action() -> DeterministicRuleRegistry:
        return DeterministicRuleRegistry(
            (
                RuleRegistration(
                    rule=_GeneratedRule(
                        source=specification.source,
                        findings=specification.findings,
                        execution_log=[],
                    ),
                    categories=frozenset({specification.category}),
                ),
                RuleRegistration(
                    rule=duplicate_source,
                    categories=frozenset({specification.category}),
                ),
            )
        )

    return action


def _assert_safe_registry_error(
    error: RuleRegistryError,
    *,
    expected_type: type[RuleRegistryError],
    text: str,
    invariant: str,
    replay: Replay,
) -> None:
    assert_structural_invariant(
        isinstance(error, expected_type),
        invariant=f"{invariant}.type",
        replay=replay,
    )
    assert_structural_invariant(
        text not in str(error),
        invariant=f"{invariant}.privacy",
        replay=replay,
    )
