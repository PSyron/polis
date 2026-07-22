#!/usr/bin/env python3
"""Generate the reviewable issue #114 safety-corpus candidate fixtures."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from polis.evaluation.correction_corpus import (
    EntitySpan,
    IsolationRecord,
    derive_normalized_template,
    load_correction_corpus_json,
)
from polis.evaluation.safety_corpus import (
    CORPUS_ID,
    REVIEW_CHECKLIST_VERSION,
    SAFETY_CONTROLLED_ENTITY_SURFACES,
    SAFETY_ENTITY_ID_OVERRIDES,
    assert_no_cross_corpus_leakage,
    safety_corpus_digest,
    validate_safety_corpus,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "tests" / "fixtures" / "evaluation"
JSON_PATH = OUTPUT_DIR / "polish_correction_safety_corpus_v1.json"
XML_PATH = OUTPUT_DIR / "polish_correction_safety_corpus_v1.xml"
APPROVAL_MANIFEST_PATH = OUTPUT_DIR / "polish_correction_safety_corpus_v1.approval.json"
CORPUS_V3_PATH = OUTPUT_DIR / "polish_correction_corpus_v3.json"
FINETUNING_DIR = ROOT / "data" / "finetuning" / "bielik_1_5b_v1"
E2E_JSON_PATH = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.json"
E2E_XML_PATH = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.xml"
FROZEN_DIGEST = "2fc05cd5552071ade7b392b3075d15bfaf57cf3f4b84df450c605b48d1615982"

PROVENANCE = {
    "source": "Polis project-authored synthetic sentence",
    "license": "CC0-1.0",
    "created": "2026-07-22",
    "method": "Explicit issue #114 safety-corpus candidate specification",
    "notes": "Synthetic issue #114 candidate; review state is recorded separately.",
}


@dataclass(frozen=True)
class CaseSpec:
    input: str
    expected: str
    description: str
    tags: tuple[str, ...]
    protected: str | None = None


def _replacement_specs(
    frames: tuple[str, ...],
    rows: tuple[tuple[str, str, str], ...],
    *,
    description: str,
    tags: tuple[str, ...],
) -> list[CaseSpec]:
    specs: list[CaseSpec] = []
    for frame, (context, wrong, correct) in zip(frames, rows, strict=True):
        source = frame.format(context=context, form=wrong)
        target = frame.format(context=context, form=correct)
        specs.append(
            CaseSpec(
                input=source,
                expected=target,
                description=description.format(wrong=wrong, correct=correct),
                tags=tags,
            )
        )
    return specs


def _explicit_specs(
    pairs: tuple[tuple[str, str], ...],
    *,
    description: str,
    tags: tuple[str, ...],
) -> list[CaseSpec]:
    return [
        CaseSpec(
            input=source,
            expected=target,
            description=description,
            tags=tags,
        )
        for source, target in pairs
    ]


def _inflection_specs() -> list[CaseSpec]:
    frames = (
        "Podczas odprawy magazynier odłożył {form} {context} na boczny regał.",
        "Po naradzie sekretarz przekazał {form} {context} do głównego archiwum.",
        "Przed kontrolą technik oznaczył {form} {context} czerwoną etykietą.",
        "W trakcie dyżuru bibliotekarz znalazł {form} {context} pod ladą.",
        "Po remoncie kustosz przeniósł {form} {context} do zachodniej sali.",
        "Wieczorem dyspozytor wysłał {form} {context} do zespołu terenowego.",
        "Przed wyjazdem opiekun spakował {form} {context} do szarej torby.",
        "Po próbie realizator schował {form} {context} w zamkniętej szafie.",
        "Podczas inwentaryzacji księgowy odnalazł {form} {context} w starej teczce.",
        "Po spotkaniu koordynator zaniósł {form} {context} do pokoju narad.",
    )
    groups = (
        (
            (
                ("książkę", "ten", "tę"),
                ("instrukcję", "ten", "tę"),
                ("przesyłkę", "ten", "tę"),
                ("mapę", "ten", "tę"),
                ("makietę", "ten", "tę"),
                ("wiadomość", "ten", "tę"),
                ("latarkę", "ten", "tę"),
                ("partyturę", "ten", "tę"),
                ("fakturę", "ten", "tę"),
                ("notatkę", "ten", "tę"),
            ),
            "Replaces masculine demonstrative “{wrong}” with feminine "
            "accusative “{correct}”.",
            ("inflection", "agreement", "demonstrative"),
        ),
        (
            (
                ("skrzynię", "ciężki", "ciężką"),
                ("kopertę", "brązowy", "brązową"),
                ("walizkę", "podręczny", "podręczną"),
                ("rzeźbę", "kamienny", "kamienną"),
                ("paczkę", "niewielki", "niewielką"),
                ("depeszę", "pilny", "pilną"),
                ("pelerynę", "przeciwdeszczowy", "przeciwdeszczową"),
                ("dekorację", "sceniczny", "sceniczną"),
                ("umowę", "podpisany", "podpisaną"),
                ("agendę", "szczegółowy", "szczegółową"),
            ),
            "Corrects adjective agreement from “{wrong}” to “{correct}”.",
            ("inflection", "agreement", "adjective"),
        ),
        (
            (
                ("projektowi", "nowy", "nowemu"),
                ("regulaminowi", "wewnętrzny", "wewnętrznemu"),
                ("urządzeniu", "pomiarowy", "pomiarowemu"),
                ("obrazowi", "odnowiony", "odnowionemu"),
                ("raportowi", "kwartalny", "kwartalnemu"),
                ("wnioskowi", "formalny", "formalnemu"),
                ("plecakowi", "turystyczny", "turystycznemu"),
                ("mikrofonowi", "bezprzewodowy", "bezprzewodowemu"),
                ("bilansowi", "roczny", "rocznemu"),
                ("harmonogramowi", "roboczy", "roboczemu"),
            ),
            "Corrects dative adjective inflection from “{wrong}” to “{correct}”.",
            ("inflection", "case", "dative"),
        ),
        (
            (
                ("budynku", "wysokiego", "wysokim"),
                ("magazynie", "chłodnego", "chłodnym"),
                ("laboratorium", "nowoczesnego", "nowoczesnym"),
                ("muzeum", "miejskiego", "miejskim"),
                ("oddziale", "ratunkowego", "ratunkowym"),
                ("terminalu", "północnego", "północnym"),
                ("schronisku", "górskiego", "górskim"),
                ("studiu", "nagraniowego", "nagraniowym"),
                ("biurze", "regionalnego", "regionalnym"),
                ("ośrodku", "szkoleniowego", "szkoleniowym"),
            ),
            "Corrects locative adjective inflection from “{wrong}” to “{correct}”.",
            ("inflection", "case", "locative"),
        ),
        (
            (
                ("skrzynką", "mała", "małą"),
                ("pieczęcią", "urzędowa", "urzędową"),
                ("sondą", "ręczna", "ręczną"),
                ("ramą", "drewniana", "drewnianą"),
                ("wagą", "precyzyjna", "precyzyjną"),
                ("anteną", "kierunkowa", "kierunkową"),
                ("liną", "asekuracyjna", "asekuracyjną"),
                ("kamerą", "studyjna", "studyjną"),
                ("tabelą", "zbiorcza", "zbiorczą"),
                ("listą", "kontrolna", "kontrolną"),
            ),
            "Corrects instrumental adjective inflection from “{wrong}” to “{correct}”.",
            ("inflection", "case", "instrumental"),
        ),
        (
            (
                ("lampy", "dwa", "dwie"),
                ("kopie", "dwa", "dwie"),
                ("próbki", "dwa", "dwie"),
                ("gabloty", "dwa", "dwie"),
                ("palety", "dwa", "dwie"),
                ("radiostacje", "dwa", "dwie"),
                ("karimaty", "dwa", "dwie"),
                ("kolumny", "dwa", "dwie"),
                ("deklaracje", "dwa", "dwie"),
                ("tablice", "dwa", "dwie"),
            ),
            "Corrects numeral agreement from “{wrong}” to feminine “{correct}”.",
            ("inflection", "agreement", "numeral"),
        ),
    )
    specs: list[CaseSpec] = []
    for rows, description, tags in groups:
        specs.extend(
            _replacement_specs(frames, rows, description=description, tags=tags)
        )
    reviewed_pairs = (
        (
            "Podczas odprawy przyglądano się nowy projektowi remontu.",
            "Podczas odprawy przyglądano się nowemu projektowi remontu.",
        ),
        (
            "Po naradzie sekretarz poświęcił uwagę wewnętrzny regulaminowi archiwum.",
            "Po naradzie sekretarz poświęcił uwagę wewnętrznemu regulaminowi archiwum.",
        ),
        (
            "Przed kontrolą technik przyjrzał się pomiarowy urządzeniu zapasowemu.",
            "Przed kontrolą technik przyjrzał się pomiarowemu urządzeniu zapasowemu.",
        ),
        (
            "W trakcie dyżuru bibliotekarz przyglądał się odnowiony obrazowi "
            "w czytelni.",
            "W trakcie dyżuru bibliotekarz przyglądał się odnowionemu obrazowi "
            "w czytelni.",
        ),
        (
            "Po remoncie kustosz poświęcił uwagę kwartalny raportowi "
            "konserwatorskiemu.",
            "Po remoncie kustosz poświęcił uwagę kwartalnemu raportowi "
            "konserwatorskiemu.",
        ),
        (
            "Wieczorem dyspozytor przyjrzał się formalny wnioskowi przewoźnika.",
            "Wieczorem dyspozytor przyjrzał się formalnemu wnioskowi przewoźnika.",
        ),
        (
            "Przed wyjazdem opiekun przyglądał się turystyczny plecakowi uczestnika.",
            "Przed wyjazdem opiekun przyglądał się turystycznemu plecakowi uczestnika.",
        ),
        (
            "Po próbie realizator poświęcił uwagę bezprzewodowy mikrofonowi solisty.",
            "Po próbie realizator poświęcił uwagę bezprzewodowemu mikrofonowi solisty.",
        ),
        (
            "Podczas inwentaryzacji księgowy przyjrzał się roczny bilansowi fundacji.",
            "Podczas inwentaryzacji księgowy przyjrzał się rocznemu bilansowi "
            "fundacji.",
        ),
        (
            "Po spotkaniu koordynator poświęcił uwagę roboczy harmonogramowi odbiorów.",
            "Po spotkaniu koordynator poświęcił uwagę roboczemu harmonogramowi "
            "odbiorów.",
        ),
        (
            "Podczas odprawy rozmawiano o wysokiego budynku dworca.",
            "Podczas odprawy rozmawiano o wysokim budynku dworca.",
        ),
        (
            "Po naradzie sekretarz czekał w chłodnego magazynie archiwum.",
            "Po naradzie sekretarz czekał w chłodnym magazynie archiwum.",
        ),
        (
            "Przed kontrolą technik pracował w nowoczesnego laboratorium pomiarowym.",
            "Przed kontrolą technik pracował w nowoczesnym laboratorium pomiarowym.",
        ),
        (
            "W trakcie dyżuru bibliotekarz był w miejskiego muzeum techniki.",
            "W trakcie dyżuru bibliotekarz był w miejskim muzeum techniki.",
        ),
        (
            "Po remoncie ratownik pracował na ratunkowego oddziale szpitala.",
            "Po remoncie ratownik pracował na ratunkowym oddziale szpitala.",
        ),
        (
            "Wieczorem dyspozytor czekał w północnego terminalu lotniska.",
            "Wieczorem dyspozytor czekał w północnym terminalu lotniska.",
        ),
        (
            "Przed wyjazdem opiekun nocował w górskiego schronisku turystycznym.",
            "Przed wyjazdem opiekun nocował w górskim schronisku turystycznym.",
        ),
        (
            "Po próbie realizator pracował w nagraniowego studiu radiowym.",
            "Po próbie realizator pracował w nagraniowym studiu radiowym.",
        ),
        (
            "Podczas inwentaryzacji księgowy został w regionalnego biurze fundacji.",
            "Podczas inwentaryzacji księgowy został w regionalnym biurze fundacji.",
        ),
        (
            "Po spotkaniu koordynator czekał w szkoleniowego ośrodku branżowym.",
            "Po spotkaniu koordynator czekał w szkoleniowym ośrodku branżowym.",
        ),
        (
            "Podczas odprawy magazynier przyszedł z mała skrzynką narzędziową.",
            "Podczas odprawy magazynier przyszedł z małą skrzynką narzędziową.",
        ),
        (
            "Po naradzie sekretarz opatrzył dokument urzędowa pieczęcią.",
            "Po naradzie sekretarz opatrzył dokument urzędową pieczęcią.",
        ),
        (
            "Przed kontrolą technik wykonał pomiar ręczna sondą.",
            "Przed kontrolą technik wykonał pomiar ręczną sondą.",
        ),
        (
            "W trakcie dyżuru bibliotekarz przeniósł obraz z drewniana ramą.",
            "W trakcie dyżuru bibliotekarz przeniósł obraz z drewnianą ramą.",
        ),
        (
            "Po remoncie kustosz posłużył się precyzyjna wagą jubilerską.",
            "Po remoncie kustosz posłużył się precyzyjną wagą jubilerską.",
        ),
        (
            "Wieczorem dyspozytor pracował z kierunkowa anteną radiową.",
            "Wieczorem dyspozytor pracował z kierunkową anteną radiową.",
        ),
        (
            "Przed wyjazdem opiekun zabezpieczył ładunek asekuracyjna liną.",
            "Przed wyjazdem opiekun zabezpieczył ładunek asekuracyjną liną.",
        ),
        (
            "Po próbie realizator posłużył się studyjna kamerą cyfrową.",
            "Po próbie realizator posłużył się studyjną kamerą cyfrową.",
        ),
        (
            "Podczas inwentaryzacji księgowy pracował ze zbiorcza tabelą kosztów.",
            "Podczas inwentaryzacji księgowy pracował ze zbiorczą tabelą kosztów.",
        ),
        (
            "Po spotkaniu koordynator posłużył się kontrolna listą odbiorową.",
            "Po spotkaniu koordynator posłużył się kontrolną listą odbiorową.",
        ),
    )
    specs[20:50] = _explicit_specs(
        reviewed_pairs,
        description=(
            "Corrects the reviewed case inflection while preserving grammatical "
            "government."
        ),
        tags=("inflection", "case", "owner_review_regression"),
    )
    return specs


def _syntax_specs() -> list[CaseSpec]:
    frames = (
        "Po porannym spotkaniu {context} {form} komplet dokumentów do kancelarii.",
        "W czasie nocnej zmiany {context} {form} wynik pomiaru w dzienniku.",
        "Przed końcem tygodnia {context} {form} szczegółowy plan naprawy.",
        "Po analizie zgłoszeń {context} {form} wspólne stanowisko dla zarządu.",
        "W trakcie próby generalnej {context} {form} wszystkie uwagi realizatora.",
        "Po zamknięciu magazynu {context} {form} brakujące pozycje w wykazie.",
        "Przed rozpoczęciem wyprawy {context} {form} trasę na papierowej mapie.",
        "Po zakończeniu nagrania {context} {form} pliki w bezpiecznym katalogu.",
        "W ostatnim dniu miesiąca {context} {form} koszty w raporcie zbiorczym.",
        "Po konsultacji roboczej {context} {form} terminy kolejnych odbiorów.",
    )
    groups = (
        (
            (
                ("zespół logistyczny", "przekazali", "przekazał"),
                ("personel laboratorium", "zapisali", "zapisał"),
                ("komitet techniczny", "przygotowali", "przygotował"),
                ("zarząd fundacji", "uzgodnili", "uzgodnił"),
                ("chór kameralny", "omówili", "omówił"),
                ("dział ewidencji", "odnotowali", "odnotował"),
                ("sztab wyprawy", "wyznaczyli", "wyznaczył"),
                ("zespół montażowy", "zapisali", "zapisał"),
                ("pion finansowy", "podsumowali", "podsumował"),
                ("sekretariat programu", "potwierdzili", "potwierdził"),
            ),
            "Corrects singular collective-subject agreement from “{wrong}” "
            "to “{correct}”.",
            ("syntax", "agreement", "collective_subject"),
        ),
        (
            (
                ("seria kontroli", "wykazały", "wykazała"),
                ("lista odczytów", "zawierały", "zawierała"),
                ("kolekcja szkiców", "obejmowały", "obejmowała"),
                ("większość uczestników", "poparli", "poparła"),
                ("część dekoracji", "wymagały", "wymagała"),
                ("ewidencja przesyłek", "ujawniły", "ujawniła"),
                ("grupa ratowników", "wybrali", "wybrała"),
                ("biblioteka nagrań", "zajmowały", "zajmowała"),
                ("suma wydatków", "przekroczyły", "przekroczyła"),
                ("większość wykonawców", "zaakceptowali", "zaakceptowała"),
            ),
            "Corrects agreement with a singular quantifying subject from "
            "“{wrong}” to “{correct}”.",
            ("syntax", "agreement", "quantifying_subject"),
        ),
        (
            (
                ("każdy z kurierów", "dostarczyli", "dostarczył"),
                ("każdy z analityków", "sprawdzili", "sprawdził"),
                ("każdy z inspektorów", "opisali", "opisał"),
                ("każdy z członków rady", "przedstawili", "przedstawił"),
                ("każdy z muzyków", "zapisali", "zapisał"),
                ("każdy z magazynierów", "oznaczyli", "oznaczył"),
                ("każdy z przewodników", "narysowali", "narysował"),
                ("każdy z montażystów", "skopiowali", "skopiował"),
                ("każdy z księgowych", "obliczyli", "obliczył"),
                ("każdy z koordynatorów", "ustalili", "ustalił"),
            ),
            "Corrects agreement with singular “każdy” from “{wrong}” to “{correct}”.",
            ("syntax", "agreement", "distributive_subject"),
        ),
        (
            (
                ("żaden z pełnomocników", "nie podpisali", "nie podpisał"),
                ("żaden z techników", "nie wpisali", "nie wpisał"),
                ("żaden z projektantów", "nie dołączyli", "nie dołączył"),
                ("żaden z delegatów", "nie zgłosili", "nie zgłosił"),
                ("żaden z aktorów", "nie pominęli", "nie pominął"),
                ("żaden z kontrolerów", "nie zauważyli", "nie zauważył"),
                ("żaden z pilotów", "nie zmienili", "nie zmienił"),
                ("żaden z realizatorów", "nie usunęli", "nie usunął"),
                ("żaden z audytorów", "nie zakwestionowali", "nie zakwestionował"),
                ("żaden z dostawców", "nie przesunęli", "nie przesunął"),
            ),
            "Corrects agreement with singular “żaden” from “{wrong}” to “{correct}”.",
            ("syntax", "agreement", "negative_subject"),
        ),
        (
            (
                ("para praktykantów", "zanieśli", "zaniosła"),
                ("para badaczy", "odczytali", "odczytała"),
                ("para kreślarzy", "naszkicowali", "naszkicowała"),
                ("para mediatorów", "sformułowali", "sformułowała"),
                ("para inspicjentów", "spisali", "spisała"),
                ("para pracowników", "policzyli", "policzyła"),
                ("para zwiadowców", "zaznaczyli", "zaznaczyła"),
                ("para dźwiękowców", "zarchiwizowali", "zarchiwizowała"),
                ("para kontrolerów", "zestawili", "zestawiła"),
                ("para planistów", "wyznaczyli", "wyznaczyła"),
            ),
            "Corrects agreement with singular “para” from “{wrong}” to “{correct}”.",
            ("syntax", "agreement", "pair_subject"),
        ),
        (
            (
                ("rada programowa", "zatwierdzili", "zatwierdziła"),
                ("obsługa stacji", "zanotowali", "zanotowała"),
                ("pracownia wzornicza", "opracowali", "opracowała"),
                ("kapituła konkursu", "ogłosili", "ogłosiła"),
                ("orkiestra festiwalowa", "uwzględnili", "uwzględniła"),
                ("komisja spisowa", "wskazali", "wskazała"),
                ("ekipa poszukiwawcza", "wytyczyli", "wytyczyła"),
                ("redakcja dźwiękowa", "uporządkowali", "uporządkowała"),
                ("jednostka rozliczeniowa", "ujęli", "ujęła"),
                ("grupa odbiorowa", "wyznaczyli", "wyznaczyła"),
            ),
            "Corrects feminine singular subject agreement from “{wrong}” "
            "to “{correct}”.",
            ("syntax", "agreement", "feminine_subject"),
        ),
    )
    specs: list[CaseSpec] = []
    for rows, description, tags in groups:
        specs.extend(
            _replacement_specs(frames, rows, description=description, tags=tags)
        )
    specs[14] = _explicit_specs(
        (
            (
                "Część dekoracji wymagały pilnej naprawy.",
                "Część dekoracji wymagała pilnej naprawy.",
            ),
        ),
        description="Corrects agreement with the singular quantifying subject “część”.",
        tags=("syntax", "agreement", "quantifying_subject"),
    )[0]
    specs[17] = _explicit_specs(
        (
            (
                "Biblioteka nagrań zajmowały trzy regały.",
                "Biblioteka nagrań zajmowała trzy regały.",
            ),
        ),
        description=(
            "Corrects singular subject agreement without changing the complement."
        ),
        tags=("syntax", "agreement", "quantifying_subject"),
    )[0]
    negative_pairs = (
        (
            "Żaden z pełnomocników nie podpisali kompletu dokumentów.",
            "Żaden z pełnomocników nie podpisał kompletu dokumentów.",
        ),
        (
            "Żaden z techników nie wpisali wyniku pomiaru.",
            "Żaden z techników nie wpisał wyniku pomiaru.",
        ),
        (
            "Żaden z projektantów nie dołączyli szczegółowego planu naprawy.",
            "Żaden z projektantów nie dołączył szczegółowego planu naprawy.",
        ),
        (
            "Żaden z delegatów nie zgłosili wspólnego stanowiska.",
            "Żaden z delegatów nie zgłosił wspólnego stanowiska.",
        ),
        (
            "Żaden z aktorów nie pominęli uwag realizatora.",
            "Żaden z aktorów nie pominął uwag realizatora.",
        ),
        (
            "Żaden z kontrolerów nie zauważyli brakujących pozycji.",
            "Żaden z kontrolerów nie zauważył brakujących pozycji.",
        ),
        (
            "Żaden z pilotów nie zmienili trasy na mapie.",
            "Żaden z pilotów nie zmienił trasy na mapie.",
        ),
        (
            "Żaden z realizatorów nie usunęli plików z katalogu.",
            "Żaden z realizatorów nie usunął plików z katalogu.",
        ),
        (
            "Żaden z audytorów nie zakwestionowali kosztów ujętych w raporcie.",
            "Żaden z audytorów nie zakwestionował kosztów ujętych w raporcie.",
        ),
        (
            "Żaden z dostawców nie przesunęli terminów kolejnych odbiorów.",
            "Żaden z dostawców nie przesunął terminów kolejnych odbiorów.",
        ),
    )
    specs[30:40] = _explicit_specs(
        negative_pairs,
        description=(
            "Corrects agreement with singular “żaden” while preserving genitive "
            "government."
        ),
        tags=("syntax", "agreement", "negative_subject"),
    )
    return specs


def _punctuation_specs() -> list[CaseSpec]:
    groups = (
        (
            "Dyspozytor potwierdził że {context}.",
            "Dyspozytor potwierdził, że {context}.",
            (
                "pociąg techniczny opuścił bocznicę",
                "próbki dotarły do laboratorium",
                "kurier odebrał zaplombowaną paczkę",
                "konserwator zamknął zachodnią galerię",
                "zapas paliwa wystarczy do rana",
                "antena działa po ostatniej regulacji",
                "schronisko przyjmie całą grupę",
                "nagranie trafiło do bezpiecznego archiwum",
                "przelew został prawidłowo zaksięgowany",
                "wykonawca zaakceptował nowy termin",
            ),
            "Inserts the required comma before a subordinate clause "
            "introduced by “że”.",
            ("punctuation", "subordinate_clause", "ze"),
        ),
        (
            "{context} gdy zakończy się zaplanowana kontrola.",
            "{context}, gdy zakończy się zaplanowana kontrola.",
            (
                "Skład opuści halę",
                "Aparatura wróci do magazynu",
                "Przesyłka pojedzie dalej",
                "Zwiedzający wejdą do sali",
                "Agregat zostanie wyłączony",
                "Ratownicy zejdą ze szlaku",
                "Miksery trafią do skrzyń",
                "Bilans zostanie opublikowany",
                "Podpiszemy protokół",
                "Zespół odbierze instalację",
            ),
            "Inserts the required comma before a subordinate clause "
            "introduced by “gdy”.",
            ("punctuation", "subordinate_clause", "gdy"),
        ),
        (
            "Chociaż {context} prace zakończono zgodnie z harmonogramem.",
            "Chociaż {context}, prace zakończono zgodnie z harmonogramem.",
            (
                "padał marznący deszcz",
                "czujnik zgłaszał chwilowe błędy",
                "dostawa przyjechała późnym wieczorem",
                "winda była czasowo wyłączona",
                "temperatura spadła poniżej zera",
                "szlak pokrywała mokra mgła",
                "próba zaczęła się z opóźnieniem",
                "system księgowy działał wolniej",
                "część dokumentów wymagała uzupełnienia",
                "odbiór trwał dłużej niż planowano",
            ),
            "Inserts the required comma after the initial concessive clause.",
            ("punctuation", "subordinate_clause", "chociaz"),
        ),
        (
            "{context} sprawdź proszę końcowy zapis w protokole.",
            "{context}, sprawdź proszę końcowy zapis w protokole.",
            (
                "Drogi magazynierze",
                "Szanowna laborantko",
                "Uważny kurierze",
                "Panie kustoszu",
                "Droga dyspozytorko",
                "Doświadczony przewodniku",
                "Szanowna realizatorko",
                "Panie księgowy",
                "Droga koordynatorko",
                "Szanowny inspektorze",
            ),
            "Separates the initial vocative with the required comma.",
            ("punctuation", "vocative"),
        ),
        (
            "Raport {context} wymaga jeszcze krótkiego uzupełnienia.",
            "Raport, {context}, wymaga jeszcze krótkiego uzupełnienia.",
            (
                "moim zdaniem",
                "jak ocenił zespół",
                "jak sądzę",
                "co istotne",
                "jak zauważył dyspozytor",
                "jak podkreślił przewodnik",
                "co wspólnie ustaliliśmy",
                "jak wynika z bilansu",
                "jak ocenił koordynator",
                "co warto podkreślić",
            ),
            "Encloses a parenthetical expression with commas.",
            ("punctuation", "parenthetical"),
        ),
        (
            "Odnaleziono {context} który wcześniej uznano za zaginiony.",
            "Odnaleziono {context}, który wcześniej uznano za zaginiony.",
            (
                "wagon pomiarowy",
                "zeszyt laboratoryjny",
                "pakunek kurierski",
                "szkic konserwatorski",
                "radiotelefon zapasowy",
                "kompas wyprawowy",
                "mikrofon sceniczny",
                "rejestr kosztów",
                "aneks wykonawczy",
                "protokół odbiorowy",
            ),
            "Inserts the required comma before a relative clause.",
            ("punctuation", "relative_clause"),
        ),
    )
    specs: list[CaseSpec] = []
    for source_frame, target_frame, contexts, description, tags in groups:
        for context in contexts:
            specs.append(
                CaseSpec(
                    input=source_frame.format(context=context),
                    expected=target_frame.format(context=context),
                    description=description,
                    tags=tags,
                )
            )
    return specs


def _hard_negative_specs() -> list[CaseSpec]:
    groups: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "decimal_comma",
            (
                "Pomiar wyniósł 18,75 milimetra.",
                "Próbka ważyła 2,48 grama.",
                "Paczka miała masę 7,30 kilograma.",
                "Wilgotność osiągnęła 63,5 procent.",
                "Napięcie spadło do 11,8 wolta.",
                "Trasa liczyła 24,6 kilometra.",
                "Nagranie trwało 3,25 minuty.",
                "Koszt wzrósł o 9,40 zł.",
                "Odchylenie wyniosło 0,17 punktu.",
                "Szczelina miała 4,05 centymetra.",
            ),
        ),
        (
            "url",
            (
                "Po nocnym przeglądzie maszynista odnalazł instrukcję techniczną "
                "pod adresem https://kolej.example.org/pomiary.",
                "Wyniki zapisano na stronie https://lab.example.net/raporty.",
                "Kurier sprawdził status na https://paczki.example.com/status.",
                "Katalog muzeum działa pod https://zbiory.example.org/start.",
                "Komunikat widnieje na https://radio.example.net/alerty.",
                "Mapę pobrano z https://szlaki.example.com/mapa.",
                "Program koncertu jest na https://scena.example.org/program.",
                "Bilans opublikowano pod https://finanse.example.net/wyniki.",
                "Formularz znajduje się na https://budowa.example.com/odbior.",
                "Terminy podano pod https://projekt.example.org/kalendarz.",
            ),
        ),
        (
            "quotation",
            (
                "Na tablicy zapisano „tor zamknięty”.",
                "Etykieta zawiera napis „próbka kontrolna”.",
                "Na paczce widniało „ostrożnie szkło”.",
                "Katalog opisano jako „wydanie robocze”.",
                "Dyspozytor nadał komunikat „kanał wolny”.",
                "Mapa nosi tytuł „Szlak nad potokiem”.",
                "Plik nazwano „wersja koncertowa”.",
                "Arkusz oznaczono jako „bilans pomocniczy”.",
                "Protokół ma status „do podpisu”.",
                "Plan opisano jako „wariant północny”.",
            ),
        ),
        (
            "marked_word_order",
            (
                "Dopiero wieczorem skład dotarł na stację.",
                "Szczególnie dokładnie laborant opisał osad.",
                "Właśnie tę paczkę kurier zostawił w skrytce.",
                "Jedynie zimą galeria pozostaje zamknięta.",
                "Nawet bez anteny odbiornik zapisał sygnał.",
                "Dopiero o świcie grupa ruszyła ze schroniska.",
                "Szczególnie cicho orkiestra zagrała finał.",
                "Właśnie ten wydatek ujęto w aneksie.",
                "Jedynie podpisu brakuje w protokole.",
                "Nawet podczas deszczu ekipa kontynuowała odbiór.",
            ),
        ),
        (
            "proper_name",
            (
                "Artur Pietrzak odebrał klucz do magazynu.",
                "Emil Wasilewski podpisał kartę pomiaru.",
                "Hubert Malinowski nadał przesyłkę priorytetową.",
                "Katarzyna Malicka otworzyła wystawę czasową.",
                "Kinga Wrońska sprawdziła kanał alarmowy.",
                "Krystian Sobieraj prowadził grupę doliną.",
                "Magdalena Cieślak przygotowała próbę dźwięku.",
                "Natalia Głowacka zatwierdziła bilans miesięczny.",
                "Oliwia Stępień odebrała dokumentację wykonawczą.",
                "Patrycja Żuk ustaliła termin następnej kontroli.",
            ),
        ),
        (
            "place_name",
            (
                "Pociąg techniczny wyruszył z Bydgoszczy.",
                "Laboratorium działa w Katowicach.",
                "Przesyłka dotarła do Kielc przed południem.",
                "Wystawa przyjechała z Lublina.",
                "Nadajnik testowano pod Olsztynem.",
                "Grupa zatrzymała się w Opolu.",
                "Po nocnej odprawie transport techniczny skierowano awaryjnie "
                "do Szczecina.",
                "Dokument wysłano do Łodzi.",
                "Ekipa wróciła z Zakopanego.",
                "Odbiór zaplanowano w Bydgoszczy.",
            ),
        ),
    )
    return [
        CaseSpec(
            input=sentence,
            expected=sentence,
            description=f"Protects correct {phenomenon.replace('_', ' ')} usage.",
            tags=("hard_negative", phenomenon),
            protected=phenomenon,
        )
        for phenomenon, sentences in groups
        for sentence in sentences
    ]


def _single_edit(source: str, target: str, category: str) -> dict[str, object]:
    start = 0
    limit = min(len(source), len(target))
    while start < limit and source[start] == target[start]:
        start += 1
    source_end = len(source)
    target_end = len(target)
    while (
        source_end > start
        and target_end > start
        and source[source_end - 1] == target[target_end - 1]
    ):
        source_end -= 1
        target_end -= 1
    original = source[start:source_end]
    suggestion = target[start:target_end]
    return {
        "category": category,
        "start": start,
        "end": source_end,
        "original": original,
        "suggestion": suggestion,
        "rationale": (
            f"The {category} correction replaces {original!r} with "
            f"{suggestion!r} at Unicode range [{start}, {source_end})."
        ),
    }


def _entity_id(surface: str) -> str:
    override = SAFETY_ENTITY_ID_OVERRIDES.get(surface.casefold())
    if override is not None:
        return cast(str, override)
    import re
    import unicodedata

    value = unicodedata.normalize("NFKD", surface.casefold()).replace("ł", "l")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def _entity_spans(text: str) -> tuple[EntitySpan, ...]:
    found: list[EntitySpan] = []
    occupied: list[tuple[int, int]] = []
    for surface in sorted(SAFETY_CONTROLLED_ENTITY_SURFACES, key=len, reverse=True):
        cursor = 0
        while True:
            start = text.find(surface, cursor)
            if start < 0:
                break
            end = start + len(surface)
            cursor = end
            left_boundary = start == 0 or not text[start - 1].isalpha()
            right_boundary = end == len(text) or not text[end].isalpha()
            overlaps = any(start < right and left < end for left, right in occupied)
            if left_boundary and right_boundary and not overlaps:
                found.append(EntitySpan(start=start, end=end, surface=surface))
                occupied.append((start, end))
    return tuple(sorted(found, key=lambda span: span.start))


def _case(stratum: str, index: int, spec: CaseSpec) -> dict[str, Any]:
    spans = _entity_spans(spec.input)
    edits = (
        []
        if stratum == "hard_negative"
        else [_single_edit(spec.input, spec.expected, stratum)]
    )
    return {
        "id": f"safety_{stratum}_{index:03d}",
        "stratum": stratum,
        "split": "development" if index <= 20 else "holdout",
        "unit": "sentence",
        "input": spec.input,
        "expected_output": spec.expected,
        "description": spec.description,
        "tags": list(spec.tags),
        "normalized_template": derive_normalized_template(spec.input, spans),
        "entity_ids": [_entity_id(span.surface) for span in spans],
        "entity_spans": [
            {"start": span.start, "end": span.end, "surface": span.surface}
            for span in spans
        ],
        "protected_phenomenon": spec.protected,
        "provenance": dict(PROVENANCE),
        "review": {
            "status": "pending-human-review",
            "reviewer": None,
            "reviewed_at": None,
            "checklist_version": REVIEW_CHECKLIST_VERSION,
        },
        "edits": edits,
    }


def build_candidate_corpus() -> dict[str, Any]:
    strata = {
        "inflection": _inflection_specs(),
        "syntax": _syntax_specs(),
        "punctuation": _punctuation_specs(),
        "hard_negative": _hard_negative_specs(),
    }
    if any(len(specs) != 60 for specs in strata.values()):
        raise ValueError("each safety corpus stratum must define exactly 60 cases")
    raw: dict[str, Any] = {
        "schema_version": 3,
        "id": CORPUS_ID,
        "language": "pl-PL",
        "holdout_state": "unfrozen-candidates",
        "provenance": dict(PROVENANCE),
        "review_policy": {
            "candidate_status": "pending-human-review",
            "approval_status": "human-reviewed",
            "required_reviewer": "Paweł Cyroń",
            "checklist_version": REVIEW_CHECKLIST_VERSION,
            "training_use": "prohibited",
        },
        "cases": [
            _case(stratum, index, spec)
            for stratum, specs in strata.items()
            for index, spec in enumerate(specs, 1)
        ],
    }
    validate_safety_corpus(raw)
    return raw


def _load_approval_manifest() -> dict[str, Any]:
    raw: Any = json.loads(APPROVAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("safety corpus approval manifest must be an object")
    required = {
        "corpus_id",
        "approval_scope",
        "approved_case_count",
        "candidate_digest",
        "frozen_digest",
        "reviewer",
        "reviewed_at",
        "checklist_version",
    }
    if set(raw) != required:
        raise ValueError("safety corpus approval manifest has unexpected fields")
    return cast(dict[str, Any], raw)


def build_frozen_corpus() -> dict[str, Any]:
    candidate = build_candidate_corpus()
    approval = _load_approval_manifest()
    expected = {
        "corpus_id": CORPUS_ID,
        "approval_scope": "all-cases",
        "approved_case_count": len(candidate["cases"]),
        "candidate_digest": safety_corpus_digest(candidate),
        "reviewer": "Paweł Cyroń",
        "reviewed_at": "2026-07-22",
        "checklist_version": REVIEW_CHECKLIST_VERSION,
    }
    for key, value in expected.items():
        if approval[key] != value:
            raise RuntimeError(f"invalid safety corpus owner approval field: {key}")

    frozen = deepcopy(candidate)
    frozen["holdout_state"] = "frozen"
    for item in frozen["cases"]:
        item["review"] = {
            "status": "human-reviewed",
            "reviewer": approval["reviewer"],
            "reviewed_at": approval["reviewed_at"],
            "checklist_version": approval["checklist_version"],
        }
    validate_safety_corpus(frozen)
    digest = safety_corpus_digest(frozen)
    if approval["frozen_digest"] != digest or FROZEN_DIGEST != digest:
        raise RuntimeError("frozen safety corpus digest does not match owner approval")
    return frozen


def build_corpus() -> dict[str, Any]:
    """Build the approved fixture; retained as the script's public entry point."""

    return build_frozen_corpus()


def _finetuning_records() -> list[IsolationRecord]:
    records: list[IsolationRecord] = []
    for path in sorted(FINETUNING_DIR.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            raw: Any = json.loads(line)
            spans = tuple(
                EntitySpan(
                    start=span["start"],
                    end=span["end"],
                    surface=span["surface"],
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
    if not records:
        raise RuntimeError("no fine-tuning assets found for leakage validation")
    return records


def _prompt_and_e2e_records() -> list[IsolationRecord]:
    from polis.llm import corrected_text

    e2e_raw: Any = json.loads(E2E_JSON_PATH.read_text(encoding="utf-8"))
    records = [
        IsolationRecord(id=f"e2e-json:{case['id']}", input=case["input"])
        for case in e2e_raw["cases"]
    ]
    records.extend(
        IsolationRecord(
            id=f"e2e-xml:{case.get('id', '')}",
            input=case.findtext("input") or "",
        )
        for case in ET.parse(E2E_XML_PATH).getroot().findall("case")
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
    return records


def validate_reserved_asset_isolation(raw: dict[str, Any]) -> None:
    """Reject leakage from every asset reserved by issue #114 before writing."""

    corpus = validate_safety_corpus(raw)
    corpus_v3 = load_correction_corpus_json(CORPUS_V3_PATH)
    assert_no_cross_corpus_leakage(
        corpus,
        (
            IsolationRecord(
                id=case.id,
                input=case.input,
                entity_spans=case.entity_spans,
            )
            for case in corpus_v3.cases
        ),
        source="corpus-v3",
    )
    assert_no_cross_corpus_leakage(
        corpus,
        _finetuning_records(),
        source="finetuning",
    )
    assert_no_cross_corpus_leakage(
        corpus,
        _prompt_and_e2e_records(),
        source="prompt-e2e",
    )


def _write_xml(raw: dict[str, Any]) -> None:
    root = ET.Element(
        "corpus",
        schema_version=str(raw["schema_version"]),
        id=str(raw["id"]),
        language=str(raw["language"]),
        holdout_state=str(raw["holdout_state"]),
    )
    ET.SubElement(root, "provenance", **raw["provenance"])
    ET.SubElement(root, "review_policy", **raw["review_policy"])
    cases_node = ET.SubElement(root, "cases")
    for item in raw["cases"]:
        case_node = ET.SubElement(
            cases_node,
            "case",
            id=item["id"],
            stratum=item["stratum"],
            split=item["split"],
            unit=item["unit"],
            protected_phenomenon=item["protected_phenomenon"] or "",
        )
        for key in ("input", "expected_output", "description", "normalized_template"):
            ET.SubElement(case_node, key).text = item[key]
        tags = ET.SubElement(case_node, "tags")
        for tag in item["tags"]:
            ET.SubElement(tags, "tag").text = tag
        entity_ids = ET.SubElement(case_node, "entity_ids")
        for entity_id in item["entity_ids"]:
            ET.SubElement(entity_ids, "entity").text = entity_id
        entity_spans = ET.SubElement(case_node, "entity_spans")
        for span in item["entity_spans"]:
            ET.SubElement(
                entity_spans,
                "entity",
                start=str(span["start"]),
                end=str(span["end"]),
                surface=span["surface"],
            )
        ET.SubElement(case_node, "provenance", **item["provenance"])
        review = dict(item["review"])
        review["reviewer"] = review["reviewer"] or ""
        review["reviewed_at"] = review["reviewed_at"] or ""
        ET.SubElement(case_node, "review", **review)
        edits = ET.SubElement(case_node, "edits")
        for edit in item["edits"]:
            ET.SubElement(
                edits,
                "edit",
                category=edit["category"],
                start=str(edit["start"]),
                end=str(edit["end"]),
                original=edit["original"],
                suggestion=edit["suggestion"],
                rationale=edit["rationale"],
            )
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(XML_PATH, encoding="utf-8", xml_declaration=True)


def main() -> None:
    raw = build_corpus()
    digest = safety_corpus_digest(raw)
    if digest != FROZEN_DIGEST:
        raise RuntimeError(
            "frozen safety corpus content changed; create a new corpus version "
            "and complete owner review before generating fixtures"
        )
    validate_reserved_asset_isolation(raw)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_xml(raw)


if __name__ == "__main__":
    main()
