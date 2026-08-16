"""Contract tests for ADR-0026 Umbrella F runtime cohort target (#339 F1.1)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Final

from polis.evaluation.calibration_sources import (
    SOURCE_ROWS,
    SOURCE_SNAPSHOT_SHA256,
    canonical_source_bytes,
)

ADR_0025: Final = (
    Path(__file__).resolve().parents[1]
    / "docs/architecture/decisions/0025-runtime-source-cohort-evolution.md"
)
ADR_0026: Final = (
    Path(__file__).resolve().parents[1]
    / "docs/architecture/decisions/0026-runtime-source-cohort-umbrella-f.md"
)
README: Final = Path(__file__).resolve().parents[1] / "docs/architecture/README.md"
EXPECTED_QUALIFICATION_DIGEST: Final = (
    "92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92"
)
EXPECTED_RUNTIME_ORDER: Final = (
    "rule:agreement.copula",
    "rule:agreement.copula_ja",
    "rule:agreement.te_zdanie",
    "rule:agreement.te_neuter_noun",
    "rule:agreement.nominal_group_te_duze_okno",
    "rule:agreement.nominal_group_ta_nowy_ksiazka",
    "rule:agreement.subject_verb_oni_czyta",
    "rule:agreement.subject_verb_my_czyta",
    "rule:inflection.negated_widziec",
    "rule:inflection.negated_widziec_nominal_group",
    "rule:inflection.negated_miec_czas",
    "rule:inflection.negated_lubic_kawe",
    "rule:inflection.przygladac_sie_nowy_budynek",
    "rule:inflection.government_potrzebowac_pomoc",
    "rule:inflection.government_szukac_klucz",
    "rule:inflection.government_sluchac_radio",
    "rule:inflection.government_uzywac_telefon",
    "rule:inflection.government_interesowac_sie_historia",
    "rule:inflection.government_byc_nauczyciel",
    "rule:inflection.government_do_sklep",
    "rule:inflection.government_ufac_lekarz",
    "rule:inflection.numeral_five_genitive_plural",
    "rule:spelling.jestes",
    "rule:spelling.napewno",
    "rule:spelling.wlasnie",
    "rule:spelling.zeby",
    "rule:spelling.wogole",
    "rule:spelling.wogole_diacritic",
    "rule:spelling.narazie",
    "rule:spelling.wziasc",
    "rule:spelling.wziasc_diacritic",
    "rule:spelling.conajmniej",
    "rule:spelling.poprostu",
    "rule:spelling.pozatym",
    "rule:spelling.przedewszystkim",
    "rule:spelling.wkoncu",
    "rule:spelling.spowrotem",
    "rule:spelling.tymbardziej",
    "rule:spelling.naprawde",
    "rule:spelling.nie_byc_joint",
    "rule:spelling.poszlem",
    "rule:spelling.wlanczac",
    "rule:spelling.month_weekday_lowercase",
    "rule:spelling.proper_adjective_lowercase",
    "rule:spelling.sentence_initial_capital",
    "rule:syntax.comma_space",
    "rule:syntax.duplicate_comma",
    "rule:syntax.initial_conditional_comma",
    "rule:syntax.initial_temporal_comma",
    "rule:syntax.comma_before_ze_reporting",
    "rule:syntax.comma_before_zeby_purpose",
    "rule:syntax.comma_before_bo",
    "rule:syntax.list_space",
    "rule:syntax.missing_correlative",
    "rule:syntax.missing_destination_preposition",
    "rule:syntax.missing_reflexive",
    "rule:syntax.quote_space",
    "rule:syntax.sentence_space",
    "rule:punctuation.abbreviation_dot",
)
EXPECTED_ADDITION_SOURCES: Final = frozenset(
    {
        "rule:agreement.copula_ja",
        "rule:agreement.te_neuter_noun",
        "rule:inflection.negated_miec_czas",
        "rule:inflection.negated_lubic_kawe",
        "rule:inflection.government_sluchac_radio",
        "rule:inflection.government_uzywac_telefon",
        "rule:inflection.government_interesowac_sie_historia",
        "rule:inflection.government_byc_nauczyciel",
        "rule:inflection.government_do_sklep",
        "rule:inflection.government_ufac_lekarz",
        "rule:inflection.numeral_five_genitive_plural",
        "rule:spelling.wogole_diacritic",
        "rule:spelling.wziasc_diacritic",
        "rule:spelling.conajmniej",
        "rule:spelling.poprostu",
        "rule:spelling.pozatym",
        "rule:spelling.przedewszystkim",
        "rule:spelling.wkoncu",
        "rule:spelling.spowrotem",
        "rule:spelling.tymbardziej",
        "rule:spelling.naprawde",
        "rule:spelling.nie_byc_joint",
        "rule:spelling.poszlem",
        "rule:spelling.wlanczac",
        "rule:spelling.month_weekday_lowercase",
        "rule:spelling.proper_adjective_lowercase",
        "rule:spelling.sentence_initial_capital",
        "rule:syntax.comma_before_ze_reporting",
        "rule:syntax.comma_before_zeby_purpose",
        "rule:syntax.comma_before_bo",
        "rule:punctuation.abbreviation_dot",
    }
)
FORBIDDEN_REINTRODUCTIONS: Final = (
    "rule:spelling.wsumie",
    "rule:spelling.nie_finite_verb_joint",
    "rule:spelling.missing_diacritic",
    "rule:syntax.comma_before_ktory",
    "rule:syntax.comma_before_contrastive",
    "rule:syntax.medial_temporal_conditional_comma",
    "rule:agreement.numeral_dwa_feminine",
    "rule:agreement.quantified_subject_verb_number",
    "rule:agreement.subject_verb_pronoun_czyta",
)


def test_adr_0026_freezes_active_runtime_cohort_contract() -> None:
    markdown = ADR_0026.read_text(encoding="utf-8")
    contract = dict(
        re.findall(r"^\| `([^`]+)` \| `([^`]+)` \|$", markdown, re.MULTILINE)
    )

    assert contract["qualification_cohort_id"] == (
        "polis-a-b-qualification-v2-source-cohort-v1"
    )
    assert contract["qualification_ordered_rows"] == "20"
    assert contract["qualification_source_snapshot_sha256"] == (
        EXPECTED_QUALIFICATION_DIGEST
    )
    assert contract["qualification_extra_source_handling"] == "reject"
    assert contract["runtime_source_cohort_id"] == "polis-runtime-source-cohort-59-v1"
    assert contract["runtime_ordered_sources"] == "59"
    assert contract["runtime_target_validation"] == "exact-ordered-59"
    assert contract["runtime_base_sources"] == "28"
    assert contract["runtime_planned_additions"] == "31"
    assert contract["additions_policy_state"] == "review-only"
    assert contract["additions_identity_kind"] == "planned-runtime-source-identity"
    assert contract["additions_source_policy_version"] == "absent"
    assert contract["additions_policy_entry"] == "none"
    assert contract["automatic_policy_identity_created"] == "false"
    assert contract["qualification_scope_inheritance"] == "forbidden"
    assert contract["automatic_requalification"] == (
        "new-dataset-and-experiment-identity"
    )
    assert contract["source_policy_version_inheritance"] == "forbidden"
    assert contract["supersedes_runtime_target_of"] == "ADR-0025"
    assert contract["umbrella_f_delivery_waves"] == "340+341+342"


def test_adr_0026_freezes_exact_target_runtime_order_of_59() -> None:
    markdown = ADR_0026.read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\d+) \| `(rule:[^`]+)` \|$", markdown, re.MULTILINE)

    assert tuple(position for position, _source in rows) == tuple(
        str(position) for position in range(1, 60)
    )
    assert tuple(source for _position, source in rows) == EXPECTED_RUNTIME_ORDER
    assert len(set(EXPECTED_RUNTIME_ORDER)) == 59


def test_adr_0026_freezes_exactly_31_review_only_additions() -> None:
    markdown = ADR_0026.read_text(encoding="utf-8")
    rows = re.findall(
        r"^\| (\d+) \| `([^`]+)` \| `([^`]+)` \| `([^`]+)` \| "
        r"`([^`]+)` \| `([^`]+)` \| `([^`]+)` \|$",
        markdown,
        re.MULTILINE,
    )

    assert len(rows) == 31
    sources = {source for _pos, source, *_rest in rows}
    assert sources == EXPECTED_ADDITION_SOURCES
    assert all(row[-1] == "review-only" for row in rows)
    positions = [int(position) for position, *_rest in rows]
    assert positions == sorted(positions)
    for _pos, source, *_rest in rows:
        assert source in EXPECTED_RUNTIME_ORDER


def test_adr_0026_excludes_refuted_sources_from_target_order() -> None:
    for source in FORBIDDEN_REINTRODUCTIONS:
        assert source not in EXPECTED_RUNTIME_ORDER
        assert source not in EXPECTED_ADDITION_SOURCES
    markdown = ADR_0026.read_text(encoding="utf-8")
    # Order table rows have exactly two cells: position and source.
    ordered_sources = {
        source
        for _pos, source in re.findall(
            r"^\| (\d+) \| `(rule:[^`]+)` \|$", markdown, re.MULTILINE
        )
    }
    assert ordered_sources == set(EXPECTED_RUNTIME_ORDER)
    for source in FORBIDDEN_REINTRODUCTIONS:
        assert source not in ordered_sources


def test_adr_0025_links_supersession_to_adr_0026() -> None:
    markdown = ADR_0025.read_text(encoding="utf-8")
    assert "0026-runtime-source-cohort-umbrella-f.md" in markdown
    assert "exact-ordered-59" in markdown
    assert "polis-runtime-source-cohort-59-v1" in markdown
    # Historical accepted record still freezes the E-era runtime target.
    contract = dict(
        re.findall(r"^\| `([^`]+)` \| `([^`]+)` \|$", markdown, re.MULTILINE)
    )
    assert contract["runtime_target_validation"] == "exact-ordered-28"
    assert contract["runtime_source_cohort_id"] == "polis-runtime-source-cohort-28-v1"


def test_architecture_readme_lists_adr_0026() -> None:
    text = README.read_text(encoding="utf-8")
    assert "0026-runtime-source-cohort-umbrella-f.md" in text
    assert "exact-ordered-59" in text


def test_qualification_cohort_digest_remains_byte_identical() -> None:
    assert len(SOURCE_ROWS) == 20
    assert SOURCE_SNAPSHOT_SHA256 == EXPECTED_QUALIFICATION_DIGEST
    assert hashlib.sha256(canonical_source_bytes()).hexdigest() == (
        EXPECTED_QUALIFICATION_DIGEST
    )
