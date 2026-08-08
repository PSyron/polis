from __future__ import annotations

from scripts.morphology_provider_json import ContractError

EXPECTED_CASE_SCOPE = (
    ("inflection_pomoc_genitive", "suggest"),
    ("government_samochod_genitive", "suggest"),
    ("agreement_nowy_feminine", "suggest"),
    ("negative_pomocy_already_genitive", "abstain"),
    ("negative_samochodu_already_genitive", "abstain"),
    ("ambiguity_nowy_without_source_filter", "abstain"),
    ("unknown_xyzzyq", "abstain"),
    ("negative_pomoc_wrong_gender", "abstain"),
    ("negative_nowy_noun_not_adjective", "abstain"),
)


def validate_case_scope(actual: tuple[tuple[str, str], ...]) -> None:
    ids = tuple(case_id for case_id, _ in actual)
    if len(ids) != len(set(ids)):
        raise ContractError("duplicate case id")
    if actual != EXPECTED_CASE_SCOPE:
        raise ContractError("dataset does not match the preregistered case set")
