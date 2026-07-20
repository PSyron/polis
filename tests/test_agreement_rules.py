from __future__ import annotations

from polis.core import AnalysisOptions, Category
from polis.rules import DeterministicRuleRegistry, RuleRegistration
from polis.rules.agreement import AgreementCopulaRule


def test_agreement_copula_rule_fixes_obvious_mismatches() -> None:
    text = "Ona jestem.\nTy jestem.\nMy jestem.\nONA JESTEM.\nTy Jestem"

    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=AgreementCopulaRule(), categories={Category.AGREEMENT}),)
    )

    findings = registry.find(
        text, options=AnalysisOptions(categories={Category.AGREEMENT})
    )

    assert len(findings) == 5

    assert findings[0].category == Category.AGREEMENT
    assert findings[0].original == "jestem"
    assert findings[0].suggestion == "jest"
    assert findings[0].start == 4
    assert findings[0].end == 10

    assert findings[1].original == "jestem"
    assert findings[1].suggestion == "jesteś"

    assert findings[2].original == "jestem"
    assert findings[2].suggestion == "jesteśmy"

    assert findings[3].original == "JESTEM"
    assert findings[3].suggestion == "JEST"

    assert findings[4].original == "Jestem"
    assert findings[4].suggestion == "Jesteś"


def test_agreement_copula_rule_respects_category_filtering() -> None:
    text = "Ona jestem, to jest poprawne."

    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=AgreementCopulaRule(), categories={Category.AGREEMENT}),)
    )

    findings = registry.find(
        text, options=AnalysisOptions(categories={Category.SPELLING})
    )

    assert findings == ()
