# ADR-0031: Zachowanie `polis.evaluation` w artefakcie dystrybucyjnym przez 1.0

- Status: Accepted
- Data: 2026-08-25
- Właściciel: Paweł Cyroń
- Issue: #432
- Zastępuje: nic; potwierdza ADR-0023

## Kontekst

Issue #432 rozważa zmniejszenie koła przez usunięcie rodziny
`polis.evaluation`. Byłaby to zmiana łamiąca: ADR-0019 zachowuje zgodność
importów w linii 0.x, a ADR-0023 utrzymuje dokładną przestrzeń nazw do wydania
1.0 włącznie. Obecna bramka `scripts/verify_distribution_install.py` sprawdza
importowalność tej przestrzeni, kolejność `__all__` i uruchomienie CLI
ewaluacji.

## Dowody

Na `main` po scaleniu #426 (`e3ee9b7353b614d8aecad48b75011eb1ddaadee2`)
zbudowano wheel i sdist poleceniem `uv build --wheel --sdist`. Oba artefakty
zawierały 50 plików pod `polis/evaluation/`; wheel miał 882178 bajtów
rozpakowanej zawartości tej przestrzeni. Weryfikator dystrybucji potwierdził
metadane MIT, licencję i wymagane importy. Trwały raport z komendami i
identyfikatorami artefaktów znajduje się w
`docs/development/issue-432-evaluation-distribution-evidence.md`.

Domknięty graf publicznego kontraktu jest następujący:

```text
polis.evaluation.__init__
├── dataset.py          → EvaluationDataset, load_dataset, validate_dataset
│                         └── polis.core → Category
├── metrics.py          → BaselineResult, QualityCounts,
│                         evaluate_baseline, findings_snapshot_for_run
│                         ├── dataset.py → EvaluationDataset, ExpectedFinding,
│                         │                 load_dataset, DATASET_PATH
│                         ├── polis.core → Category, Finding
│                         └── polis.core.models → SourceKind
└── safety_corpus.py    → 12 eksportów kontroli korpusów
                           └── correction_corpus.py → typy, walidatory i edycje
```

Pełna lista 18 eksportów, w kolejności zapisanej w ADR-0023, brzmi:

```text
BaselineResult, EvaluationDataset, QualityCounts,
SAFETY_CORPUS_ID, SAFETY_CORPUS_V2_ID,
SAFETY_REVIEW_CHECKLIST_VERSION, SAFETY_REVIEW_CHECKLIST_V2_VERSION,
assert_no_cross_corpus_leakage, evaluate_baseline, findings_snapshot_for_run,
load_dataset, load_safety_corpus_json, load_safety_corpus_xml,
safety_corpus_digest, safety_entity_catalog_ids,
select_safety_cases_for_purpose, validate_dataset, validate_safety_corpus
```

Graf jest zamknięty dla przestrzeni `polis.evaluation`: `metrics.py` korzysta
z `dataset.py`, `dataset.py` i `metrics.py` korzystają wyłącznie z istniejących
typów `polis.core`, `safety_corpus.py` korzysta z `correction_corpus.py`, a
`correction_corpus.py` nie importuje modułów ewaluacji. Zależności
`polis.core` i `polis.core.models` pozostają częścią istniejącego runtime'u i
nie są nowymi eksportami tego namespace'u.
`correction_corpus.py` oraz lekkie moduły zależne pozostają częścią
kompatybilnego grafu dystrybucji, ale nie są dodatkowymi eksportami z
`polis.evaluation.__all__`. Moduły kalibracji, holdoutu i generatora
syntetycznego są osobno wykluczane zgodnie z granicą runtime-first.

W przeszukanym repozytorium nie znaleziono zewnętrznego rejestru konsumentów;
znane użycia są w testach kontraktu, skryptach weryfikacyjnych i dokumentacji.
To nie jest dowód nieistnienia konsumentów poza repozytorium, dlatego nie
stanowi podstawy do cichego usunięcia namespace'u.

## Decyzja

Do wydania 1.0 włącznie pozostawiamy `polis.evaluation` bez zmian. Nie
wydzielamy pakietu `polis-eval`, nie usuwamy namespace'u i nie redukujemy go do
18 eksportów bez osobnego ADR-u, planu migracji oraz nowych bramek zgodności.

Ta decyzja nie zmienia runtime'u, aktywnej polityki korekty ani zawartości
zamrożonych korpusów. Potwierdza i doprecyzowuje ADR-0023; nie modyfikuje jego
niezmiennego zapisu.

## Konsekwencje

- `import polis.evaluation` oraz dokładne 18-elementowe `__all__` pozostają
  wspierane przez 1.0.
- Koszt dystrybucji pozostaje jawnie zaakceptowany i zmierzony; optymalizacja
  rozmiaru jest odroczona do osobnego, migracyjnego issue.
- Każda przyszła zmiana wymaga aktualizacji ADR-0023 przez nowy ADR,
  sprawdzenia grafu zależności i zielonych testów instalacji izolowanej.

## Bramka decyzji

Zachowanie opcji 1 z #432 jest pełnowartościowym wynikiem decyzyjnym. Kryterium
„bez cichej zmiany importu” jest spełnione, a opcje 2–4 nie są uruchamiane bez
nowej decyzji właściciela.
