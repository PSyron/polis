# ADR-0023: Zachowanie przestrzeni `polis.evaluation` przez 1.0

- Status: Accepted
- Data: 2026-08-06
- Właściciel: Paweł Cyroń
- Issue: #219

## Kontekst

ADR-0019 zachował zgodność importów `polis.evaluation` w linii 0.x. Przed
wydaniem 1.0 pakiet nadal zawiera lekkie dane, walidatory i metryki potrzebne
istniejącym użytkownikom tej przestrzeni. Nie jest to jednak główny interfejs
analizy ani źródło aktywnej polityki korekty runtime'u v1.

Porządkowanie artefaktów wydania mogłoby przypadkowo usunąć albo zmienić część
tej powierzchni. Taka zmiana złamałaby importy bez jawnej migracji. Jednocześnie
historyczne korpusy i badania nie mogą stać się przez samo ich zachowanie nową
bramką jakości produktu.

## Decyzja

Do wydania 1.0 włącznie `polis.evaluation.__all__` zachowuje dokładnie, w tej
samej kolejności, następującą krotkę:

```python
(
    "BaselineResult",
    "EvaluationDataset",
    "QualityCounts",
    "SAFETY_CORPUS_ID",
    "SAFETY_CORPUS_V2_ID",
    "SAFETY_REVIEW_CHECKLIST_VERSION",
    "SAFETY_REVIEW_CHECKLIST_V2_VERSION",
    "assert_no_cross_corpus_leakage",
    "evaluate_baseline",
    "findings_snapshot_for_run",
    "load_dataset",
    "load_safety_corpus_json",
    "load_safety_corpus_xml",
    "safety_corpus_digest",
    "safety_entity_catalog_ids",
    "select_safety_cases_for_purpose",
    "validate_dataset",
    "validate_safety_corpus",
)
```

Wheel i sdist dostarczają ten moduł wraz z `dataset.py`, `metrics.py`,
`safety_corpus.py`, `correction_corpus.py` oraz
`datasets/v1/cases.json`. Zawierają również ten ADR jako część jawnie
weryfikowanej granicy dystrybucji.

Zachowanie tej przestrzeni jest zobowiązaniem zgodności importów. Nie zmienia
runtime'u, nie rozszerza publicznego API głównego analizatora i nie włącza
historycznych korpusów jako bramki jakości v1. Aktywny runtime v1 nadal używa
wyłącznie konserwatywnego korpusu regresji dziesięciu reguł, z bliskimi
negatywami i trzema przypadkami wstrzymania korekty.

## Konsekwencje

- Użytkownicy mogą nadal importować wszystkie wymienione symbole przez 1.0.
- Testy artefaktów i instalacji izolowanej odrzucają brakujący, dodatkowy albo
  przestawiony eksport oraz brak wymaganych plików dystrybucji.
- Przyszłe usunięcie, deprecjacja albo zmiana kolejności wymaga osobnego issue,
  planu migracji i kolejnego ADR-u.
- Ten ADR nie zmienia danych korpusów, zachowania reguł ani zamrożonych dowodów.

## Rozważone alternatywy

- **Zachować tylko `load_dataset` i `validate_dataset`.** Odrzucono, ponieważ
  zawęża istniejącą powierzchnię bez migracji.
- **Uczynić `polis.evaluation` głównym API produktu.** Odrzucono, ponieważ
  głównym API pozostają `polis` i `polis.core`.
- **Użyć zachowanych korpusów jako dodatkowej bramki v1.** Odrzucono, ponieważ
  zgodność importów nie zmienia aktywnego zakresu konserwatywnego runtime'u.
