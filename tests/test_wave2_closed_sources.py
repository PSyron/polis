"""Wave 2 (#340) closed orthography and pure-inflection review-only sources."""

from __future__ import annotations

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import Category, Source, SourceKind
from polis.core.models import Confidence, Finding, Severity
from polis.correction.policy import (
    SOURCE_POLICY_VERSION,
    SourceBehavior,
    is_automatic_correction_eligible,
)
from polis.evaluation.quality_dataset import QualityDatasetVersion, load_quality_dataset

_SPELLING_CASES = (
    (
        "rule:spelling.wogole_diacritic",
        "Wogóle tego nie pamiętam.",
        "Wogóle",
        "W ogóle",
    ),
    ("rule:spelling.wziasc_diacritic", "Chcę wziąść parasol.", "wziąść", "wziąć"),
    (
        "rule:spelling.conajmniej",
        "Conajmniej spróbuj raz.",
        "Conajmniej",
        "Co najmniej",
    ),
    ("rule:spelling.poprostu", "Poprostu to powiedz.", "Poprostu", "Po prostu"),
    ("rule:spelling.pozatym", "Pozatym nic nie wiem.", "Pozatym", "Poza tym"),
    (
        "rule:spelling.przedewszystkim",
        "Przedewszystkim usiądź.",
        "Przedewszystkim",
        "Przede wszystkim",
    ),
    ("rule:spelling.wkoncu", "Wkońcu wróciłem do domu.", "Wkońcu", "W końcu"),
    (
        "rule:spelling.spowrotem",
        "Spowrotem wracam do pracy.",
        "Spowrotem",
        "Z powrotem",
    ),
    (
        "rule:spelling.tymbardziej",
        "Tymbardziej nie idę.",
        "Tymbardziej",
        "Tym bardziej",
    ),
    ("rule:spelling.naprawde", "Naprawde nie wiem.", "Naprawde", "Naprawdę"),
    (
        "rule:spelling.nie_byc_joint",
        "Niejestem gotowy dziś.",
        "Niejestem",
        "Nie jestem",
    ),
    ("rule:spelling.poszlem", "Poszłem już do sklepu.", "Poszłem", "Poszedłem"),
    ("rule:spelling.wlanczac", "Chcę włanczać światło.", "włanczać", "włączać"),
)

_GROUP_B = (
    ("rule:inflection.negated_miec_czas", "Nie mam czas.", "czas", "czasu"),
    ("rule:agreement.te_neuter_noun", "Te dziecko przyszło.", "Te", "To"),
    ("rule:agreement.copula_ja", "Ja jest gotowy.", "jest", "jestem"),
    (
        "rule:inflection.numeral_five_genitive_plural",
        "Pięć książki leży na stole.",
        "książki",
        "książek",
    ),
)

_WAVE2_SOURCES = tuple(item[0] for item in _SPELLING_CASES) + tuple(
    item[0] for item in _GROUP_B
)


def test_runtime_exposes_wave2_sources_in_adr_order() -> None:
    snapshot = Analyzer(AnalyzerConfig()).source_identity_snapshot
    assert len(snapshot) >= 45
    sources = [item.source for item in snapshot]
    for source in _WAVE2_SOURCES:
        assert source in sources
    # Relative order of delivered E spelling block stays contiguous with inserts.
    assert sources.index("rule:spelling.wogole") < sources.index(
        "rule:spelling.wogole_diacritic"
    )
    assert sources.index("rule:spelling.wogole_diacritic") < sources.index(
        "rule:spelling.narazie"
    )
    assert sources.index("rule:agreement.copula") < sources.index(
        "rule:agreement.copula_ja"
    )
    assert sources.index("rule:agreement.copula_ja") < sources.index(
        "rule:agreement.te_zdanie"
    )


@pytest.mark.parametrize(("source", "text", "original", "suggestion"), _SPELLING_CASES)
def test_wave2_spelling_emits_exact_contract(
    source: str, text: str, original: str, suggestion: str
) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(text)
    hits = [item for item in result.issues if str(item.source) == source]
    assert hits
    finding = hits[0]
    assert finding.category is Category.SPELLING
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == original
    assert finding.suggestion == suggestion
    assert text[finding.start : finding.end] == original
    assert finding.confidence.value == 0.98


@pytest.mark.parametrize(("source", "text", "original", "suggestion"), _GROUP_B)
def test_wave2_group_b_emits_exact_contract(
    source: str, text: str, original: str, suggestion: str
) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(text)
    hits = [item for item in result.issues if str(item.source) == source]
    assert hits
    finding = hits[0]
    assert finding.original == original
    assert finding.suggestion == suggestion
    assert text[finding.start : finding.end] == original
    # review-only: correct() does not auto-apply
    correction = Analyzer(AnalyzerConfig()).correct(text)
    assert correction.applied_findings == ()


def test_wkoncu_registers_both_joint_surfaces() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    a = analyzer.analyze("Wkońcu wróciłem.")
    b = analyzer.analyze("Wkoncu wróciłem.")
    assert any(str(i.source) == "rule:spelling.wkoncu" for i in a.issues)
    assert any(str(i.source) == "rule:spelling.wkoncu" for i in b.issues)


def test_nie_byc_joint_excludes_niejestes_and_maps_closed_surfaces() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    assert not any(
        str(i.source) == "rule:spelling.nie_byc_joint"
        for i in analyzer.analyze("Niejestes gotowy.").issues
    )
    for text, suggestion in (
        ("Niebędzie padać.", "Nie będzie"),
        ("Niebył gotowy.", "Nie był"),
    ):
        hits = [
            i
            for i in analyzer.analyze(text).issues
            if str(i.source) == "rule:spelling.nie_byc_joint"
        ]
        assert hits and hits[0].suggestion == suggestion


def test_poszlem_excludes_przeszlem_and_przyszlem() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text in ("Przeszłem już do sklepu.", "Przyszłem już do sklepu."):
        assert not any(
            str(i.source) == "rule:spelling.poszlem"
            for i in analyzer.analyze(text).issues
        )


def test_wziasc_diacritic_excludes_mixed_near_zero_surfaces() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text in ("Chcę wziąśc parasol.", "Chcę wziasć parasol."):
        assert not any(
            str(i.source) == "rule:spelling.wziasc_diacritic"
            for i in analyzer.analyze(text).issues
        )


def test_wlanczac_is_literal_map_not_substring_rewrite() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    assert any(
        str(i.source) == "rule:spelling.wlanczac"
        for i in analyzer.analyze("Chcę wyłanczać lampę.").issues
    )
    # no productive odłanczać
    assert not any(
        str(i.source) == "rule:spelling.wlanczac"
        for i in analyzer.analyze("Chcę odłanczać lampę.").issues
    )


def test_te_neuter_excludes_zdanie_miasto_and_comma_vocative() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    # te_zdanie owns zdanie; te_neuter must not fire on it
    te_neuter = [
        i
        for i in analyzer.analyze("Te zdanie jest poprawne.").issues
        if str(i.source) == "rule:agreement.te_neuter_noun"
    ]
    assert te_neuter == []
    assert not any(
        str(i.source) == "rule:agreement.te_neuter_noun"
        for i in analyzer.analyze("Te miasto jest duże.").issues
    )
    assert not any(
        str(i.source) == "rule:agreement.te_neuter_noun"
        for i in analyzer.analyze("Te dziecko, chodź tu.").issues
    )


def test_copula_ja_excludes_jestes_contention() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    issues = analyzer.analyze("Ja jestes gotowy.").issues
    assert not any(str(i.source) == "rule:agreement.copula_ja" for i in issues)


def test_numeral_five_requires_sentence_anchor() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    # unanchored mid-clause should abstain
    assert not any(
        str(i.source) == "rule:inflection.numeral_five_genitive_plural"
        for i in analyzer.analyze("Widziałem pięć książki na stole bez kotwicy.").issues
    )
    assert any(
        str(i.source) == "rule:inflection.numeral_five_genitive_plural"
        for i in analyzer.analyze("Pięć książki leży na stole.").issues
    )


def test_group_b_identical_without_morphology_extra() -> None:
    # Default env may or may not have morfeusz; identity must not depend on it.
    analyzer = Analyzer(AnalyzerConfig())
    for source, text, original, suggestion in _GROUP_B:
        hits = [i for i in analyzer.analyze(text).issues if str(i.source) == source]
        assert (
            hits and hits[0].original == original and hits[0].suggestion == suggestion
        )


@pytest.mark.parametrize("source", _WAVE2_SOURCES)
def test_wave2_sources_remain_review_only(source: str) -> None:
    name = source.removeprefix("rule:")
    behavior_version = {
        "spelling.wogole_diacritic": "spelling-wogole-diacritic/1.0",
        "spelling.wziasc_diacritic": "spelling-wziasc-diacritic/1.0",
        "spelling.conajmniej": "spelling-conajmniej/1.0",
        "spelling.poprostu": "spelling-poprostu/1.0",
        "spelling.pozatym": "spelling-pozatym/1.0",
        "spelling.przedewszystkim": "spelling-przedewszystkim/1.0",
        "spelling.wkoncu": "spelling-wkoncu/1.0",
        "spelling.spowrotem": "spelling-spowrotem/1.0",
        "spelling.tymbardziej": "spelling-tymbardziej/1.0",
        "spelling.naprawde": "spelling-naprawde/1.0",
        "spelling.nie_byc_joint": "spelling-nie-byc-joint/1.0",
        "spelling.poszlem": "spelling-poszlem/1.0",
        "spelling.wlanczac": "spelling-wlanczac/1.0",
        "inflection.negated_miec_czas": "inflection-negated-miec-czas/1.0",
        "agreement.te_neuter_noun": "agreement-te-neuter-noun/2.0",
        "agreement.copula_ja": "agreement-copula-ja/1.0",
        "inflection.numeral_five_genitive_plural": (
            "inflection-numeral-five-genitive-plural/1.0"
        ),
    }[name]
    category = {
        "spelling": Category.SPELLING,
        "inflection": Category.INFLECTION,
        "agreement": Category.AGREEMENT,
    }[name.split(".", 1)[0]]
    operation = {
        "spelling": "replace.common_typo",
        "inflection": "replace.governed_form",
        "agreement.te_neuter_noun": "replace.pronoun_gender",
        "agreement.copula_ja": "replace.copula_person",
    }
    if name.startswith("spelling."):
        op = operation["spelling"]
    elif name.startswith("inflection."):
        op = operation["inflection"]
    else:
        op = operation[name]
    source_obj = Source(SourceKind.RULE, name)
    finding = Finding.create(
        category=category,
        severity=Severity.SUGGESTION,
        message="x",
        explanation="x",
        original="x",
        suggestion="y",
        start=0,
        end=1,
        confidence=Confidence(0.99),
        source=source_obj,
    )
    behavior = SourceBehavior(
        source=source_obj, operation=op, behavior_version=behavior_version
    )
    assert not is_automatic_correction_eligible(
        finding, behavior, source_policy_version=SOURCE_POLICY_VERSION
    )


def test_wave2_group_b_quotation_mentions_abstain() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text, source in (
        (
            "Cytat „Ja jest gotowy” omawiamy bez zmiany.",
            "rule:agreement.copula_ja",
        ),
        (
            "Cytat „Te dziecko” omawiamy bez zmiany.",
            "rule:agreement.te_neuter_noun",
        ),
    ):
        assert not any(
            str(item.source) == source for item in analyzer.analyze(text).issues
        )


def test_wave2_mixed_uppercase_diacritic_surfaces_map_to_full_upper() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text, source, suggestion in (
        ("ŁÓDŹ: WOGóLE NIE PADA.", "rule:spelling.wogole_diacritic", "W OGÓLE"),
        ("ŻÓŁĆ: WKOńCU WRÓCIŁEM.", "rule:spelling.wkoncu", "W KOŃCU"),
    ):
        hits = [
            item for item in analyzer.analyze(text).issues if str(item.source) == source
        ]
        assert hits and hits[0].suggestion == suggestion


def test_wave2_v3_error_cases_flip_fn_to_tp_for_implemented_sources() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V3)
    analyzer = Analyzer(AnalyzerConfig())
    # Map planned source suffix to a representative v3 error case id prefix
    samples = {
        "rule:spelling.wogole_diacritic": "v3_wogole_diacritic_error",
        "rule:spelling.conajmniej": "v3_conajmniej_error",
        "rule:spelling.naprawde": "v3_naprawde_error",
        "rule:inflection.negated_miec_czas": "v3_negated_miec_czas_error",
        "rule:agreement.copula_ja": "v3_copula_ja_error",
        "rule:agreement.te_neuter_noun": "v3_te_neuter_noun_error",
    }
    by_id = {case.id: case for case in dataset.cases}
    for source, case_id in samples.items():
        case = by_id[case_id]
        issues = analyzer.analyze(case.text).issues
        assert any(str(item.source) == source for item in issues)
        # no false alarms on correct pair
        pair = by_id[case_id.replace("_error", "_corrected_pair")]
        pair_issues = [
            item
            for item in analyzer.analyze(pair.text).issues
            if str(item.source) == source
        ]
        assert pair_issues == []


def test_wave2_spelling_abstains_on_url_and_assignment_guards() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text in (
        "https://example.com/wogóle",
        "wogóle=3",
        "tag #wogóle",
    ):
        assert not any(
            str(i.source) == "rule:spelling.wogole_diacritic"
            for i in analyzer.analyze(text).issues
        )
