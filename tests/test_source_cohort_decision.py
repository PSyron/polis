from __future__ import annotations

import re
from pathlib import Path
from typing import Final

ADR: Final = (
    Path(__file__).resolve().parents[1]
    / "docs/architecture/decisions/0025-runtime-source-cohort-evolution.md"
)
EXPECTED_QUALIFICATION_DIGEST: Final = (
    "92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92"
)
EXPECTED_RUNTIME_ORDER: Final = (
    "rule:agreement.copula",
    "rule:agreement.te_zdanie",
    "rule:agreement.nominal_group_te_duze_okno",
    "rule:agreement.nominal_group_ta_nowy_ksiazka",
    "rule:agreement.subject_verb_oni_czyta",
    "rule:agreement.subject_verb_my_czyta",
    "rule:inflection.negated_widziec",
    "rule:inflection.negated_widziec_nominal_group",
    "rule:inflection.przygladac_sie_nowy_budynek",
    "rule:inflection.government_potrzebowac_pomoc",
    "rule:inflection.government_szukac_klucz",
    "rule:spelling.jestes",
    "rule:spelling.napewno",
    "rule:spelling.wlasnie",
    "rule:spelling.zeby",
    "rule:spelling.wogole",
    "rule:spelling.narazie",
    "rule:spelling.wziasc",
    "rule:syntax.comma_space",
    "rule:syntax.duplicate_comma",
    "rule:syntax.initial_conditional_comma",
    "rule:syntax.initial_temporal_comma",
    "rule:syntax.list_space",
    "rule:syntax.missing_correlative",
    "rule:syntax.missing_destination_preposition",
    "rule:syntax.missing_reflexive",
    "rule:syntax.quote_space",
    "rule:syntax.sentence_space",
)
EXPECTED_ADDITIONS: Final = (
    (
        "4",
        "rule:agreement.nominal_group_ta_nowy_ksiazka",
        "agreement",
        "replace.adjective_gender",
        "agreement-nominal-group-ta-nowy-ksiazka/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
        "0.9",
        "review-only",
    ),
    (
        "6",
        "rule:agreement.subject_verb_my_czyta",
        "agreement",
        "replace.subject_verb_number",
        "agreement-subject-verb-my-czyta/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
        "0.9",
        "review-only",
    ),
    (
        "9",
        "rule:inflection.przygladac_sie_nowy_budynek",
        "inflection",
        "replace.governed_nominal_group",
        "inflection-przygladac-sie-nowy-budynek/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
        "0.9",
        "review-only",
    ),
    (
        "11",
        "rule:inflection.government_szukac_klucz",
        "inflection",
        "replace.governed_form",
        "inflection-government-szukac-klucz/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
        "0.9",
        "review-only",
    ),
    (
        "16",
        "rule:spelling.wogole",
        "spelling",
        "replace.common_typo",
        "spelling-wogole/1.0",
        "0.98",
        "review-only",
    ),
    (
        "17",
        "rule:spelling.narazie",
        "spelling",
        "replace.common_typo",
        "spelling-narazie/1.0",
        "0.98",
        "review-only",
    ),
    (
        "18",
        "rule:spelling.wziasc",
        "spelling",
        "replace.common_typo",
        "spelling-wziasc/1.0",
        "0.98",
        "review-only",
    ),
    (
        "22",
        "rule:syntax.initial_temporal_comma",
        "syntax",
        "insert.temporal_clause_comma",
        "syntax-initial-temporal-comma/1.0",
        "0.9",
        "review-only",
    ),
)


def test_decision_freezes_distinct_cohort_identities_and_boundaries() -> None:
    markdown = ADR.read_text(encoding="utf-8")
    contract = dict(
        re.findall(r"^\| `([^`]+)` \| `([^`]+)` \|$", markdown, re.MULTILINE)
    )

    assert contract == {
        "qualification_cohort_id": "polis-a-b-qualification-v2-source-cohort-v1",
        "qualification_ordered_rows": "20",
        "qualification_source_snapshot_sha256": EXPECTED_QUALIFICATION_DIGEST,
        "qualification_extra_source_handling": "reject",
        "runtime_source_cohort_id": "polis-runtime-source-cohort-28-v1",
        "runtime_ordered_sources": "28",
        "runtime_target_validation": "exact-ordered-28",
        "additions_policy_state": "review-only",
        "additions_identity_kind": "planned-runtime-source-identity",
        "additions_source_policy_version": "absent",
        "additions_policy_entry": "none",
        "automatic_policy_identity_created": "false",
        "qualification_scope_inheritance": "forbidden",
        "automatic_requalification": "new-dataset-and-experiment-identity",
        "automatic_requalification_exact_key": (
            "(source, category, operation, behavior_version, source_policy_version)"
        ),
        "source_policy_version_inheritance": "forbidden",
    }


def test_decision_freezes_exact_target_runtime_order() -> None:
    markdown = ADR.read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\d+) \| `(rule:[^`]+)` \|$", markdown, re.MULTILINE)

    assert tuple(position for position, _source in rows) == tuple(
        str(position) for position in range(1, 29)
    )
    assert tuple(source for _position, source in rows) == EXPECTED_RUNTIME_ORDER


def test_decision_freezes_exact_review_only_addition_identities() -> None:
    markdown = ADR.read_text(encoding="utf-8")
    rows = re.findall(
        r"^\| (\d+) \| `([^`]+)` \| `([^`]+)` \| `([^`]+)` \| "
        r"`([^`]+)` \| `([^`]+)` \| `([^`]+)` \|$",
        markdown,
        re.MULTILINE,
    )

    assert tuple(rows) == EXPECTED_ADDITIONS
