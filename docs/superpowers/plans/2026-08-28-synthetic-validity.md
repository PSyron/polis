# Plan implementacji: wiarygodny profil benchmarku syntetycznego

## Goal

Zrealizować kryteria issue #452: dodać jawny, walidowany profil przypadków do
benchmarku hybrydowego Qwen, który korzysta wyłącznie z odtwarzalnych,
kontrolowanych par źródłowych i nie zmienia bitowo domyślnego generatora v1.
Profil ma odrzucać mutacje w cytatach/literałach, przypadki konfliktowe i
abstencje, ograniczać zgodę do jednej zmiany czynnika, zachować kontekst
fleksyjny oraz przyjmować tylko regułowe interpunkcje i bezpieczne zmiany
diakrytyczne.

## Architecture

- `source_texts()` zachowa dotychczasową kolejność i wartości wejściowe, ale
  do `SourceText` doda jawne metadane przypadku oraz zweryfikowaną, pojedynczą
  parę `error -> correct`, jeśli jej finding rekonstruuje tekst poprawny.
- `generate(profile="legacy")` pozostanie dotychczasową ścieżką i zachowa hash
  bajtów dla `seed=426, count=5000`; `profile="validated"` będzie osobną,
  kontrolowaną ścieżką bez zgadywania nowych mutacji na podstawie samego lematu.
- Walidacja kontrolowanej pary będzie wymagała dokładnego zakresu `[start, end)`
  i sprawdzenia rekonstrukcji. Pary z wieloma findingami, niespójnym tekstem,
  chronionym stratum albo nieobsługiwaną klasą pozostaną poza profilem.
- Czysta funkcja walidacji pojedynczej edycji będzie porównywała strukturę
  przedrostka, zakres i przyrostek zamiast `SequenceMatcher`, więc ocena nie
  będzie odrzucała poprawnych zmian zawierających wspólne podciągi.
- Deterministyczny podział rozwojowy/testowy będzie grupował po
  `source_case_id` (i tekście źródłowym), aby ten sam przypadek nie przeciekał
  między splitami.

## Tech Stack

- Python 3.12+; `dataclass(frozen=True, slots=True)` dla wewnętrznych modeli.
- Istniejące `pytest`, `ruff`, `mypy` i opcjonalny Morfeusz pozostają narzędziami
  repozytorium. Profil walidowany nie dodaje zależności od modelu, sieci ani
  runtime'u Qwen.
- Wszystkie polecenia uruchamiane przez `uv run --locked` w worktree.

## Spec

- GitHub issue: #452 `Urealnij korpus syntetyczny i walidację benchmarku
  hybrydowego`.
- Kontrakty źródeł i splitów: `docs/evaluation-dataset.md` oraz
  `docs/project/rule-coverage.md`.
- Zakres domyślny: `generate(seed=426, count=5000)` musi pozostać identyczny
  bajtowo (`sha256=d1cd75a9289b12d6913ff4f9912d27f83936ce29bb743a5c13e23796b7d7b1d0`).
- Profil walidowany ma być rozwojowy, jawnie wersjonowany w manifeście i nadal
  `holdout: false`; nie wolno odczytywać ani zmieniać zamrożonych holdoutów.

## Global constraints

- Nie wysyłać analizowanego tekstu do sieci i nie wiązać `core` z Qwenem.
- Nie używać `_ACTIVE_POLICY_ENTRIES`, nie zmieniać runtime'u korekt ani nie
  awansować korpusu syntetycznego do niezależnego holdoutu.
- Zachować istniejące API i testy profilu legacy; nowe odrzucenia mają być
  obserwowalne przez osobny profil, nie przez ciche przepisanie historii.
- Zakresy są półotwarte `[start, end)` i muszą wskazywać dokładny tekst
  błędny. Pary nieprzechodzące kontroli pozostają odrzucone, nie poprawiane
  heurystycznie.

## Tasks

### Task 1: Zweryfikowany model źródła i protected spans

**Files:** `src/polis/evaluation/_synthetic_corpus_sources.py`,
`tests/test_synthetic_corpus.py`, nowy test jakości źródeł.

- Najpierw dodać czerwone testy dla metadanych `kind`, `phenomenon`,
  `shape_strata`, `pair_id`, findingu oraz zakresów cytatu/backticka.
- Sparować rekordy `error` i `correct` wyłącznie po `pair_id`; zaakceptować
  tylko jedną findingową rekonstrukcję, która daje dokładny tekst poprawny.
- Udostępnić niemutowalny helper protected spans i testować wykluczenie tekstu
  w cytacie/literale bez zmiany legacy outputu.

### Task 2: Kontrolowany profil czterech klas

**Files:** `src/polis/evaluation/_synthetic_corpus_candidates.py`,
`src/polis/evaluation/synthetic_corpus.py`, testy generatora.

- Dodać jawny profil `validated` obok `legacy`, bez zmiany domyślnej selekcji.
- Budować kandydatów z ręcznie zweryfikowanych par: agreement tylko przy jednej
  zmianie tokenu, case tylko dla `inflection`/`rection`, punctuation tylko dla
  findingu z `rule_family` interpunkcyjnym i zmianą znaku, diacritics tylko dla
  jednej zmiany znaku z zachowaną bazą Unicode.
- Odrzucić protected spans, `quotation-or-literal`, `conflict-or-abstention`,
  `kind != correct`, brak pary, wiele findingów i niespójną rekonstrukcję.
- Dodać testy, że profil ma wszystkie dostępne klasy, nie zawiera znanych
  przykładów „Cytat ...”, nie zawiera lexicalnego `potu/potem` i zachowuje
  dokładną odwracalność.

### Task 3: Strukturalna walidacja edycji i splitów

**Files:** nowy moduł `src/polis/evaluation/_synthetic_corpus_validation.py`,
`tests/test_synthetic_validation.py`.

- Dodać typowane funkcje `validate_single_edit`, `assert_source_disjoint` oraz
  deterministyczny `split_source_disjoint`.
- Testować podciąg `najstarsze -> starym`, edycje zero-width, zakresy Unicode,
  odrzucenie zmiany poza zakresem i brak wspólnego `source_case_id`/tekstu
  między splitami.

### Task 4: Manifest i dokumentacja profilu

**Files:** `src/polis/evaluation/synthetic_corpus.py`,
`docs/evaluation-dataset.md`, testy manifestu.

- Wersjonować profil w manifeście bez zmiany `generator_version` i kształtu
  manifestu legacy; jawnie zapisać `profile`, coverage, odrzucone powody i
  status rozwojowy profilu walidowanego.
- Udokumentować komendy, ograniczoną liczność profilu oraz fakt, że nie jest to
  miara jakości ani holdout.
- Dodać test stałego SHA legacy i test różnicy metadanych profili.

### Task 5: Weryfikacja

- Uruchomić testy regresyjne generatora i walidacji.
- Uruchomić `uv run --locked --extra dev ruff check .`,
  `uv run --locked --extra dev ruff format --check .`,
  `uv run --locked --extra dev mypy .` oraz pełny `pytest`.
- Sprawdzić diff i status worktree; nie modyfikować pre-existing `.omo/` w
  checkout głównym. Zatrzymać się przed push/merge i przekazać branch oraz
  commit do dalszego review.

## Testing strategy

- Najpierw każdy nowy test uruchomić osobno w stanie czerwonym.
- Po implementacji uruchomić `uv run --locked --extra dev pytest
  tests/test_synthetic_corpus.py tests/test_synthetic_validation.py -q`.
- Na końcu wykonać pełny zestaw jakości repozytorium i zachować wyniki w
  przekazaniu do issue #452.
