"""Wave 4 (#342) morphology-backed government sources."""

from __future__ import annotations

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions, Category, Confidence, Source, SourceKind
from polis.core.models import Finding, Severity
from polis.correction.policy import (
    SOURCE_POLICY_VERSION,
    SourceBehavior,
    is_automatic_correction_eligible,
)
from polis.evaluation.quality_dataset import QualityDatasetVersion, load_quality_dataset
from polis.rules._morfeusz import _ProviderIdentity, _QualifiedMorfeusz
from polis.rules.government import InflectionGovernmentSluchacRadioRule

_NOTICE = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
_PROVIDER_SUFFIX = "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-" + _NOTICE


def _behavior_version(source: str, stem: str) -> str:
    major = (
        2
        if source
        in {
            "rule:inflection.government_szukac_klucz",
            "rule:inflection.government_uzywac_telefon",
            "rule:inflection.government_interesowac_sie_historia",
            "rule:inflection.government_do_sklep",
            "rule:inflection.government_ufac_lekarz",
        }
        else 1
    )
    return f"{stem}/{major}.0+{_PROVIDER_SUFFIX}"


_CASES = (
    (
        "rule:inflection.government_sluchac_radio",
        "Słucham radio.",
        "radio",
        "radia",
        8,
        13,
        "inflection-government-sluchac-radio",
    ),
    (
        "rule:inflection.government_uzywac_telefon",
        "Używam telefon.",
        "telefon",
        "telefonu",
        7,
        14,
        "inflection-government-uzywac-telefon",
    ),
    (
        "rule:inflection.government_interesowac_sie_historia",
        "Interesuję się historia.",
        "historia",
        "historią",
        15,
        23,
        "inflection-government-interesowac-sie-historia",
    ),
    (
        "rule:inflection.government_byc_nauczyciel",
        "Jestem nauczyciel.",
        "nauczyciel",
        "nauczycielem",
        7,
        17,
        "inflection-government-byc-nauczyciel",
    ),
    (
        "rule:inflection.government_do_sklep",
        "Idę do sklep.",
        "sklep",
        "sklepu",
        7,
        12,
        "inflection-government-do-sklep",
    ),
    (
        "rule:inflection.government_ufac_lekarz",
        "Ufam lekarz.",
        "lekarz",
        "lekarzowi",
        5,
        11,
        "inflection-government-ufac-lekarz",
    ),
    (
        "rule:inflection.negated_lubic_kawe",
        "Nie lubię kawę.",
        "kawę",
        "kawy",
        10,
        14,
        "inflection-negated-lubic-kawe",
    ),
)

_WAVE4 = tuple(item[0] for item in _CASES)


def test_runtime_exposes_sixty_sources_after_issue_386() -> None:
    snapshot = Analyzer(AnalyzerConfig()).source_identity_snapshot
    assert len(snapshot) == 62
    sources = [item.source for item in snapshot]
    for source in _WAVE4:
        assert source in sources
    assert sources.index("rule:inflection.negated_miec_czas") < sources.index(
        "rule:inflection.negated_lubic_kawe"
    )
    assert sources.index("rule:inflection.government_szukac_klucz") < sources.index(
        "rule:inflection.government_sluchac_radio"
    )
    assert sources.index("rule:inflection.government_ufac_lekarz") < sources.index(
        "rule:inflection.numeral_five_genitive_plural"
    )


@pytest.mark.parametrize(
    ("source", "text", "original", "suggestion", "start", "end", "stem"),
    _CASES,
)
def test_wave4_emits_exact_contract_with_provider(
    source: str,
    text: str,
    original: str,
    suggestion: str,
    start: int,
    end: int,
    stem: str,
) -> None:
    analyzer = Analyzer(AnalyzerConfig())
    hits = [
        item for item in analyzer.analyze(text).issues if str(item.source) == source
    ]
    assert hits
    finding = hits[0]
    assert finding.category is Category.INFLECTION
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == original
    assert finding.suggestion == suggestion
    assert (finding.start, finding.end) == (start, end)
    assert text[finding.start : finding.end] == original
    assert finding.confidence.value == 0.9
    behavior = analyzer._registry.source_behavior(finding.source)
    assert behavior is not None
    assert behavior.operation == "replace.governed_form"
    assert behavior.behavior_version == _behavior_version(source, stem)
    correction = analyzer.correct(text)
    assert correction.applied_findings == ()
    assert any(str(item.source) == source for item in correction.skipped_findings)


def test_wave4_coordination_shape_abstains() -> None:
    # Mandatory: NP-final excludes comma (coordination).
    result = Analyzer(AnalyzerConfig()).analyze("Używam telefon, laptop i tablet.")
    assert not any(
        str(item.source) == "rule:inflection.government_uzywac_telefon"
        for item in result.issues
    )


def test_wave4_filename_domain_shape_abstains() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text in ("Słucham radio.txt", "Używam telefon.com"):
        assert not any(
            "government_" in str(item.source) for item in analyzer.analyze(text).issues
        )


def test_wave4_title_case_governed_noun_abstains() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text, source in (
        ("Słucham Radio.", "rule:inflection.government_sluchac_radio"),
        (
            "Interesuję się Historia.",
            "rule:inflection.government_interesowac_sie_historia",
        ),
    ):
        assert not any(
            str(item.source) == source for item in analyzer.analyze(text).issues
        )


def test_wave4_already_correct_and_wrong_lexeme_abstain() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    for text, source in (
        ("Słucham radia.", "rule:inflection.government_sluchac_radio"),
        ("Używam telefonu.", "rule:inflection.government_uzywac_telefon"),
        ("Słucham telewizor.", "rule:inflection.government_sluchac_radio"),
        ("Ufam lekarzowi.", "rule:inflection.government_ufac_lekarz"),
    ):
        assert not any(
            str(item.source) == source for item in analyzer.analyze(text).issues
        )


def test_wave4_missing_provider_abstains(monkeypatch: pytest.MonkeyPatch) -> None:
    import polis.analyzer as analyzer_module

    monkeypatch.setattr(analyzer_module, "_load_qualified_morfeusz", lambda: None)
    analyzer = Analyzer(AnalyzerConfig())
    for source, text, *_rest in _CASES:
        assert not any(
            str(item.source) == source for item in analyzer.analyze(text).issues
        )
    # pure deterministic still works without morphology
    assert any(
        str(item.source) == "rule:inflection.negated_miec_czas"
        for item in analyzer.analyze("Nie mam czas.").issues
    )


def test_wave4_provider_identity_drift_abstains() -> None:
    class _UnusedBackend:
        def analyse(self, text: str) -> list[object]:
            raise AssertionError(text)

        def generate(self, lemma: str) -> list[object]:
            raise AssertionError(lemma)

    drifted = _QualifiedMorfeusz(
        backend=_UnusedBackend(),
        identity=_ProviderIdentity(
            package_version="1.99.16",
            dictionary_id="pl.sgjp.sgjp-2026.06.01",
            dictionary_notice_sha256=_NOTICE,
        ),
    )
    rule = InflectionGovernmentSluchacRadioRule(drifted)
    assert rule.find("Słucham radio.", options=AnalysisOptions()) == ()


@pytest.mark.parametrize("source", _WAVE4)
def test_wave4_sources_remain_review_only(source: str) -> None:
    name = source.removeprefix("rule:")
    stem = {
        "inflection.government_sluchac_radio": "inflection-government-sluchac-radio",
        "inflection.government_uzywac_telefon": "inflection-government-uzywac-telefon",
        "inflection.government_interesowac_sie_historia": (
            "inflection-government-interesowac-sie-historia"
        ),
        "inflection.government_byc_nauczyciel": "inflection-government-byc-nauczyciel",
        "inflection.government_do_sklep": "inflection-government-do-sklep",
        "inflection.government_ufac_lekarz": "inflection-government-ufac-lekarz",
        "inflection.negated_lubic_kawe": "inflection-negated-lubic-kawe",
    }[name]
    source_obj = Source(SourceKind.RULE, name)
    finding = Finding.create(
        category=Category.INFLECTION,
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
        source=source_obj,
        operation="replace.governed_form",
        behavior_version=_behavior_version(source, stem),
    )
    assert not is_automatic_correction_eligible(
        finding, behavior, source_policy_version=SOURCE_POLICY_VERSION
    )


def test_wave4_v3_error_cases_flip_fn_to_tp() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V3)
    analyzer = Analyzer(AnalyzerConfig())
    samples = {
        "rule:inflection.government_sluchac_radio": (
            "v3_government_sluchac_radio_error"
        ),
        "rule:inflection.government_uzywac_telefon": (
            "v3_government_uzywac_telefon_error"
        ),
        "rule:inflection.government_interesowac_sie_historia": (
            "v3_government_interesowac_sie_historia_error"
        ),
        "rule:inflection.government_byc_nauczyciel": (
            "v3_government_byc_nauczyciel_error"
        ),
        "rule:inflection.government_do_sklep": "v3_government_do_sklep_error",
        "rule:inflection.government_ufac_lekarz": "v3_government_ufac_lekarz_error",
        "rule:inflection.negated_lubic_kawe": "v3_negated_lubic_kawe_error",
    }
    by_id = {case.id: case for case in dataset.cases}
    for source, case_id in samples.items():
        case = by_id[case_id]
        assert any(
            str(item.source) == source for item in analyzer.analyze(case.text).issues
        )
        pair = by_id[case_id.replace("_error", "_corrected_pair")]
        pair_hits = [
            item
            for item in analyzer.analyze(pair.text).issues
            if str(item.source) == source
        ]
        assert pair_hits == []
