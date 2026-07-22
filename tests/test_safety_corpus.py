from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, cast

import pytest

from polis.evaluation import (
    assert_no_cross_corpus_leakage,
    load_safety_corpus_json,
    load_safety_corpus_xml,
    safety_corpus_digest,
    select_safety_cases_for_purpose,
    validate_safety_corpus,
)
from polis.evaluation.correction_corpus import (
    _CONTROLLED_ENTITY_SURFACES,
    CorpusUsageError,
    EntitySpan,
    IsolationRecord,
    load_correction_corpus_json,
)
from polis.evaluation.correction_corpus import (
    _entity_id as corpus_v3_entity_id,
)
from polis.evaluation.safety_corpus import safety_entity_catalog_ids

ROOT = Path(__file__).resolve().parents[1]
JSON_CORPUS = (
    ROOT
    / "tests"
    / "fixtures"
    / "evaluation"
    / "polish_correction_safety_corpus_v1.json"
)
XML_CORPUS = (
    ROOT
    / "tests"
    / "fixtures"
    / "evaluation"
    / "polish_correction_safety_corpus_v1.xml"
)
CORPUS_V3 = (
    ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"
)
E2E_CORPUS = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.json"
E2E_XML_CORPUS = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.xml"
GUIDE = ROOT / "docs" / "evaluation-dataset.md"
QUALITY_GATES = ROOT / "docs" / "llm-quality-gates.md"
LIMITATIONS = ROOT / "docs" / "limitations.md"
CHECKLIST = ROOT / "docs" / "evaluation-safety-corpus-v1-review-checklist.md"


def _raw_corpus() -> dict[str, Any]:
    value: Any = json.loads(JSON_CORPUS.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_safety_corpus_api_is_public() -> None:
    assert callable(load_safety_corpus_json)


def test_candidate_corpus_has_exact_balance() -> None:
    corpus = load_safety_corpus_json(JSON_CORPUS)

    assert len(corpus.cases) == 240
    for stratum in ("inflection", "syntax", "punctuation", "hard_negative"):
        cases = [case for case in corpus.cases if case.stratum == stratum]
        assert len(cases) == 60
        assert sum(case.split == "development" for case in cases) == 20
        assert sum(case.split == "holdout" for case in cases) == 40


def test_corpus_is_frozen_after_complete_owner_review() -> None:
    corpus = load_safety_corpus_json(JSON_CORPUS)

    assert corpus.holdout_state == "frozen"
    assert corpus.required_reviewer == "Paweł Cyroń"
    assert all(case.provenance.license == "CC0-1.0" for case in corpus.cases)
    assert all(case.review.status == "human-reviewed" for case in corpus.cases)
    assert all(case.review.reviewer == "Paweł Cyroń" for case in corpus.cases)
    assert all(case.review.reviewed_at == "2026-07-22" for case in corpus.cases)


def test_json_and_xml_candidates_are_equivalent() -> None:
    assert load_safety_corpus_json(JSON_CORPUS) == load_safety_corpus_xml(XML_CORPUS)


def test_canonical_digest_ignores_formatting_and_tracks_content() -> None:
    raw = _raw_corpus()
    reformatted = json.loads(json.dumps(raw, ensure_ascii=False, indent=7))
    changed = copy.deepcopy(raw)
    changed["cases"][0]["description"] += " Changed."

    assert safety_corpus_digest(raw) == safety_corpus_digest(reformatted)
    assert safety_corpus_digest(raw) != safety_corpus_digest(changed)


def test_development_code_cannot_load_pending_or_holdout_gold() -> None:
    raw = _raw_corpus()
    raw["holdout_state"] = "unfrozen-candidates"
    for case in raw["cases"]:
        case["review"] = {
            "status": "pending-human-review",
            "reviewer": None,
            "reviewed_at": None,
            "checklist_version": "safety-corpus-review-v1",
        }
    pending = validate_safety_corpus(raw)

    with pytest.raises(CorpusUsageError, match="pending-human-review"):
        select_safety_cases_for_purpose(pending, purpose="benchmark")

    first_development = next(
        case for case in raw["cases"] if case["split"] == "development"
    )
    first_development["review"] = {
        "status": "human-reviewed",
        "reviewer": "Paweł Cyroń",
        "reviewed_at": "2026-07-22",
        "checklist_version": "safety-corpus-review-v1",
    }
    partially_reviewed = validate_safety_corpus(raw)

    selected = select_safety_cases_for_purpose(partially_reviewed, purpose="benchmark")
    assert [case.id for case in selected] == [first_development["id"]]
    assert all(case.split == "development" for case in selected)


def test_quality_gate_requires_frozen_complete_owner_review() -> None:
    corpus = load_safety_corpus_json(JSON_CORPUS)

    selected = select_safety_cases_for_purpose(corpus, purpose="quality_gate")
    assert len(selected) == 160
    assert all(case.split == "holdout" for case in selected)
    with pytest.raises(CorpusUsageError, match="prohibited"):
        select_safety_cases_for_purpose(corpus, purpose="training")


def test_cross_asset_records_require_valid_entity_span_evidence() -> None:
    corpus = load_safety_corpus_json(JSON_CORPUS)
    invalid = IsolationRecord(
        id="invalid-span",
        input="Obcy zapis pozostaje niezależny.",
        entity_spans=(EntitySpan(start=0, end=4, surface="Inny"),),
    )

    with pytest.raises(CorpusUsageError, match="invalid entity span evidence"):
        assert_no_cross_corpus_leakage(corpus, [invalid], source="adversary")


def test_safety_entity_catalog_is_disjoint_from_corpus_v3() -> None:
    corpus_v3_ids = frozenset(
        corpus_v3_entity_id(surface) for surface in _CONTROLLED_ENTITY_SURFACES
    )

    assert safety_entity_catalog_ids().isdisjoint(corpus_v3_ids)


def test_corpus_is_independent_from_corpus_v3() -> None:
    safety = load_safety_corpus_json(JSON_CORPUS)
    corpus_v3 = load_correction_corpus_json(CORPUS_V3)
    records = [
        IsolationRecord(id=case.id, input=case.input, entity_spans=case.entity_spans)
        for case in corpus_v3.cases
    ]

    assert_no_cross_corpus_leakage(safety, records, source="corpus-v3")


def test_corpus_is_independent_from_finetuning_assets() -> None:
    safety = load_safety_corpus_json(JSON_CORPUS)
    records: list[IsolationRecord] = []
    directory = ROOT / "data" / "finetuning" / "bielik_1_5b_v1"
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = json.loads(line)
            spans = tuple(
                EntitySpan(
                    start=span["start"], end=span["end"], surface=span["surface"]
                )
                for span in raw["entity_spans"]
            )
            records.append(
                IsolationRecord(
                    id=f"{path.name}:{raw['id']}",
                    input=raw["source_text"],
                    entity_spans=spans,
                )
            )

    assert records
    assert_no_cross_corpus_leakage(safety, records, source="finetuning")


def test_corpus_is_independent_from_prompt_examples_and_e2e() -> None:
    from polis.llm import corrected_text

    safety = load_safety_corpus_json(JSON_CORPUS)
    e2e_raw = json.loads(E2E_CORPUS.read_text(encoding="utf-8"))
    records = [
        IsolationRecord(id=f"e2e:{case['id']}", input=case["input"])
        for case in e2e_raw["cases"]
    ]
    records.extend(
        IsolationRecord(
            id=f"e2e-xml:{case.get('id', '')}",
            input=case.findtext("input") or "",
        )
        for case in ET.parse(E2E_XML_CORPUS).getroot().findall("case")
    )
    records.extend(
        IsolationRecord(id=f"focus:{focus}", input=example[0])
        for focus, example in corrected_text._FOCUS_EXAMPLES.items()
    )
    records.extend(
        IsolationRecord(id=f"diagnostic:{variant}:{index}", input=example[0])
        for variant, examples in corrected_text._DIAGNOSTIC_EXAMPLES.items()
        for index, example in enumerate(examples, 1)
    )

    assert_no_cross_corpus_leakage(safety, records, source="prompt-e2e")


def test_candidate_documentation_records_identity_boundaries_and_review() -> None:
    checklist = CHECKLIST.read_text(encoding="utf-8")
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in (GUIDE, QUALITY_GATES, LIMITATIONS)
    )

    for item in (
        "Correctness",
        "Category",
        "Minimality",
        "Offsets",
        "Reconstruction",
        "Proper-name behavior",
        "Syntax and word order",
        "Provenance",
        "Licensing",
        "Isolation",
    ):
        assert item in checklist
    assert "Paweł Cyroń" in checklist
    assert "polis_polish_correction_safety_corpus_v1" in combined
    assert "frozen" in combined
    assert "CC0-1.0" in combined
    assert "corpus v3" in combined
    assert "#85" in combined
    assert "no holdout score" in combined
    assert "digest" in combined.casefold()


def test_owner_review_regressions_have_grammatical_expected_text() -> None:
    raw = _raw_corpus()
    cases = {case["id"]: case for case in raw["cases"]}
    expected_inflection = {
        21: "Podczas odprawy przyglądano się nowemu projektowi remontu.",
        22: "Po naradzie sekretarz poświęcił uwagę wewnętrznemu regulaminowi archiwum.",
        23: "Przed kontrolą technik przyjrzał się pomiarowemu urządzeniu zapasowemu.",
        24: (
            "W trakcie dyżuru bibliotekarz przyglądał się odnowionemu obrazowi "
            "w czytelni."
        ),
        25: (
            "Po remoncie kustosz poświęcił uwagę kwartalnemu raportowi "
            "konserwatorskiemu."
        ),
        26: "Wieczorem dyspozytor przyjrzał się formalnemu wnioskowi przewoźnika.",
        27: "Przed wyjazdem opiekun przyglądał się turystycznemu plecakowi uczestnika.",
        28: "Po próbie realizator poświęcił uwagę bezprzewodowemu mikrofonowi solisty.",
        29: (
            "Podczas inwentaryzacji księgowy przyjrzał się rocznemu bilansowi fundacji."
        ),
        30: (
            "Po spotkaniu koordynator poświęcił uwagę roboczemu harmonogramowi "
            "odbiorów."
        ),
        31: "Podczas odprawy rozmawiano o wysokim budynku dworca.",
        32: "Po naradzie sekretarz czekał w chłodnym magazynie archiwum.",
        33: "Przed kontrolą technik pracował w nowoczesnym laboratorium pomiarowym.",
        34: "W trakcie dyżuru bibliotekarz był w miejskim muzeum techniki.",
        35: "Po remoncie ratownik pracował na ratunkowym oddziale szpitala.",
        36: "Wieczorem dyspozytor czekał w północnym terminalu lotniska.",
        37: "Przed wyjazdem opiekun nocował w górskim schronisku turystycznym.",
        38: "Po próbie realizator pracował w nagraniowym studiu radiowym.",
        39: "Podczas inwentaryzacji księgowy został w regionalnym biurze fundacji.",
        40: "Po spotkaniu koordynator czekał w szkoleniowym ośrodku branżowym.",
        41: "Podczas odprawy magazynier przyszedł z małą skrzynką narzędziową.",
        42: "Po naradzie sekretarz opatrzył dokument urzędową pieczęcią.",
        43: "Przed kontrolą technik wykonał pomiar ręczną sondą.",
        44: "W trakcie dyżuru bibliotekarz przeniósł obraz z drewnianą ramą.",
        45: "Po remoncie kustosz posłużył się precyzyjną wagą jubilerską.",
        46: "Wieczorem dyspozytor pracował z kierunkową anteną radiową.",
        47: "Przed wyjazdem opiekun zabezpieczył ładunek asekuracyjną liną.",
        48: "Po próbie realizator posłużył się studyjną kamerą cyfrową.",
        49: "Podczas inwentaryzacji księgowy pracował ze zbiorczą tabelą kosztów.",
        50: "Po spotkaniu koordynator posłużył się kontrolną listą odbiorową.",
    }
    for number, expected in expected_inflection.items():
        assert cases[f"safety_inflection_{number:03d}"]["expected_output"] == expected

    expected_syntax = {
        15: "Część dekoracji wymagała pilnej naprawy.",
        18: "Biblioteka nagrań zajmowała trzy regały.",
        31: "Żaden z pełnomocników nie podpisał kompletu dokumentów.",
        32: "Żaden z techników nie wpisał wyniku pomiaru.",
        33: "Żaden z projektantów nie dołączył szczegółowego planu naprawy.",
        34: "Żaden z delegatów nie zgłosił wspólnego stanowiska.",
        35: "Żaden z aktorów nie pominął uwag realizatora.",
        36: "Żaden z kontrolerów nie zauważył brakujących pozycji.",
        37: "Żaden z pilotów nie zmienił trasy na mapie.",
        38: "Żaden z realizatorów nie usunął plików z katalogu.",
        39: "Żaden z audytorów nie zakwestionował kosztów ujętych w raporcie.",
        40: "Żaden z dostawców nie przesunął terminów kolejnych odbiorów.",
    }
    for number, expected in expected_syntax.items():
        assert cases[f"safety_syntax_{number:03d}"]["expected_output"] == expected

    expected_punctuation = {
        42: "Raport, jak ocenił zespół, wymaga jeszcze krótkiego uzupełnienia.",
        45: "Raport, jak zauważył dyspozytor, wymaga jeszcze krótkiego uzupełnienia.",
        46: "Raport, jak podkreślił przewodnik, wymaga jeszcze krótkiego uzupełnienia.",
        47: "Raport, co wspólnie ustaliliśmy, wymaga jeszcze krótkiego uzupełnienia.",
        48: "Raport, jak wynika z bilansu, wymaga jeszcze krótkiego uzupełnienia.",
        49: "Raport, jak ocenił koordynator, wymaga jeszcze krótkiego uzupełnienia.",
    }
    for number, expected in expected_punctuation.items():
        assert cases[f"safety_punctuation_{number:03d}"]["expected_output"] == expected

    hard_negative = cases["safety_hard_negative_008"]
    assert hard_negative["input"] == "Koszt wzrósł o 9,40 zł."
    assert hard_negative["expected_output"] == hard_negative["input"]


def test_owner_reviewed_corpus_is_frozen_and_digest_is_documented() -> None:
    raw = _raw_corpus()
    corpus = validate_safety_corpus(raw)

    assert corpus.holdout_state == "frozen"
    assert all(case.review.status == "human-reviewed" for case in corpus.cases)
    assert all(case.review.reviewer == "Paweł Cyroń" for case in corpus.cases)
    assert all(case.review.reviewed_at == "2026-07-22" for case in corpus.cases)
    assert safety_corpus_digest(raw) in GUIDE.read_text(encoding="utf-8")


def test_frozen_generator_is_pinned_to_reviewed_digest() -> None:
    from scripts.generate_safety_corpus_candidates import (
        FROZEN_DIGEST,
        build_candidate_corpus,
        build_frozen_corpus,
    )

    candidate = validate_safety_corpus(build_candidate_corpus())
    assert candidate.holdout_state == "unfrozen-candidates"
    assert all(case.review.status == "pending-human-review" for case in candidate.cases)
    assert all(case.review.reviewer is None for case in candidate.cases)
    assert safety_corpus_digest(build_frozen_corpus()) == FROZEN_DIGEST
    assert FROZEN_DIGEST == safety_corpus_digest(_raw_corpus())


def test_generator_checks_every_reserved_asset_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import generate_safety_corpus_candidates as generator

    checked: list[str] = []
    original = generator.validate_reserved_asset_isolation

    def validate(raw: dict[str, Any]) -> None:
        original(raw)
        checked.append(safety_corpus_digest(raw))

    monkeypatch.setattr(generator, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(generator, "JSON_PATH", tmp_path / "corpus.json")
    monkeypatch.setattr(generator, "XML_PATH", tmp_path / "corpus.xml")
    monkeypatch.setattr(generator, "validate_reserved_asset_isolation", validate)

    generator.main()

    assert checked == [generator.FROZEN_DIGEST]
    assert (tmp_path / "corpus.json").is_file()
    assert (tmp_path / "corpus.xml").is_file()


def test_protected_name_cases_have_complete_entity_evidence() -> None:
    corpus = load_safety_corpus_json(JSON_CORPUS)
    protected_names = [
        case
        for case in corpus.cases
        if case.protected_phenomenon in {"proper_name", "place_name"}
    ]

    assert len(protected_names) == 20
    assert all(case.entity_ids for case in protected_names)
    assert all(case.entity_spans for case in protected_names)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda raw: raw.update(extra=True), "schema-v3 fields"),
        (lambda raw: raw["cases"][0].update(unit="paragraph"), "unit"),
        (
            lambda raw: raw["cases"][0]["edits"][0].update(start=999),
            "range",
        ),
        (
            lambda raw: raw["cases"][0].update(expected_output="Niepoprawne."),
            "reconstruct",
        ),
        (
            lambda raw: raw["cases"][180].update(review={}),
            "case review.*schema-v3 fields",
        ),
        (
            lambda raw: raw["cases"][0].update(
                review={
                    "status": "pending-human-review",
                    "reviewer": None,
                    "reviewed_at": None,
                    "checklist_version": "safety-corpus-review-v1",
                }
            ),
            "unapproved",
        ),
    ],
)
def test_invalid_candidate_states_are_rejected(mutation: Any, message: str) -> None:
    raw = _raw_corpus()
    mutation(raw)

    with pytest.raises(ValueError, match=message):
        validate_safety_corpus(raw)
