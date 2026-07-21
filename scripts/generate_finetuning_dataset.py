"""Generate the deterministic CC0 Polish correction fine-tuning bundle."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

from polis.evaluation.finetuning_dataset import (
    build_finetuning_manifest,
    render_bielik_chatml,
    validate_finetuning_records,
)
from polis.llm import (
    FiniteCandidate,
    build_inflection_candidate_prompt_request,
    build_specialist_corrected_text_prompt_request,
)
from polis.llm.corrected_text import SpecialistFocus

ROOT = Path(__file__).parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "finetuning" / "bielik_1_5b_v1"

Split = Literal["train", "validation"]

PROVENANCE = {
    "source": "Polis project-authored synthetic sentence",
    "license": "CC0-1.0",
    "gold_source": "reviewed-linguistic-transformation",
    "model_generated": False,
}
REVIEW = {
    "state": "transformation-reviewed",
    "method": "linguistic-transformation-registry-review-v1",
    "checklist_version": "finetuning-dataset-v1",
}


@dataclass(frozen=True)
class Person:
    identity: str
    nominative: str
    genitive: str
    dative: str
    accusative: str
    instrumental: str
    locative: str
    vocative: str


TRAIN_PEOPLE = (
    Person(
        "mariusz_borowski",
        "Mariusz Borowski",
        "Mariusza Borowskiego",
        "Mariuszowi Borowskiemu",
        "Mariusza Borowskiego",
        "Mariuszem Borowskim",
        "Mariuszu Borowskim",
        "Mariuszu Borowski",
    ),
    Person(
        "dariusz_lipski",
        "Dariusz Lipski",
        "Dariusza Lipskiego",
        "Dariuszowi Lipskiemu",
        "Dariusza Lipskiego",
        "Dariuszem Lipskim",
        "Dariuszu Lipskim",
        "Dariuszu Lipski",
    ),
    Person(
        "hubert_radomski",
        "Hubert Radomski",
        "Huberta Radomskiego",
        "Hubertowi Radomskiemu",
        "Huberta Radomskiego",
        "Hubertem Radomskim",
        "Hubercie Radomskim",
        "Hubercie Radomski",
    ),
    Person(
        "konrad_olszewski",
        "Konrad Olszewski",
        "Konrada Olszewskiego",
        "Konradowi Olszewskiemu",
        "Konrada Olszewskiego",
        "Konradem Olszewskim",
        "Konradzie Olszewskim",
        "Konradzie Olszewski",
    ),
    Person(
        "bogdan_borkowski",
        "Bogdan Borkowski",
        "Bogdana Borkowskiego",
        "Bogdanowi Borkowskiemu",
        "Bogdana Borkowskiego",
        "Bogdanem Borkowskim",
        "Bogdanie Borkowskim",
        "Bogdanie Borkowski",
    ),
    Person(
        "ryszard_jaworski",
        "Ryszard Jaworski",
        "Ryszarda Jaworskiego",
        "Ryszardowi Jaworskiemu",
        "Ryszarda Jaworskiego",
        "Ryszardem Jaworskim",
        "Ryszardzie Jaworskim",
        "Ryszardzie Jaworski",
    ),
    Person(
        "waldemar_rogowski",
        "Waldemar Rogowski",
        "Waldemara Rogowskiego",
        "Waldemarowi Rogowskiemu",
        "Waldemara Rogowskiego",
        "Waldemarem Rogowskim",
        "Waldemarze Rogowskim",
        "Waldemarze Rogowski",
    ),
    Person(
        "artur_sikorski",
        "Artur Sikorski",
        "Artura Sikorskiego",
        "Arturowi Sikorskiemu",
        "Artura Sikorskiego",
        "Arturem Sikorskim",
        "Arturze Sikorskim",
        "Arturze Sikorski",
    ),
    Person(
        "emil_zawadzki",
        "Emil Zawadzki",
        "Emila Zawadzkiego",
        "Emilowi Zawadzkiemu",
        "Emila Zawadzkiego",
        "Emilem Zawadzkim",
        "Emilu Zawadzkim",
        "Emilu Zawadzki",
    ),
    Person(
        "seweryn_witkowski",
        "Seweryn Witkowski",
        "Seweryna Witkowskiego",
        "Sewerynowi Witkowskiemu",
        "Seweryna Witkowskiego",
        "Sewerynem Witkowskim",
        "Sewerynie Witkowskim",
        "Sewerynie Witkowski",
    ),
    Person(
        "grazyna_borowska",
        "Grażyna Borowska",
        "Grażyny Borowskiej",
        "Grażynie Borowskiej",
        "Grażynę Borowską",
        "Grażyną Borowską",
        "Grażynie Borowskiej",
        "Grażyno Borowska",
    ),
    Person(
        "renata_lipska",
        "Renata Lipska",
        "Renaty Lipskiej",
        "Renacie Lipskiej",
        "Renatę Lipską",
        "Renatą Lipską",
        "Renacie Lipskiej",
        "Renato Lipska",
    ),
    Person(
        "danuta_radomska",
        "Danuta Radomska",
        "Danuty Radomskiej",
        "Danucie Radomskiej",
        "Danutę Radomską",
        "Danutą Radomską",
        "Danucie Radomskiej",
        "Danuto Radomska",
    ),
    Person(
        "lidia_olszewska",
        "Lidia Olszewska",
        "Lidii Olszewskiej",
        "Lidii Olszewskiej",
        "Lidię Olszewską",
        "Lidią Olszewską",
        "Lidii Olszewskiej",
        "Lidio Olszewska",
    ),
    Person(
        "monika_borkowska",
        "Monika Borkowska",
        "Moniki Borkowskiej",
        "Monice Borkowskiej",
        "Monikę Borkowską",
        "Moniką Borkowską",
        "Monice Borkowskiej",
        "Moniko Borkowska",
    ),
    Person(
        "alicja_jaworska",
        "Alicja Jaworska",
        "Alicji Jaworskiej",
        "Alicji Jaworskiej",
        "Alicję Jaworską",
        "Alicją Jaworską",
        "Alicji Jaworskiej",
        "Alicjo Jaworska",
    ),
    Person(
        "teresa_rogowska",
        "Teresa Rogowska",
        "Teresy Rogowskiej",
        "Teresie Rogowskiej",
        "Teresę Rogowską",
        "Teresą Rogowską",
        "Teresie Rogowskiej",
        "Tereso Rogowska",
    ),
    Person(
        "beata_sikorska",
        "Beata Sikorska",
        "Beaty Sikorskiej",
        "Beacie Sikorskiej",
        "Beatę Sikorską",
        "Beatą Sikorską",
        "Beacie Sikorskiej",
        "Beato Sikorska",
    ),
    Person(
        "urszula_zawadzka",
        "Urszula Zawadzka",
        "Urszuli Zawadzkiej",
        "Urszuli Zawadzkiej",
        "Urszulę Zawadzką",
        "Urszulą Zawadzką",
        "Urszuli Zawadzkiej",
        "Urszulo Zawadzka",
    ),
    Person(
        "sabina_witkowska",
        "Sabina Witkowska",
        "Sabiny Witkowskiej",
        "Sabinie Witkowskiej",
        "Sabinę Witkowską",
        "Sabiną Witkowską",
        "Sabinie Witkowskiej",
        "Sabino Witkowska",
    ),
)

VALIDATION_PEOPLE = (
    Person(
        "kordian_milewski",
        "Kordian Milewski",
        "Kordiana Milewskiego",
        "Kordianowi Milewskiemu",
        "Kordiana Milewskiego",
        "Kordianem Milewskim",
        "Kordianie Milewskim",
        "Kordianie Milewski",
    ),
    Person(
        "marcel_gajewski",
        "Marcel Gajewski",
        "Marcela Gajewskiego",
        "Marcelowi Gajewskiemu",
        "Marcela Gajewskiego",
        "Marcelem Gajewskim",
        "Marcelu Gajewskim",
        "Marcelu Gajewski",
    ),
    Person(
        "ernest_klimowski",
        "Ernest Klimowski",
        "Ernesta Klimowskiego",
        "Ernestowi Klimowskiemu",
        "Ernesta Klimowskiego",
        "Ernestem Klimowskim",
        "Erneście Klimowskim",
        "Erneście Klimowski",
    ),
    Person(
        "bruno_wasilewski",
        "Bruno Wasilewski",
        "Bruna Wasilewskiego",
        "Brunowi Wasilewskiemu",
        "Bruna Wasilewskiego",
        "Brunem Wasilewskim",
        "Brunie Wasilewskim",
        "Brunie Wasilewski",
    ),
    Person(
        "olaf_czarnecki",
        "Olaf Czarnecki",
        "Olafa Czarneckiego",
        "Olafowi Czarneckiemu",
        "Olafa Czarneckiego",
        "Olafem Czarneckim",
        "Olafie Czarneckim",
        "Olafie Czarnecki",
    ),
    Person(
        "ignacy_sadowski",
        "Ignacy Sadowski",
        "Ignacego Sadowskiego",
        "Ignacemu Sadowskiemu",
        "Ignacego Sadowskiego",
        "Ignacym Sadowskim",
        "Ignacym Sadowskim",
        "Ignacy Sadowski",
    ),
    Person(
        "elwira_milewska",
        "Elwira Milewska",
        "Elwiry Milewskiej",
        "Elwirze Milewskiej",
        "Elwirę Milewską",
        "Elwirą Milewską",
        "Elwirze Milewskiej",
        "Elwiro Milewska",
    ),
    Person(
        "malwina_gajewska",
        "Malwina Gajewska",
        "Malwiny Gajewskiej",
        "Malwinie Gajewskiej",
        "Malwinę Gajewską",
        "Malwiną Gajewską",
        "Malwinie Gajewskiej",
        "Malwino Gajewska",
    ),
    Person(
        "jolanta_klimowska",
        "Jolanta Klimowska",
        "Jolanty Klimowskiej",
        "Jolancie Klimowskiej",
        "Jolantę Klimowską",
        "Jolantą Klimowską",
        "Jolancie Klimowskiej",
        "Jolanto Klimowska",
    ),
    Person(
        "karina_wasilewska",
        "Karina Wasilewska",
        "Kariny Wasilewskiej",
        "Karinie Wasilewskiej",
        "Karinę Wasilewską",
        "Kariną Wasilewską",
        "Karinie Wasilewskiej",
        "Karino Wasilewska",
    ),
    Person(
        "nina_czarnecka",
        "Nina Czarnecka",
        "Niny Czarneckiej",
        "Ninie Czarneckiej",
        "Ninę Czarnecką",
        "Niną Czarnecką",
        "Ninie Czarneckiej",
        "Nino Czarnecka",
    ),
    Person(
        "wioletta_sadowska",
        "Wioletta Sadowska",
        "Wioletty Sadowskiej",
        "Wioletcie Sadowskiej",
        "Wiolettę Sadowską",
        "Wiolettą Sadowską",
        "Wioletcie Sadowskiej",
        "Wioletto Sadowska",
    ),
)

TRAIN_INFLECTION_TEMPLATES = (
    ("inst_discussion", "Rozmawialiśmy z {name} po naradzie.", "instrumental", "inst"),
    ("gen_opinion", "Nie uwzględniono opinii {name} w raporcie.", "genitive", "gen"),
    (
        "dat_copy",
        "Kopię protokołu przekazano {name} przed naradą.",
        "dative",
        "dat",
    ),
    (
        "acc_invite",
        "Na posiedzenie zaproszono {name} w poniedziałek.",
        "accusative",
        "acc",
    ),
    ("loc_note", "W notatce napisano o {name} bardzo rzeczowo.", "locative", "loc"),
    ("voc_question", "{name}, czy możesz sprawdzić załącznik?", "vocative", "voc"),
    (
        "inst_project",
        "Projekt przygotowano wspólnie z {name} w maju.",
        "instrumental",
        "inst",
    ),
    ("gen_signature", "Brakuje podpisu {name} pod decyzją.", "genitive", "gen"),
    (
        "dat_access",
        "Dostęp do archiwum umożliwiono {name} bez zwłoki.",
        "dative",
        "dat",
    ),
    (
        "acc_nomination",
        "Do komisji konkursowej wyznaczono {name} jednogłośnie.",
        "accusative",
        "acc",
    ),
    ("loc_debate", "Podczas debaty mówiono o {name} z uznaniem.", "locative", "loc"),
    ("voc_request", "{name}, proszę zamknąć okno przed wyjściem.", "vocative", "voc"),
    (
        "inst_consult",
        "Wyniki skonsultowano z {name} przed publikacją.",
        "instrumental",
        "inst",
    ),
    ("gen_email", "Nie znaleziono wiadomości od {name} w skrzynce.", "genitive", "gen"),
    (
        "dat_award",
        "Za projekt przyznano {name} specjalne wyróżnienie.",
        "dative",
        "dat",
    ),
)

VALIDATION_INFLECTION_TEMPLATES = (
    (
        "val_acc_delegate",
        "Do zespołu kontrolnego delegowano {name} na miesiąc.",
        "accusative",
        "acc",
    ),
    (
        "val_inst_interview",
        "Wywiad przeprowadzono z {name} w poniedziałek.",
        "instrumental",
        "inst",
    ),
    ("val_gen_attachment", "W aktach nie było załącznika {name}.", "genitive", "gen"),
    (
        "val_dat_key",
        "Klucz do pracowni oddano {name} po kontroli.",
        "dative",
        "dat",
    ),
    ("val_loc_article", "W artykule wspomniano o {name} tylko raz.", "locative", "loc"),
)

TRAIN_SYNTAX = (
    (
        "each_participant",
        "Każdy z uczestników otrzymali wiadomość {detail}.",
        "Każdy z uczestników otrzymał wiadomość {detail}.",
    ),
    (
        "expert_group",
        "Grupa ekspertów przygotowali raport {detail}.",
        "Grupa ekspertów przygotowała raport {detail}.",
    ),
    (
        "committee_majority",
        "Większość komisji zaakceptowali wniosek {detail}.",
        "Większość komisji zaakceptowała wniosek {detail}.",
    ),
    (
        "solution_singular",
        "To rozwiązanie są wystarczająco dokładne {detail}.",
        "To rozwiązanie jest wystarczająco dokładne {detail}.",
    ),
    (
        "no_variant",
        "Żaden z wariantów nie spełniają wymagań {detail}.",
        "Żaden z wariantów nie spełnia wymagań {detail}.",
    ),
    (
        "editorial_team",
        "Zespół redakcyjny sprawdzili dokument {detail}.",
        "Zespół redakcyjny sprawdził dokument {detail}.",
    ),
    (
        "research_pair",
        "Para badaczy przeanalizowali próbkę {detail}.",
        "Para badaczy przeanalizowała próbkę {detail}.",
    ),
    (
        "each_answer",
        "Każda z odpowiedzi zawierają uzasadnienie {detail}.",
        "Każda z odpowiedzi zawiera uzasadnienie {detail}.",
    ),
    (
        "data_set",
        "Ten zestaw danych pozostają kompletny {detail}.",
        "Ten zestaw danych pozostaje kompletny {detail}.",
    ),
    (
        "test_series",
        "Seria testów wykazały tę samą usterkę {detail}.",
        "Seria testów wykazała tę samą usterkę {detail}.",
    ),
    (
        "several_notes",
        "Kilka istotnych uwag zostały pominięte {detail}.",
        "Kilka istotnych uwag zostało pominiętych {detail}.",
    ),
    (
        "five_people",
        "Pięcioro uczestników zgłosili zastrzeżenie {detail}.",
        "Pięcioro uczestników zgłosiło zastrzeżenie {detail}.",
    ),
    (
        "one_review",
        "Jedna z recenzji wskazywały błąd {detail}.",
        "Jedna z recenzji wskazywała błąd {detail}.",
    ),
    (
        "result_total",
        "Całość wyników potwierdzają hipotezę {detail}.",
        "Całość wyników potwierdza hipotezę {detail}.",
    ),
    (
        "document_half",
        "Połowa dokumentów wymagały korekty {detail}.",
        "Połowa dokumentów wymagała korekty {detail}.",
    ),
)

VALIDATION_SYNTAX = (
    (
        "val_member",
        "Każdy członek zespołu podpisali protokół {detail}.",
        "Każdy członek zespołu podpisał protokół {detail}.",
    ),
    (
        "val_part",
        "Część odpowiedzi zostały odrzucone {detail}.",
        "Część odpowiedzi została odrzucona {detail}.",
    ),
    (
        "val_collection",
        "Zbiór dokumentów trafiły do archiwum {detail}.",
        "Zbiór dokumentów trafił do archiwum {detail}.",
    ),
    (
        "val_none",
        "Nikt z obecnych nie zgłosili sprzeciwu {detail}.",
        "Nikt z obecnych nie zgłosił sprzeciwu {detail}.",
    ),
    (
        "val_team",
        "Ekipa techniczna usunęli awarię {detail}.",
        "Ekipa techniczna usunęła awarię {detail}.",
    ),
)

TRAIN_PUNCTUATION = (
    (
        "know_that",
        "Wiadomo że dokument jest kompletny {detail}.",
        "Wiadomo, że dokument jest kompletny {detail}.",
    ),
    (
        "if_then",
        "Jeżeli raport będzie gotowy wyślemy go {detail}.",
        "Jeżeli raport będzie gotowy, wyślemy go {detail}.",
    ),
    (
        "although",
        "Chociaż padał deszcz spotkanie się odbyło {detail}.",
        "Chociaż padał deszcz, spotkanie się odbyło {detail}.",
    ),
    (
        "when",
        "Kiedy zakończymy analizę opublikujemy wyniki {detail}.",
        "Kiedy zakończymy analizę, opublikujemy wyniki {detail}.",
    ),
    (
        "because",
        "Nie wyszliśmy ponieważ trwała burza {detail}.",
        "Nie wyszliśmy, ponieważ trwała burza {detail}.",
    ),
    (
        "which",
        "To jest raport który omawialiśmy {detail}.",
        "To jest raport, który omawialiśmy {detail}.",
    ),
    (
        "that",
        "Sądzę że ten wariant jest bezpieczny {detail}.",
        "Sądzę, że ten wariant jest bezpieczny {detail}.",
    ),
    (
        "before",
        "Zanim rozpoczniemy test sprawdzimy ustawienia {detail}.",
        "Zanim rozpoczniemy test, sprawdzimy ustawienia {detail}.",
    ),
    (
        "despite",
        "Mimo że było późno kontynuowaliśmy pracę {detail}.",
        "Mimo że było późno, kontynuowaliśmy pracę {detail}.",
    ),
    (
        "unless",
        "Nie zmienimy wersji chyba że test zawiedzie {detail}.",
        "Nie zmienimy wersji, chyba że test zawiedzie {detail}.",
    ),
    (
        "so_that",
        "Zapisz plik tak aby wynik był powtarzalny {detail}.",
        "Zapisz plik tak, aby wynik był powtarzalny {detail}.",
    ),
    (
        "whereas",
        "Pierwszy test przeszedł podczas gdy drugi zawiódł {detail}.",
        "Pierwszy test przeszedł, podczas gdy drugi zawiódł {detail}.",
    ),
    (
        "despite_fact",
        "Pomimo że termin minął raport przyjęto {detail}.",
        "Pomimo że termin minął, raport przyjęto {detail}.",
    ),
    (
        "whether",
        "Nie wiem czy serwer działa {detail}.",
        "Nie wiem, czy serwer działa {detail}.",
    ),
    (
        "who",
        "Badacz który prowadził test sporządził notatkę {detail}.",
        "Badacz, który prowadził test, sporządził notatkę {detail}.",
    ),
)

VALIDATION_PUNCTUATION = (
    (
        "val_where",
        "Tam gdzie kończy się ścieżka ustawiono znak {detail}.",
        "Tam, gdzie kończy się ścieżka, ustawiono znak {detail}.",
    ),
    (
        "val_even_if",
        "Nawet jeśli wynik się zmieni zachowamy raport {detail}.",
        "Nawet jeśli wynik się zmieni, zachowamy raport {detail}.",
    ),
    (
        "val_after",
        "Po tym jak test się zakończył zapisano log {detail}.",
        "Po tym, jak test się zakończył, zapisano log {detail}.",
    ),
    (
        "val_though",
        "Choć zadanie było trudne ukończono je {detail}.",
        "Choć zadanie było trudne, ukończono je {detail}.",
    ),
    (
        "val_as_long",
        "Dopóki system działa nie zmieniamy konfiguracji {detail}.",
        "Dopóki system działa, nie zmieniamy konfiguracji {detail}.",
    ),
)

TRAIN_DETAILS = (
    "przed południem",
    "w pierwszym etapie",
    "podczas poniedziałkowej narady",
    "po dokładnej analizie",
    "bez dodatkowych opóźnień",
    "zgodnie z harmonogramem",
    "w zamkniętym obiegu",
    "na początku tygodnia",
    "przed końcem dnia",
    "w obecnej wersji",
    "po krótkiej przerwie",
    "w ramach przeglądu",
    "podczas ostatniej sesji",
    "w głównym oddziale",
    "na potrzeby audytu",
    "po ponownym sprawdzeniu",
    "w trybie roboczym",
    "dla całego zespołu",
    "w ustalonym terminie",
    "bez zmiany zakresu",
)

VALIDATION_DETAILS = (
    "pod koniec miesiąca",
    "w osobnym przebiegu",
    "po zamknięciu formularza",
    "w trakcie kontroli",
    "dla komisji odbiorczej",
    "przed następną rundą",
    "w archiwalnej wersji",
    "na oddzielnym stanowisku",
    "po zatwierdzeniu planu",
    "w krótkim raporcie",
    "bez udziału obserwatorów",
    "w wyznaczonym oknie",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    generate(args.output)
    return 0


def generate(output: Path) -> None:
    train = _generate_split("train")
    validation = _generate_split("validation")
    validate_finetuning_records(train, expected_split="train")
    validate_finetuning_records(validation, expected_split="validation")
    output.mkdir(parents=True, exist_ok=True)
    train_path = output / "train.jsonl"
    validation_path = output / "validation.jsonl"
    _write_jsonl(train_path, train)
    _write_jsonl(validation_path, validation)
    manifest = build_finetuning_manifest(
        validate_finetuning_records(train, expected_split="train"),
        validate_finetuning_records(validation, expected_split="validation"),
        train_sha256=_digest(train_path),
        validation_sha256=_digest(validation_path),
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _generate_split(split: Split) -> list[dict[str, object]]:
    people = TRAIN_PEOPLE if split == "train" else VALIDATION_PEOPLE
    inflection_templates = (
        TRAIN_INFLECTION_TEMPLATES
        if split == "train"
        else VALIDATION_INFLECTION_TEMPLATES
    )
    syntax_templates = TRAIN_SYNTAX if split == "train" else VALIDATION_SYNTAX
    punctuation_templates = (
        TRAIN_PUNCTUATION if split == "train" else VALIDATION_PUNCTUATION
    )
    details = TRAIN_DETAILS if split == "train" else VALIDATION_DETAILS
    records: list[dict[str, object]] = []
    for person in people:
        for template_id, template, form_name, feature in inflection_templates:
            correct_form = getattr(person, form_name)
            source = template.format(name=person.nominative)
            start = source.index(person.nominative)
            end = start + len(person.nominative)
            candidates = (
                FiniteCandidate(
                    "unchanged-form",
                    start,
                    end,
                    person.nominative,
                    person.nominative,
                    ("nominative",),
                ),
                FiniteCandidate(
                    "correct-form",
                    start,
                    end,
                    correct_form,
                    person.nominative,
                    (feature,),
                ),
            )
            records.append(
                _candidate_record(
                    split,
                    source,
                    candidates,
                    template_id=f"{split}_inflection_{template_id}",
                    transformation_id=f"inflection-{feature}-proper-name-v1",
                    entity=(start, end, person.nominative, person.identity),
                )
            )
    for category, templates in (
        ("syntax", syntax_templates),
        ("punctuation", punctuation_templates),
    ):
        for template_id, source_template, target_template in templates:
            for detail in details:
                records.append(
                    _corrected_record(
                        split,
                        category,
                        source_template.format(detail=detail),
                        target_template.format(detail=detail),
                        template_id=f"{split}_{category}_{template_id}",
                        transformation_id=f"{category}-{template_id}-v1",
                    )
                )
    records.extend(_no_change_records(split, people, details))
    expected = 1_200 if split == "train" else 240
    if len(records) != expected:
        raise RuntimeError(
            f"generated {len(records)} records for {split}, expected {expected}"
        )
    return sorted(records, key=lambda record: str(record["id"]))


def _no_change_records(
    split: Split, people: tuple[Person, ...], details: tuple[str, ...]
) -> list[dict[str, object]]:
    templates = _negative_templates(split)
    records: list[dict[str, object]] = []
    required = 300 if split == "train" else 60
    for index in range(required):
        template_id, template, tags, focus = templates[index % len(templates)]
        occurrence = index // len(templates)
        detail = details[occurrence % len(details)]
        person = people[occurrence % len(people)]
        text = template.format(
            detail=detail,
            name=person.instrumental,
            nominative=person.nominative,
            number=1000 + index,
            url=f"https://example.invalid/{split}/{index + 1}",
        )
        entity = None
        for surface in (person.instrumental, person.nominative):
            if surface in text:
                start = text.index(surface)
                entity = (start, start + len(surface), surface, person.identity)
                break
        records.append(
            _corrected_record(
                split,
                "no_change",
                text,
                text,
                template_id=f"{split}_negative_{template_id}",
                transformation_id=f"protected-negative-{template_id}-v1",
                tags=tags,
                focus=focus,
                entity=entity,
            )
        )
    return records


def _negative_templates(
    split: Split,
) -> tuple[tuple[str, str, tuple[str, ...], str], ...]:
    prefix = "roboczym" if split == "train" else "kontrolnym"
    return (
        (
            "inflected_name",
            "Rozmawialiśmy z {name} w trybie " + prefix + ".",
            ("correct-inflection", "proper-name"),
            "inflection",
        ),
        (
            "proper_name",
            "{nominative} prowadzi spotkanie {detail}.",
            ("proper-name",),
            "inflection",
        ),
        (
            "marked_order",
            "Dopiero {detail} komisja podała wynik.",
            ("marked-word-order",),
            "syntax",
        ),
        (
            "punctuation",
            "Jeśli wszystko działa, raport zostaje bez zmian {detail}.",
            ("correct-punctuation",),
            "punctuation",
        ),
        (
            "number",
            "Raport zawiera dokładnie {number} wpisów {detail}.",
            ("number",),
            "syntax",
        ),
        (
            "url",
            "Podręcznik wdrożeniowy wskazuje stronę {url} jako źródło.",
            ("url",),
            "punctuation",
        ),
        (
            "quotation",
            "W protokole zapisano zwrot „wynik jest poprawny” {detail}.",
            ("quotation", "correct-punctuation"),
            "punctuation",
        ),
        (
            "name_quote",
            "{nominative} użył zwrotu „sprawdzę raport” {detail}.",
            ("proper-name", "quotation"),
            "punctuation",
        ),
        (
            "correct_case",
            "Przy zadaniu współpracowano z {name} {detail}.",
            ("correct-inflection", "proper-name"),
            "inflection",
        ),
        (
            "number_quote",
            "Pole „limit” ma wartość {number} {detail}.",
            ("number", "quotation"),
            "syntax",
        ),
        (
            "url_quote",
            "Adres „{url}” zapisano poprawnie.",
            ("url", "quotation"),
            "punctuation",
        ),
        (
            "order_emphasis",
            "Ten właśnie wariant wybrano {detail}.",
            ("marked-word-order",),
            "syntax",
        ),
        (
            "parenthetical",
            "Wynik, co ważne, pozostał stabilny {detail}.",
            ("correct-punctuation",),
            "punctuation",
        ),
        (
            "decimal",
            "Pomiar wyniósł {number},5 milimetra {detail}.",
            ("number", "correct-punctuation"),
            "punctuation",
        ),
        (
            "dash_quote",
            "Odpowiedź — „tak” — wpisano {detail}.",
            ("quotation", "correct-punctuation"),
            "punctuation",
        ),
    )


def _candidate_record(
    split: Split,
    source: str,
    candidates: tuple[FiniteCandidate, ...],
    *,
    template_id: str,
    transformation_id: str,
    entity: tuple[int, int, str, str],
) -> dict[str, object]:
    request = build_inflection_candidate_prompt_request(source, candidates)
    target = {"candidate_id": "correct-form"}
    messages = [*request.messages, {"role": "assistant", "content": _compact(target)}]
    return _record(
        split,
        "inflection",
        "inflection",
        source,
        target,
        [asdict(candidate) for candidate in candidates],
        messages,
        template_id,
        transformation_id,
        (entity,),
        ("name-inflection", "finite-candidate"),
        request.protocol_id,
    )


def _corrected_record(
    split: Split,
    category: str,
    source: str,
    target_text: str,
    *,
    template_id: str,
    transformation_id: str,
    tags: tuple[str, ...] = (),
    focus: str | None = None,
    entity: tuple[int, int, str, str] | None = None,
) -> dict[str, object]:
    selected_focus = cast(SpecialistFocus, focus or category)
    request = build_specialist_corrected_text_prompt_request(
        source, focus=selected_focus
    )
    target = {"corrected_text": target_text}
    messages = [*request.messages, {"role": "assistant", "content": _compact(target)}]
    return _record(
        split,
        category,
        selected_focus,
        source,
        target,
        [],
        messages,
        template_id,
        transformation_id,
        (entity,) if entity else (),
        tags or (f"{category}-correction",),
        request.protocol_id,
    )


def _record(
    split: Split,
    category: str,
    focus: str,
    source: str,
    target: dict[str, str],
    candidates: list[dict[str, object]],
    messages: list[dict[str, str]],
    template_id: str,
    transformation_id: str,
    entities: tuple[tuple[int, int, str, str], ...],
    tags: tuple[str, ...],
    protocol_id: str,
) -> dict[str, object]:
    suffix = _stable_suffix(source)
    return {
        "schema_version": 1,
        "id": f"ft_{split}_{category}_{suffix}",
        "split": split,
        "category": category,
        "protocol_id": protocol_id,
        "focus": focus,
        "source_text": source,
        "target": target,
        "candidates": candidates,
        "messages": messages,
        "chatml": render_bielik_chatml(messages),
        "transformation_id": transformation_id,
        "template_id": template_id,
        "entity_spans": [
            {"start": start, "end": end, "surface": surface, "identity": identity}
            for start, end, surface, identity in entities
        ],
        "tags": list(tags),
        "provenance": PROVENANCE,
        "review": REVIEW,
    }


def _stable_suffix(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(_compact(record) + "\n" for record in records), encoding="utf-8"
    )


def _digest(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
