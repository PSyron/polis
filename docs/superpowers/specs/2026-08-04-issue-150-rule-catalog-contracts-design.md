# Projekt niezmiennych kontraktów katalogu reguł dla issue #150

## Cel

Issue #150 wprowadza wyłącznie wewnętrzne, typowane kontrakty metadanych i
katalogu reguł zaakceptowane w ADR-0021. Kontrakty mają umożliwić późniejsze
migracje źródeł w #152 i #153, nie zmieniając jeszcze composition root,
wykonania rejestru, wyników analizy, publicznej konfiguracji ani polityki
automatycznych poprawek.

## Granica zakresu

Implementacja pozostaje w warstwie `polis.rules`. Powstaje osobny moduł
`polis.rules.catalog`, a jego typy są ponownie eksportowane wyłącznie z
wewnętrznego pakietu `polis.rules`. Nie trafiają do publicznego `polis` ani do
`polis.core`.

#150 nie tworzy jeszcze produkcyjnej listy 12 źródeł z inwentarza #148 i nie
zmienia `Analyzer._make_default_registry()`. Rejestracja dziesięciu źródeł
wbudowanych należy do #152, a dwóch źródeł opcjonalnych do #153. Wybór źródeł,
konfiguracja `enabled_sources` i `disabled_sources` oraz serializacja należą do
#151, które nadal jest zablokowane przez #90. Inspekcja i dokumentacja dla CLI
należą do #154.

## Typy

### `RuleAvailability`

Wewnętrzny enum tekstowy ma dokładnie dwie wartości:

- `BUILT_IN = "built_in"` — implementacja jest częścią instalacji Polis;
- `REQUIRES_CONFIGURATION = "requires_configuration"` — uruchomienie źródła
  wymaga jawnie skonfigurowanego producenta lokalnego.

Jest to statyczna klasa dostępności źródła. Nie opisuje, czy transport został
właśnie skonfigurowany, uruchomiony lub uznany za zdrowy. Te stany pozostają w
composition root i późniejszych migracjach #152/#153.

### `RuleMetadata`

`RuleMetadata` jest dataclassą `frozen=True, slots=True` z polami:

- `source: Source`;
- `operation: str`;
- `behavior_version: str`;
- `categories: frozenset[Category]`;
- `enabled_by_default: bool`;
- `availability: RuleAvailability`;
- `description: str`.

`source` musi mieć `SourceKind.RULE`. Kategorie oznaczają pełny zbiór kategorii,
które źródło może emitować; nie są zakresem wykonawczym
`RuleRegistration.categories`. Zbiór kategorii musi być niepustym
`frozenset[Category]`, aby nie ukrywać normalizacji ani kolejności na granicy
kontraktu.

`operation`, `behavior_version` i `description` muszą być niepustymi napisami
bez otaczających białych znaków. #150 nie narzuca nowej gramatyki ani regexu
dla wersji zachowania, ponieważ ADR-0021 zatwierdza stabilność i jawność wersji,
ale nie zatwierdza konkretnego formatu semantycznego. `enabled_by_default` musi
być dokładną wartością `bool`, a `availability` wartością `RuleAvailability`.

Nie powstaje zależność między `enabled_by_default` i `availability`. Są to
odrębne fakty zgodnie z ADR-0021; zasady składania efektywnego rejestru należą
do późniejszych issue.

### `RuleCatalog`

`RuleCatalog` jest niezmiennym obiektem ze slotami. Konstruktor przyjmuje
wyłącznie uporządkowaną krotkę `tuple[RuleMetadata, ...]`, materializuje ją bez
sortowania i atomowo waliduje wszystkie wpisy przed zapisaniem stanu.

Publiczna powierzchnia wewnętrzna katalogu zawiera tylko:

```python
def entries(self) -> tuple[RuleMetadata, ...]: ...
def get(self, source: Source) -> RuleMetadata | None: ...
```

`entries()` zachowuje dokładną kolejność konstrukcji. `get()` zwraca wpis dla
dokładnego `Source` albo `None`. Przy skali 12 źródeł lookup może przejść po
niezmiennej krotce; #150 nie dodaje ukrytego mutowalnego indeksu ani
przedwczesnej abstrakcji wydajnościowej.

Pusty katalog jest poprawną wartością kontraktu. Kompletność 12 standardowych
źródeł jest wymaganiem migracji i końcowej weryfikacji #152–#155, a nie ogólnej
struktury danych.

## Walidacja i błędy

Moduł definiuje:

- `RuleCatalogError(ValueError)` — wspólny bezpieczny błąd kontraktu;
- `InvalidRuleMetadataError(RuleCatalogError)` — niepoprawne pole metadanych;
- `DuplicateRuleMetadataError(RuleCatalogError)` — powtórzony `source`.

Każde niepoprawne pole kończy się deterministycznym błędem wskazującym nazwę
pola. Jeśli istnieje poprawny, bezpieczny identyfikator `rule:`, komunikat może
go zawierać. Duplikat wskazuje wyłącznie powtórzony `source`. Konstruktor
katalogu odrzuca listy, zbiory, generatory i inne kontenery, dzięki czemu nie
akceptuje niejawnej lub niestabilnej kolejności.

Żaden interfejs katalogu nie przyjmuje analizowanego tekstu, implementacji
reguły, producenta ani transportu. Komunikaty nie mogą zawierać reprezentacji
całego wadliwego obiektu; ograniczają się do bezpiecznej nazwy pola i
identyfikatora źródła. Walidacja następuje przed zapisaniem stanu katalogu, więc
nie powstaje częściowy katalog.

## Zgodność

`RuleRegistration`, `DeterministicRuleRegistry`, `VersionedRule`,
`source_behavior()` oraz `SourceBehavior` pozostają bez zmian. Katalog nie
odczytuje ani nie tworzy wpisów `_ACTIVE_POLICY_ENTRIES` i nie zawiera progów,
dyspozycji ani wersji polityki automatycznej korekty.

Nie zmieniają się:

- kolejność ani domyślne wykonanie reguł;
- znaleziska, identyfikatory, kategorie i offsety;
- serializacja JSON i publiczne eksporty;
- wymagania instalacyjne i zachowanie offline;
- żaden raport, korpus, model, holdout ani zamrożony dowód.

## Testy

Nowy `tests/test_rule_catalog.py` prowadzi implementację w TDD i sprawdza:

- niezmienność, sloty i zachowanie pełnej wartości `RuleMetadata`;
- zachowanie kolejności oraz dokładny lookup katalogu;
- poprawny pusty katalog;
- duplikaty źródeł;
- niepoprawny rodzaj źródła, puste lub nieprzycięte napisy, pusty albo
  niepoprawny zbiór kategorii, nie-boolean default i niepoprawną dostępność;
- odrzucenie nieuporządkowanych lub niejawnie materializowanych kontenerów;
- komunikaty błędów ograniczone do bezpiecznych metadanych;
- brak nowych eksportów w publicznym `polis`.

Testy regresyjne `tests/test_rules.py`, `tests/test_protocols.py`,
`tests/test_rule_catalog_inventory.py` i
`tests/test_automatic_correction_policy.py` dowodzą, że obecny rejestr,
inwentarz i polityka pozostają zgodne. Pełna weryfikacja obejmuje `pytest`,
`ruff check .`, `ruff format --check .`, `mypy .` oraz `git diff --check`.

## Odrzucone podejścia

- **Rozszerzenie `RuleRegistration`.** Mieszałoby własność katalogu z
  wykonawczym zakresem rejestracji i utrudniało oddzielenie #150 od migracji
  #152/#153.
- **Słowniki lub luźne stałe.** Nie zapewniają typowanej niezmienności ani
  atomowej walidacji.
- **Katalog fabryk reguł.** Wciągałby producentów, transporty i cykl życia do
  #150, choć należą one do composition root oraz #152/#153.
- **Równoczesna migracja 12 źródeł.** Łamałaby kolejność zależności i atomowe
  granice zaakceptowanych dzieci #97.
- **Dynamiczna kontrola zdrowia transportu.** Nie jest statyczną metadaną i
  naruszałaby niezależność katalogu od konkretnych producentów.
