from __future__ import annotations

from polis.core import AnalysisOptions, Category
from polis.rules import DeterministicRuleRegistry, RuleRegistration
from polis.rules.spelling import (
    SpellingJestesRule,
    SpellingWlasnieRule,
    SpellingZebyRule,
)


def test_spelling_rules_emit_expected_fixes_with_offsets() -> None:
    text = "Zeby zeby, wlasnie! Jestes, ale to już jest."

    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(rule=SpellingZebyRule(), categories={Category.SPELLING}),
            RuleRegistration(
                rule=SpellingWlasnieRule(), categories={Category.SPELLING}
            ),
            RuleRegistration(rule=SpellingJestesRule(), categories={Category.SPELLING}),
        )
    )

    findings = registry.find(
        text, options=AnalysisOptions(categories={Category.SPELLING})
    )

    assert len(findings) == 4

    assert findings[0].original == "Zeby"
    assert findings[0].suggestion == "Żeby"
    assert findings[0].start == 0
    assert findings[0].end == 4

    assert findings[1].original == "zeby"
    assert findings[1].suggestion == "żeby"
    assert findings[1].start == 5

    assert findings[2].original == "wlasnie"
    assert findings[2].suggestion == "właśnie"
    assert text[findings[2].start : findings[2].end] == findings[2].original

    assert findings[3].original == "Jestes"
    assert findings[3].suggestion == "Jesteś"
    assert findings[3].start < findings[3].end


def test_spelling_rules_do_not_trigger_on_difficult_negatives() -> None:
    text = "Właśnie, to jest poprawna forma.\nJesteś ważny. Zebyj, wlasniew, niezeby"

    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=SpellingWlasnieRule(), categories={Category.SPELLING}
            ),
            RuleRegistration(rule=SpellingJestesRule(), categories={Category.SPELLING}),
            RuleRegistration(rule=SpellingZebyRule(), categories={Category.SPELLING}),
        )
    )

    findings = registry.find(
        text, options=AnalysisOptions(categories={Category.SPELLING})
    )

    assert len(findings) == 0
