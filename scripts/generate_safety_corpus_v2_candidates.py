#!/usr/bin/env python3
"""Generate approved frozen issue #119 sentence-safety corpus v2 fixtures."""

from __future__ import annotations

import json
import re
import unicodedata
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
    CORPUS_V2_ID,
    REVIEW_CHECKLIST_V2_VERSION,
    SAFETY_V2_CONTROLLED_ENTITY_SURFACES,
    V2_APPROVAL_REVIEW_BASIS,
    V2_APPROVED_CANDIDATE_DIGEST,
    V2_APPROVED_FROZEN_DIGEST,
    V2_APPROVED_REVIEW_DATE,
    V2_REQUIRED_REVIEWER,
    assert_no_cross_corpus_leakage,
    load_safety_corpus_json,
    safety_corpus_digest,
    validate_safety_corpus,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "tests" / "fixtures" / "evaluation"
JSON_PATH = OUTPUT_DIR / "polish_correction_safety_corpus_v2.json"
XML_PATH = OUTPUT_DIR / "polish_correction_safety_corpus_v2.xml"
APPROVAL_MANIFEST_PATH = OUTPUT_DIR / "polish_correction_safety_corpus_v2.approval.json"
CORPUS_V3_PATH = OUTPUT_DIR / "polish_correction_corpus_v3.json"
SAFETY_V1_PATH = OUTPUT_DIR / "polish_correction_safety_corpus_v1.json"
FINETUNING_DIR = ROOT / "data" / "finetuning" / "bielik_1_5b_v1"
E2E_JSON_PATH = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.json"
E2E_XML_PATH = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.xml"

PROVENANCE = {
    "source": "Polis project-authored synthetic sentence",
    "license": "CC0-1.0",
    "created": "2026-07-23",
    "method": "Explicit issue #119 sentence-safety corpus v2 specification",
    "notes": "Synthetic v2 candidate; owner review is not automated.",
}


@dataclass(frozen=True)
class CaseSpec:
    input: str
    expected: str
    description: str
    tags: tuple[str, ...]
    protected: str | None = None


def _replacement_group(
    frames: tuple[str, ...],
    rows: tuple[tuple[str, str, str], ...],
    *,
    description: str,
    tags: tuple[str, ...],
) -> list[CaseSpec]:
    return [
        CaseSpec(
            input=frame.format(context=context, form=wrong),
            expected=frame.format(context=context, form=correct),
            description=description.format(wrong=wrong, correct=correct),
            tags=tags,
        )
        for frame, (context, wrong, correct) in zip(frames, rows, strict=True)
    ]


def _pair_group(
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
        "Po nocnym dyżurze operator odłożył {form} {context} obok panelu.",
        "Przed odprawą redaktor zaznaczył {form} {context} w roboczym spisie.",
        "W południe instruktorka pokazała {form} {context} całej grupie.",
        "Po przeglądzie mechanik zabezpieczył {form} {context} miękkim pokrowcem.",
        "Pod koniec zmiany archiwistka opisała {form} {context} nową sygnaturą.",
        "Przed wysyłką laborant sprawdził {form} {context} pod lampą.",
        "Po ćwiczeniu ratownik schował {form} {context} w bocznej kieszeni.",
        "Wieczorem scenograf przeniósł {form} {context} za kulisy.",
        "W trakcie audytu specjalistka odnalazła {form} {context} w segregatorze.",
        "Po konsultacji projektant poprawił {form} {context} zgodnie z uwagami.",
    )
    specs: list[CaseSpec] = []
    specs.extend(
        _replacement_group(
            frames,
            (
                ("kartę dostępu", "ten", "tę"),
                ("rubrykę kosztową", "ten", "tę"),
                ("planszę szkoleniową", "ten", "tę"),
                ("osłonę przekładni", "ten", "tę"),
                ("metrykę zbioru", "ten", "tę"),
                ("próbkę kontrolną", "ten", "tę"),
                ("apteczkę podróżną", "ten", "tę"),
                ("kurtynę sceniczną", "ten", "tę"),
                ("deklarację zgodności", "ten", "tę"),
                ("wersję makiety", "ten", "tę"),
            ),
            description=(
                "Replaces masculine demonstrative “{wrong}” with feminine "
                "accusative “{correct}”."
            ),
            tags=("inflection", "agreement", "demonstrative"),
        )
    )
    specs.extend(
        _replacement_group(
            (
                "Na pulpicie przez cały ranek leżało {form} {context}.",
                "W zestawie demonstracyjnym znajdowało się {form} {context}.",
                "Obok wejścia wisiało {form} {context}.",
                "W magazynie pozostało {form} {context}.",
                "Na końcu korytarza działało {form} {context}.",
                "Pod osłoną pracowało {form} {context}.",
                "W gablocie było widoczne {form} {context}.",
                "W skrzyni transportowej spoczywało {form} {context}.",
                "Na stanowisku testowym stało {form} {context}.",
                "W dokumentacji widniało {form} {context}.",
            ),
            (
                ("radio awaryjne", "ta", "to"),
                ("lustro sygnałowe", "ta", "to"),
                ("godło zakładowe", "ta", "to"),
                ("pudło montażowe", "ta", "to"),
                ("światło ostrzegawcze", "ta", "to"),
                ("sprzęgło pomocnicze", "ta", "to"),
                ("zdjęcie archiwalne", "ta", "to"),
                ("krzesło składane", "ta", "to"),
                ("ogniwo pomiarowe", "ta", "to"),
                ("hasło kontrolne", "ta", "to"),
            ),
            description=(
                "Replaces feminine demonstrative “{wrong}” with neuter "
                "nominative “{correct}”."
            ),
            tags=("inflection", "agreement", "neuter"),
        )
    )
    specs.extend(
        _replacement_group(
            (
                "Komisja wybrała {form} {context} do dalszej analizy.",
                "Zespół zamówił {form} {context} na próbne wdrożenie.",
                "Kierowniczka wskazała {form} {context} jako priorytet.",
                "Technicy zabrali {form} {context} na stanowisko numer trzy.",
                "Sekretariat wysłał {form} {context} do podpisu.",
                "Ekipa ustawiła {form} {context} przy ścianie północnej.",
                "Badacze opisali {form} {context} w protokole.",
                "Organizatorzy przewieźli {form} {context} osobnym autem.",
                "Kontrolerzy oznaczyli {form} {context} żółtą taśmą.",
                "Uczestnicy otrzymali {form} {context} po rejestracji.",
            ),
            (
                ("metodę badawczą", "nowy", "nową"),
                ("platformę roboczą", "lekki", "lekką"),
                ("procedurę awaryjną", "krótki", "krótką"),
                ("wiertarkę udarową", "sprawny", "sprawną"),
                ("uchwałę programową", "gotowy", "gotową"),
                ("konstrukcję wsporczą", "stalowy", "stalową"),
                ("reakcję chemiczną", "nietypowy", "nietypową"),
                ("wystawę objazdową", "mobilny", "mobilną"),
                ("strefę ochronną", "zewnętrzny", "zewnętrzną"),
                ("broszurę informacyjną", "bezpłatny", "bezpłatną"),
            ),
            description="Corrects feminine agreement from “{wrong}” to “{correct}”.",
            tags=("inflection", "agreement", "adjective"),
        )
    )
    specs.extend(
        _replacement_group(
            (
                "Recenzent przyjrzał się {form} {context} przed publikacją.",
                "Inspektorka poświęciła uwagę {form} {context} podczas odbioru.",
                "Analityk długo przyglądał się {form} {context} na ekranie.",
                "Lekarka przekazała zalecenia {form} {context} po badaniu.",
                "Mentor udzielił wsparcia {form} {context} w pierwszym tygodniu.",
                "Sędzia przysłuchiwał się {form} {context} bez przerywania.",
                "Kustoszka nadała numer {form} {context} z darowizny.",
                "Dyżurny przekazał klucz {form} {context} po odprawie.",
                "Koordynatorka przypisała zadanie {form} {context} z zespołu.",
                "Serwisant przyjrzał się {form} {context} przed wymianą.",
            ),
            (
                ("opracowaniu eksperckiemu", "obszerny", "obszernemu"),
                ("zamówieniu publicznemu", "pilny", "pilnemu"),
                ("zestawieniu miesięcznemu", "szczegółowy", "szczegółowemu"),
                ("pacjentowi ambulatoryjnemu", "młody", "młodemu"),
                ("stażyście technicznemu", "nowy", "nowemu"),
                ("świadkowi koronnemu", "ważny", "ważnemu"),
                ("eksponatowi ceramicznemu", "kruchy", "kruchemu"),
                ("pracownikowi zmianowemu", "spóźniony", "spóźnionemu"),
                ("asystentowi terenowemu", "doświadczony", "doświadczonemu"),
                ("modułowi sterującemu", "wadliwy", "wadliwemu"),
            ),
            description="Corrects dative agreement from “{wrong}” to “{correct}”.",
            tags=("inflection", "case", "dative"),
        )
    )
    specs.extend(
        _replacement_group(
            (
                "O zmianie rozmawiano w {form} {context} po zamknięciu.",
                "Próby prowadzono na {form} {context} przez trzy godziny.",
                "Dokument znaleziono w {form} {context} pod oknem.",
                "Alarm uruchomiono na {form} {context} tuż przed świtem.",
                "Spotkanie odbyło się w {form} {context} bez gości.",
                "Naprawę wykonano przy {form} {context} podczas postoju.",
                "Nagranie powstało w {form} {context} po próbie.",
                "Oznaczenie umieszczono na {form} {context} od strony wejścia.",
                "Pomiary wykonano w {form} {context} przy pełnym obciążeniu.",
                "Zajęcia prowadzono w {form} {context} przez cały semestr.",
            ),
            (
                ("centrum logistycznym", "nowego", "nowym"),
                ("poligonie doświadczalnym", "zamkniętego", "zamkniętym"),
                ("archiwum zakładowym", "głównego", "głównym"),
                ("odcinku próbnym", "północnego", "północnym"),
                ("pawilonie konferencyjnym", "odnowionego", "odnowionym"),
                ("silniku pomocniczym", "wyłączonego", "wyłączonym"),
                ("studiu emisyjnym", "małego", "małym"),
                ("zbiorniku retencyjnym", "betonowego", "betonowym"),
                ("laboratorium materiałowym", "akredytowanego", "akredytowanym"),
                ("ośrodku edukacyjnym", "lokalnego", "lokalnym"),
            ),
            description="Corrects locative agreement from “{wrong}” to “{correct}”.",
            tags=("inflection", "case", "locative"),
        )
    )
    specs.extend(
        _replacement_group(
            (
                "Operator posłużył się {form} {context} podczas rozruchu.",
                "Kartograf pracował z {form} {context} przy wyznaczaniu trasy.",
                "Restauratorka oczyściła detal {form} {context}.",
                "Ratowniczka zabezpieczyła linę {form} {context}.",
                "Fotograf wykonał ujęcie {form} {context}.",
                "Laborant przeniósł roztwór {form} {context}.",
                "Ogrodnik wyrównał brzeg {form} {context}.",
                "Geodetka oznaczyła punkt {form} {context}.",
                "Monter dokręcił złącze {form} {context}.",
                "Konserwator pokrył powierzchnię {form} {context}.",
            ),
            (
                ("dźwignią sterującą", "krótka", "krótką"),
                ("mapą topograficzną", "dokładna", "dokładną"),
                ("szczotką włosianą", "miękka", "miękką"),
                ("taśmą odblaskową", "szeroka", "szeroką"),
                ("kamerą termiczną", "przenośna", "przenośną"),
                ("pipetą miarową", "szklana", "szklaną"),
                ("łopatą ogrodową", "płaska", "płaską"),
                ("tyczką pomiarową", "wysoka", "wysoką"),
                ("nakrętką kontrującą", "stalowa", "stalową"),
                ("żywicą ochronną", "bezbarwna", "bezbarwną"),
            ),
            description=(
                "Corrects instrumental agreement from “{wrong}” to “{correct}”."
            ),
            tags=("inflection", "case", "instrumental"),
        )
    )
    return specs


def _syntax_specs() -> list[CaseSpec]:
    groups: tuple[tuple[tuple[tuple[str, str], ...], str, tuple[str, ...]], ...] = (
        (
            (
                (
                    "Operator nie odnalazł kompletny rejestr zmian.",
                    "Operator nie odnalazł kompletnego rejestru zmian.",
                ),
                (
                    "Redakcja nie otrzymała podpisana zgoda autora.",
                    "Redakcja nie otrzymała podpisanej zgody autora.",
                ),
                (
                    "Ekipa nie zabezpieczyła uszkodzony fragment dachu.",
                    "Ekipa nie zabezpieczyła uszkodzonego fragmentu dachu.",
                ),
                (
                    "Archiwistka nie znalazła brakująca karta katalogowa.",
                    "Archiwistka nie znalazła brakującej karty katalogowej.",
                ),
                (
                    "Laborant nie pobrał wymagana próbka kontrolna.",
                    "Laborant nie pobrał wymaganej próbki kontrolnej.",
                ),
                (
                    "Ratownik nie zauważył zerwana plomba zabezpieczająca.",
                    "Ratownik nie zauważył zerwanej plomby zabezpieczającej.",
                ),
                (
                    "Scenograf nie przygotował zapasowy element dekoracji.",
                    "Scenograf nie przygotował zapasowego elementu dekoracji.",
                ),
                (
                    "Analityczka nie sprawdziła końcowa wersja zestawienia.",
                    "Analityczka nie sprawdziła końcowej wersji zestawienia.",
                ),
                (
                    "Serwisant nie wymienił zużyty przewód zasilający.",
                    "Serwisant nie wymienił zużytego przewodu zasilającego.",
                ),
                (
                    "Koordynator nie wysłał aktualny plan dyżurów.",
                    "Koordynator nie wysłał aktualnego planu dyżurów.",
                ),
            ),
            "Corrects object government under sentential negation.",
            ("syntax", "government", "negation"),
        ),
        (
            (
                (
                    "Większość uczestników zakończyli ćwiczenie przed południem.",
                    "Większość uczestników zakończyła ćwiczenie przed południem.",
                ),
                (
                    "Większość komisji poparli wniosek bez zastrzeżeń.",
                    "Większość komisji poparła wniosek bez zastrzeżeń.",
                ),
                (
                    "Większość załogi opuścili pokład po alarmie.",
                    "Większość załogi opuściła pokład po alarmie.",
                ),
                (
                    "Większość publiczności zajęli miejsca na balkonie.",
                    "Większość publiczności zajęła miejsca na balkonie.",
                ),
                (
                    "Większość grupy wybrali krótszą trasę powrotną.",
                    "Większość grupy wybrała krótszą trasę powrotną.",
                ),
                (
                    "Większość rady przyjęli poprawkę podczas głosowania.",
                    "Większość rady przyjęła poprawkę podczas głosowania.",
                ),
                (
                    "Większość zespołu podpisali protokół jeszcze rano.",
                    "Większość zespołu podpisała protokół jeszcze rano.",
                ),
                (
                    "Większość obsługi sprawdzili bilety przy wejściu.",
                    "Większość obsługi sprawdziła bilety przy wejściu.",
                ),
                (
                    "Większość klasy rozwiązali zadanie bez podpowiedzi.",
                    "Większość klasy rozwiązała zadanie bez podpowiedzi.",
                ),
                (
                    "Większość delegacji wrócili wieczornym pociągiem.",
                    "Większość delegacji wróciła wieczornym pociągiem.",
                ),
            ),
            "Corrects predicate agreement with a singular collective subject.",
            ("syntax", "agreement", "collective_subject"),
        ),
        (
            (
                (
                    "Każdy z monterów sprawdzili własny zestaw narzędzi.",
                    "Każdy z monterów sprawdził własny zestaw narzędzi.",
                ),
                (
                    "Każdy z recenzentów przesłali osobną opinię.",
                    "Każdy z recenzentów przesłał osobną opinię.",
                ),
                (
                    "Każdy z kierowców zapisali godzinę przyjazdu.",
                    "Każdy z kierowców zapisał godzinę przyjazdu.",
                ),
                (
                    "Każdy z lekarzy otrzymali dostęp do wyników.",
                    "Każdy z lekarzy otrzymał dostęp do wyników.",
                ),
                (
                    "Każdy z muzyków przygotowali zapasowe nuty.",
                    "Każdy z muzyków przygotował zapasowe nuty.",
                ),
                (
                    "Każdy z badaczy opisali użyte odczynniki.",
                    "Każdy z badaczy opisał użyte odczynniki.",
                ),
                (
                    "Każdy z przewodników wskazali bezpieczne przejście.",
                    "Każdy z przewodników wskazał bezpieczne przejście.",
                ),
                (
                    "Każdy z audytorów podpisali własny arkusz kontroli.",
                    "Każdy z audytorów podpisał własny arkusz kontroli.",
                ),
                (
                    "Każdy z uczniów przynieśli papierowy atlas.",
                    "Każdy z uczniów przyniósł papierowy atlas.",
                ),
                (
                    "Każdy z operatorów uruchomili osobny terminal.",
                    "Każdy z operatorów uruchomił osobny terminal.",
                ),
            ),
            "Corrects predicate agreement with the singular pronoun “każdy”.",
            ("syntax", "agreement", "quantified_subject"),
        ),
        (
            (
                (
                    "Zespół potrzebuje nowy plan ewakuacji.",
                    "Zespół potrzebuje nowego planu ewakuacji.",
                ),
                (
                    "Pracownia potrzebuje dodatkowe źródło światła.",
                    "Pracownia potrzebuje dodatkowego źródła światła.",
                ),
                (
                    "Biblioteka potrzebuje aktualny wykaz czasopism.",
                    "Biblioteka potrzebuje aktualnego wykazu czasopism.",
                ),
                (
                    "Stacja potrzebuje sprawna antena kierunkowa.",
                    "Stacja potrzebuje sprawnej anteny kierunkowej.",
                ),
                (
                    "Warsztat potrzebuje precyzyjne urządzenie pomiarowe.",
                    "Warsztat potrzebuje precyzyjnego urządzenia pomiarowego.",
                ),
                (
                    "Sekretariat potrzebuje podpisana kopia umowy.",
                    "Sekretariat potrzebuje podpisanej kopii umowy.",
                ),
                (
                    "Schronisko potrzebuje nowy agregat prądotwórczy.",
                    "Schronisko potrzebuje nowego agregatu prądotwórczego.",
                ),
                (
                    "Redakcja potrzebuje krótkie nagranie próbne.",
                    "Redakcja potrzebuje krótkiego nagrania próbnego.",
                ),
                (
                    "Magazyn potrzebuje oddzielna strefa odbioru.",
                    "Magazyn potrzebuje oddzielnej strefy odbioru.",
                ),
                (
                    "Laboratorium potrzebuje czysty pojemnik szklany.",
                    "Laboratorium potrzebuje czystego pojemnika szklanego.",
                ),
            ),
            "Corrects genitive government required by “potrzebować”.",
            ("syntax", "government", "genitive"),
        ),
        (
            (
                (
                    "W protokole brakuje trzy wymagane podpisy.",
                    "W protokole brakuje trzech wymaganych podpisów.",
                ),
                (
                    "W zestawie brakuje dwa krótkie przewody.",
                    "W zestawie brakuje dwóch krótkich przewodów.",
                ),
                (
                    "Na półce brakuje cztery oznaczone próbki.",
                    "Na półce brakuje czterech oznaczonych próbek.",
                ),
                (
                    "W archiwum brakuje pięć rocznych sprawozdań.",
                    "W archiwum brakuje pięciu rocznych sprawozdań.",
                ),
                (
                    "Na mapie brakuje trzy punkty orientacyjne.",
                    "Na mapie brakuje trzech punktów orientacyjnych.",
                ),
                (
                    "W raporcie brakuje dwa ważne załączniki.",
                    "W raporcie brakuje dwóch ważnych załączników.",
                ),
                (
                    "W apteczce brakuje cztery jałowe opatrunki.",
                    "W apteczce brakuje czterech jałowych opatrunków.",
                ),
                (
                    "Na liście brakuje pięć nazwisk uczestników.",
                    "Na liście brakuje pięciu nazwisk uczestników.",
                ),
                (
                    "W paczce brakuje trzy elementy montażowe.",
                    "W paczce brakuje trzech elementów montażowych.",
                ),
                (
                    "W katalogu brakuje dwa nowe rekordy.",
                    "W katalogu brakuje dwóch nowych rekordów.",
                ),
            ),
            "Corrects quantified genitive government after “brakuje”.",
            ("syntax", "government", "quantifier"),
        ),
        (
            (
                (
                    "Pomimo silny wiatr prom wypłynął zgodnie z planem.",
                    "Pomimo silnego wiatru prom wypłynął zgodnie z planem.",
                ),
                (
                    "Pomimo późna pora komisja dokończyła obrady.",
                    "Pomimo późnej pory komisja dokończyła obrady.",
                ),
                (
                    "Pomimo drobna usterka urządzenie zakończyło test.",
                    "Pomimo drobnej usterki urządzenie zakończyło test.",
                ),
                (
                    "Pomimo gęsta mgła patrol dotarł do schronu.",
                    "Pomimo gęstej mgły patrol dotarł do schronu.",
                ),
                (
                    "Pomimo krótki termin zespół przygotował ofertę.",
                    "Pomimo krótkiego terminu zespół przygotował ofertę.",
                ),
                (
                    "Pomimo niska temperatura próbka zachowała właściwości.",
                    "Pomimo niskiej temperatury próbka zachowała właściwości.",
                ),
                (
                    "Pomimo głośny remont biblioteka pozostała otwarta.",
                    "Pomimo głośnego remontu biblioteka pozostała otwarta.",
                ),
                (
                    "Pomimo długa trasa kierowca przyjechał punktualnie.",
                    "Pomimo długiej trasy kierowca przyjechał punktualnie.",
                ),
                (
                    "Pomimo brakujące dane analityk zamknął zestawienie.",
                    "Pomimo brakujących danych analityk zamknął zestawienie.",
                ),
                (
                    "Pomimo nagła zmiana organizator utrzymał program.",
                    "Pomimo nagłej zmiany organizator utrzymał program.",
                ),
            ),
            "Corrects genitive government required by “pomimo”.",
            ("syntax", "government", "preposition"),
        ),
    )
    return [
        CaseSpec(source, target, description, tags)
        for pairs, description, tags in groups
        for source, target in pairs
    ]


def _punctuation_specs() -> list[CaseSpec]:
    groups: tuple[tuple[tuple[tuple[str, str], ...], str, tuple[str, ...]], ...] = (
        (
            (
                (
                    "Zespół przerwał pomiar ponieważ czujnik wskazał błąd.",
                    "Zespół przerwał pomiar, ponieważ czujnik wskazał błąd.",
                ),
                (
                    "Kurier zawrócił ponieważ droga została zamknięta.",
                    "Kurier zawrócił, ponieważ droga została zamknięta.",
                ),
                (
                    "Biblioteka skróciła dyżur ponieważ zabrakło zasilania.",
                    "Biblioteka skróciła dyżur, ponieważ zabrakło zasilania.",
                ),
                (
                    "Próba rozpoczęła się później ponieważ aktor utknął w korku.",
                    "Próba rozpoczęła się później, ponieważ aktor utknął w korku.",
                ),
                (
                    "Statek pozostał w porcie ponieważ nadciągał sztorm.",
                    "Statek pozostał w porcie, ponieważ nadciągał sztorm.",
                ),
                (
                    "Serwisant wymienił moduł ponieważ stary się przegrzewał.",
                    "Serwisant wymienił moduł, ponieważ stary się przegrzewał.",
                ),
                (
                    "Komisja odroczyła decyzję ponieważ brakowało opinii prawnej.",
                    "Komisja odroczyła decyzję, ponieważ brakowało opinii prawnej.",
                ),
                (
                    "Ratownicy zmienili trasę ponieważ most był uszkodzony.",
                    "Ratownicy zmienili trasę, ponieważ most był uszkodzony.",
                ),
                (
                    "Redakcja usunęła tabelę ponieważ zawierała stare dane.",
                    "Redakcja usunęła tabelę, ponieważ zawierała stare dane.",
                ),
                (
                    "Technik wyłączył układ ponieważ pojawiło się iskrzenie.",
                    "Technik wyłączył układ, ponieważ pojawiło się iskrzenie.",
                ),
            ),
            "Inserts the required comma before a causal subordinate clause.",
            ("punctuation", "comma", "subordinate_clause"),
        ),
        (
            (
                (
                    "Odnaleziono szkic który zaginął podczas przeprowadzki.",
                    "Odnaleziono szkic, który zaginął podczas przeprowadzki.",
                ),
                (
                    "Naprawiono zawór który przeciekał od tygodnia.",
                    "Naprawiono zawór, który przeciekał od tygodnia.",
                ),
                (
                    "Wybrano trasę która omija zalany odcinek.",
                    "Wybrano trasę, która omija zalany odcinek.",
                ),
                (
                    "Przyjęto regulamin który obowiązuje od sierpnia.",
                    "Przyjęto regulamin, który obowiązuje od sierpnia.",
                ),
                (
                    "Otworzono salę która mieści sto osób.",
                    "Otworzono salę, która mieści sto osób.",
                ),
                (
                    "Zamówiono materiał który tłumi drgania.",
                    "Zamówiono materiał, który tłumi drgania.",
                ),
                (
                    "Wysłano raport który obejmuje cały kwartał.",
                    "Wysłano raport, który obejmuje cały kwartał.",
                ),
                (
                    "Zabezpieczono plik który zawiera dane pomiarowe.",
                    "Zabezpieczono plik, który zawiera dane pomiarowe.",
                ),
                (
                    "Oznaczono pojemnik który trafi do chłodni.",
                    "Oznaczono pojemnik, który trafi do chłodni.",
                ),
                (
                    "Przetestowano silnik który napędza pompę rezerwową.",
                    "Przetestowano silnik, który napędza pompę rezerwową.",
                ),
            ),
            "Inserts the required comma before a relative clause.",
            ("punctuation", "comma", "relative_clause"),
        ),
        (
            (
                (
                    "Kiedy ucichł alarm pracownicy wrócili do hali.",
                    "Kiedy ucichł alarm, pracownicy wrócili do hali.",
                ),
                (
                    "Gdy zakończono odprawę kierowcy odebrali dokumenty.",
                    "Gdy zakończono odprawę, kierowcy odebrali dokumenty.",
                ),
                (
                    "Jeśli pogoda się poprawi wyprawa ruszy o świcie.",
                    "Jeśli pogoda się poprawi, wyprawa ruszy o świcie.",
                ),
                (
                    "Zanim otwarto wystawę konserwator sprawdził gabloty.",
                    "Zanim otwarto wystawę, konserwator sprawdził gabloty.",
                ),
                (
                    "Chociaż padał deszcz zawody odbyły się zgodnie z planem.",
                    "Chociaż padał deszcz, zawody odbyły się zgodnie z planem.",
                ),
                (
                    "Dopóki trwał remont czytelnia działała na parterze.",
                    "Dopóki trwał remont, czytelnia działała na parterze.",
                ),
                (
                    "Skoro potwierdzono termin zespół zarezerwował nocleg.",
                    "Skoro potwierdzono termin, zespół zarezerwował nocleg.",
                ),
                (
                    "Kiedy nadeszła przesyłka laborant sprawdził plombę.",
                    "Kiedy nadeszła przesyłka, laborant sprawdził plombę.",
                ),
                (
                    "Gdy opadła mgła pilot wznowił lot próbny.",
                    "Gdy opadła mgła, pilot wznowił lot próbny.",
                ),
                (
                    "Jeżeli wynik się powtórzy komisja zleci dodatkowy test.",
                    "Jeżeli wynik się powtórzy, komisja zleci dodatkowy test.",
                ),
            ),
            "Separates an initial subordinate clause from the main clause.",
            ("punctuation", "comma", "initial_clause"),
        ),
        (
            (
                (
                    "Plan był ambitny ale zespół wykonał wszystkie etapy.",
                    "Plan był ambitny, ale zespół wykonał wszystkie etapy.",
                ),
                (
                    "Droga była śliska lecz kierowca zachował właściwe tempo.",
                    "Droga była śliska, lecz kierowca zachował właściwe tempo.",
                ),
                (
                    "Czujnik działał poprawnie jednak przewód wymagał wymiany.",
                    "Czujnik działał poprawnie, jednak przewód wymagał wymiany.",
                ),
                (
                    "Sala była niewielka ale wszyscy znaleźli miejsca.",
                    "Sala była niewielka, ale wszyscy znaleźli miejsca.",
                ),
                (
                    "Raport był kompletny lecz brakowało podpisu przewodniczącej.",
                    "Raport był kompletny, lecz brakowało podpisu przewodniczącej.",
                ),
                (
                    "Próba trwała krótko jednak dostarczyła ważnych danych.",
                    "Próba trwała krótko, jednak dostarczyła ważnych danych.",
                ),
                (
                    "Silnik był zimny ale uruchomił się bez problemu.",
                    "Silnik był zimny, ale uruchomił się bez problemu.",
                ),
                (
                    "Wniosek wpłynął późno lecz komisja zdążyła go ocenić.",
                    "Wniosek wpłynął późno, lecz komisja zdążyła go ocenić.",
                ),
                (
                    "Mapa była stara jednak szlak pozostał czytelny.",
                    "Mapa była stara, jednak szlak pozostał czytelny.",
                ),
                (
                    "Paczka była ciężka ale kurier wniósł ją samodzielnie.",
                    "Paczka była ciężka, ale kurier wniósł ją samodzielnie.",
                ),
            ),
            "Inserts a comma between coordinated clauses.",
            ("punctuation", "comma", "coordination"),
        ),
        (
            (
                (
                    "Panie kierowniku proszę zatwierdzić harmonogram.",
                    "Panie kierowniku, proszę zatwierdzić harmonogram.",
                ),
                (
                    "Szanowna komisjo dziękuję za ponowne rozpatrzenie.",
                    "Szanowna komisjo, dziękuję za ponowne rozpatrzenie.",
                ),
                (
                    "Drogi czytelniku sprawdź przypisy na końcu rozdziału.",
                    "Drogi czytelniku, sprawdź przypisy na końcu rozdziału.",
                ),
                (
                    "Pani doktor wyniki są już dostępne.",
                    "Pani doktor, wyniki są już dostępne.",
                ),
                (
                    "Młody odkrywco zachowaj tę mapę na później.",
                    "Młody odkrywco, zachowaj tę mapę na później.",
                ),
                (
                    "Szanowni goście wystawa zostanie otwarta o siedemnastej.",
                    "Szanowni goście, wystawa zostanie otwarta o siedemnastej.",
                ),
                (
                    "Panie kapitanie załoga czeka na rozkaz.",
                    "Panie kapitanie, załoga czeka na rozkaz.",
                ),
                (
                    "Drodzy uczestnicy odbierzcie identyfikatory przy wejściu.",
                    "Drodzy uczestnicy, odbierzcie identyfikatory przy wejściu.",
                ),
                (
                    "Pani redaktor tekst wymaga jeszcze korekty.",
                    "Pani redaktor, tekst wymaga jeszcze korekty.",
                ),
                (
                    "Kolego mechaniku podaj klucz dynamometryczny.",
                    "Kolego mechaniku, podaj klucz dynamometryczny.",
                ),
            ),
            "Inserts the comma required after a direct address.",
            ("punctuation", "comma", "vocative"),
        ),
        (
            (
                (
                    "Czytając instrukcję operator zaznaczył najważniejsze kroki.",
                    "Czytając instrukcję, operator zaznaczył najważniejsze kroki.",
                ),
                (
                    "Wracając z patrolu ratownik zauważył uszkodzoną barierę.",
                    "Wracając z patrolu, ratownik zauważył uszkodzoną barierę.",
                ),
                (
                    "Analizując próbkę badaczka zapisała zmianę koloru.",
                    "Analizując próbkę, badaczka zapisała zmianę koloru.",
                ),
                (
                    "Otwierając skrzynię magazynier sprawdził numer plomby.",
                    "Otwierając skrzynię, magazynier sprawdził numer plomby.",
                ),
                (
                    "Kończąc raport analityk dodał krótkie podsumowanie.",
                    "Kończąc raport, analityk dodał krótkie podsumowanie.",
                ),
                (
                    "Przechodząc przez halę inspektorka usłyszała nietypowy hałas.",
                    "Przechodząc przez halę, inspektorka usłyszała nietypowy hałas.",
                ),
                (
                    "Pakując sprzęt fotograf zabezpieczył szklany obiektyw.",
                    "Pakując sprzęt, fotograf zabezpieczył szklany obiektyw.",
                ),
                (
                    "Sprawdzając listę koordynatorka odnalazła brakujący wpis.",
                    "Sprawdzając listę, koordynatorka odnalazła brakujący wpis.",
                ),
                (
                    "Montując czujnik technik odłączył główne zasilanie.",
                    "Montując czujnik, technik odłączył główne zasilanie.",
                ),
                (
                    "Porównując mapy przewodniczka wybrała bezpieczniejszy szlak.",
                    "Porównując mapy, przewodniczka wybrała bezpieczniejszy szlak.",
                ),
            ),
            "Separates an initial adverbial participial phrase.",
            ("punctuation", "comma", "participial_phrase"),
        ),
    )
    return [
        CaseSpec(source, target, description, tags)
        for pairs, description, tags in groups
        for source, target in pairs
    ]


def _hard_negative_specs() -> list[CaseSpec]:
    decimal_sentences = (
        "Przewód miał długość 7,85 metra.",
        "Temperatura wzrosła o 2,6 stopnia.",
        "Masa próbki wyniosła 14,20 grama.",
        "Zbiornik pomieścił 3,75 litra.",
        "Poziom hałasu spadł o 1,4 decybela.",
        "Płyta miała grubość 0,65 milimetra.",
        "Trasa skróciła się o 5,30 kilometra.",
        "Roztwór zawierał 8,5 procent dodatku.",
        "Opóźnienie wyniosło 12,25 minuty.",
        "Koszt jednostkowy wzrósł do 6,90 zł.",
    )
    url_sentences = (
        "Instrukcja znajduje się pod adresem https://serwis.example.pl/start.",
        "Wyniki opublikowano na https://badania.example.org/wyniki.",
        "Rozkład jest dostępny na https://transport.example.net/plan.",
        (
            "Recepcja przekazała uczestnikom elektroniczny formularz dostępny pod "
            "https://urzad.example.pl/formularze."
        ),
        "Mapa działa pod adresem https://teren.example.com/szlaki.",
        "Archiwum udostępniono na https://zbiory.example.net/katalog.",
        "Status paczki sprawdzono na https://kurier.example.org/status.",
        (
            "Po zakończeniu zapisów zasady klubu można nadal przeczytać w witrynie "
            "https://klub.example.pl/zasady."
        ),
        "Zdjęcia umieszczono na https://galeria.example.com/wystawa.",
        "Komunikaty pojawiają się na https://alarm.example.net/aktualnosci.",
    )
    quotation_sentences = (
        "Na tablicy zapisano: „Wejście tylko dla obsługi”.",
        "Instruktorka powiedziała: „Zaczynamy od krótkiej próby”.",
        "W raporcie widnieje określenie „wariant rezerwowy”.",
        "Technik zapytał: „Czy zasilanie jest odłączone?”",
        "Przewodnik przypomniał: „Nie schodzimy ze szlaku”.",
        "Redaktorka zaznaczyła zwrot „wersja robocza”.",
        "Na kopercie napisano: „Otworzyć po odbiorze”.",
        "Sędzia ogłosił: „Wniosek został przyjęty”.",
        "W instrukcji użyto hasła „tryb bezpieczny”.",
        "Kierowca odpowiedział: „Będę przed południem”.",
    )
    abbreviation_sentences = (
        "Spotkanie rozpocznie się o godz. 8.30.",
        "Przesyłka waży ok. 12 kilogramów.",
        "Zestaw zawiera m.in. dwa przewody.",
        "Przesyłkę nadano w woj. pomorskim.",
        "Adres zapisano przy ul. Leśnej 4.",
        "Koszt podano w tys. zł.",
        "Badanie wykonano dn. 23 lipca.",
        "Wymiary wynoszą 8 cm × 12 cm.",
        "Temperaturę zapisano jako 21 °C.",
        "Termin przypada na 15.08.2026 r.",
    )
    people_sentences = (
        "Alicja Kurek prowadzi dzisiejsze warsztaty terenowe.",
        "Bartosz Domański odebrał zaplombowaną przesyłkę.",
        "Celina Rogalska przygotowała plan rozmieszczenia stanowisk.",
        "Damian Kaczmarek sprawdził działanie agregatu.",
        "Ewa Leszczyńska podpisała protokół odbioru.",
        "Filip Jaworski poprowadził poranną odprawę.",
        "Grażyna Kłos uporządkowała dokumentację projektu.",
        "Ireneusz Marciniak zamknął magazyn po kontroli.",
        "Joanna Rybak przedstawiła wyniki pomiarów.",
        "Konrad Zięba zarezerwował salę na czwartek.",
    )
    place_sentences = (
        "Błękitna Dolina pozostaje zamknięta po intensywnych opadach.",
        "Cichy Bór leży poza głównym szlakiem turystycznym.",
        "Kamienny Brzeg otrzymał nowe oznaczenia kierunkowe.",
        "Leśna Przełęcz jest dostępna wyłącznie od południa.",
        "Nowa Przystań organizuje coroczny przegląd łodzi.",
        "Srebrny Jar zachował dawny układ ścieżek.",
        "Stary Most wymaga okresowej kontroli technicznej.",
        "Wysoka Łąka słynie z późnego kwitnienia roślin.",
        "Zielone Wzgórze znajduje się przy północnej granicy parku.",
        "Źródlana Polana została objęta ochroną krajobrazową.",
    )
    groups = (
        ("decimal_comma", decimal_sentences),
        ("url", url_sentences),
        ("quotation", quotation_sentences),
        ("abbreviation_or_measurement", abbreviation_sentences),
        ("proper_name", people_sentences),
        ("place_name", place_sentences),
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
    value = unicodedata.normalize("NFKD", surface.casefold()).replace("ł", "l")
    value = "".join(
        character for character in value if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def _entity_spans(text: str) -> tuple[EntitySpan, ...]:
    found: list[EntitySpan] = []
    occupied: list[tuple[int, int]] = []
    for surface in sorted(SAFETY_V2_CONTROLLED_ENTITY_SURFACES, key=len, reverse=True):
        cursor = 0
        while True:
            start = text.find(surface, cursor)
            if start < 0:
                break
            end = start + len(surface)
            cursor = end
            boundaries = (
                start == 0 or not text[start - 1].isalpha(),
                end == len(text) or not text[end].isalpha(),
            )
            overlaps = any(start < right and left < end for left, right in occupied)
            if all(boundaries) and not overlaps:
                found.append(EntitySpan(start=start, end=end, surface=surface))
                occupied.append((start, end))
    return tuple(sorted(found, key=lambda span: span.start))


def _case(stratum: str, index: int, spec: CaseSpec) -> dict[str, Any]:
    spans = _entity_spans(spec.input)
    return {
        "id": f"safety_v2_{stratum}_{index:03d}",
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
            "checklist_version": REVIEW_CHECKLIST_V2_VERSION,
        },
        "edits": (
            []
            if stratum == "hard_negative"
            else [_single_edit(spec.input, spec.expected, stratum)]
        ),
    }


def build_candidate_corpus() -> dict[str, Any]:
    """Build the pending, unscored v2 candidate corpus."""

    strata = {
        "inflection": _inflection_specs(),
        "syntax": _syntax_specs(),
        "punctuation": _punctuation_specs(),
        "hard_negative": _hard_negative_specs(),
    }
    if any(len(specs) != 60 for specs in strata.values()):
        raise ValueError("each safety corpus v2 stratum must define 60 cases")
    raw: dict[str, Any] = {
        "schema_version": 3,
        "id": CORPUS_V2_ID,
        "language": "pl-PL",
        "holdout_state": "unfrozen-candidates",
        "provenance": dict(PROVENANCE),
        "review_policy": {
            "candidate_status": "pending-human-review",
            "approval_status": "human-reviewed",
            "required_reviewer": V2_REQUIRED_REVIEWER,
            "checklist_version": REVIEW_CHECKLIST_V2_VERSION,
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
        raise ValueError("safety corpus v2 approval manifest must be an object")
    required = {
        "corpus_id",
        "approval_scope",
        "approved_case_count",
        "candidate_digest",
        "frozen_digest",
        "reviewer",
        "reviewed_at",
        "checklist_version",
        "review_basis",
    }
    if set(raw) != required:
        raise ValueError("safety corpus v2 approval manifest has unexpected fields")
    return cast(dict[str, Any], raw)


def build_frozen_corpus() -> dict[str, Any]:
    """Apply the role-authorized review manifest to the exact candidate."""

    candidate = build_candidate_corpus()
    approval = _load_approval_manifest()
    candidate_digest = safety_corpus_digest(candidate)
    if candidate_digest != V2_APPROVED_CANDIDATE_DIGEST:
        raise RuntimeError(
            "safety corpus v2 candidate digest does not match role approval"
        )
    expected = {
        "corpus_id": CORPUS_V2_ID,
        "approval_scope": "all-cases",
        "approved_case_count": len(candidate["cases"]),
        "candidate_digest": V2_APPROVED_CANDIDATE_DIGEST,
        "reviewer": V2_REQUIRED_REVIEWER,
        "reviewed_at": V2_APPROVED_REVIEW_DATE,
        "checklist_version": REVIEW_CHECKLIST_V2_VERSION,
        "review_basis": V2_APPROVAL_REVIEW_BASIS,
    }
    for key, value in expected.items():
        if approval[key] != value:
            raise RuntimeError(f"invalid safety corpus v2 approval field: {key}")

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
    if approval["frozen_digest"] != digest or V2_APPROVED_FROZEN_DIGEST != digest:
        raise RuntimeError(
            "frozen safety corpus v2 digest does not match role approval"
        )
    return frozen


def build_corpus() -> dict[str, Any]:
    """Build the approved frozen corpus for committed fixtures."""

    return build_frozen_corpus()


def _corpus_records(path: Path, *, safety: bool) -> list[IsolationRecord]:
    corpus = (
        load_safety_corpus_json(path) if safety else load_correction_corpus_json(path)
    )
    return [
        IsolationRecord(
            id=case.id,
            input=case.input,
            entity_spans=case.entity_spans,
        )
        for case in corpus.cases
    ]


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
    """Reject v2 leakage from all reserved evaluation and prompt assets."""

    corpus = validate_safety_corpus(raw)
    sources = (
        ("safety-corpus-v1", _corpus_records(SAFETY_V1_PATH, safety=True)),
        ("corpus-v3", _corpus_records(CORPUS_V3_PATH, safety=False)),
        ("finetuning", _finetuning_records()),
        ("prompt-e2e", _prompt_and_e2e_records()),
    )
    for source, records in sources:
        assert_no_cross_corpus_leakage(corpus, records, source=source)


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
    if safety_corpus_digest(raw) != V2_APPROVED_FROZEN_DIGEST:
        raise RuntimeError(
            "frozen safety corpus v2 content changed; create a new corpus "
            "version and repeat role review"
        )
    validate_reserved_asset_isolation(raw)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_xml(raw)


if __name__ == "__main__":
    main()
