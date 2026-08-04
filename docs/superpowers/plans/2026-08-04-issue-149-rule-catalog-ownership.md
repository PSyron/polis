# Issue #149: plan decyzji o własności katalogu reguł

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zamknąć issue #149 zaakceptowanym ADR-em, który definiuje własność
katalogu reguł, minimalne metadane, stabilność, pierwszeństwo wyboru źródeł,
zgodność konfiguracji i rozdział od polityki automatycznych poprawek.

**Architecture:** Warstwa `polis.rules` jest właścicielem kuratorowanego
katalogu standardowych źródeł, a composition root analizatora składa z niego
efektywny rejestr. Konfiguracja źródeł jest filtrem wykonania niezależnym od
wersjonowanej polityki automatycznych poprawek; katalog nie przenosi uprawnień
polityki. To issue zapisuje wyłącznie decyzję i nie dodaje typów ani zachowania
runtime'u.

**Tech Stack:** Markdown, Python 3.12+, pytest, Ruff, mypy, Git.

## Global Constraints

- Zmień wyłącznie dokumentację decyzji, indeks architektury, inwentarz #148,
  plan i testy integralności dokumentacji.
- Nie zmieniaj kodu produkcyjnego, publicznego API, konfiguracji runtime'u,
  rejestracji reguł ani polityki automatycznych poprawek.
- Nie uruchamiaj ani nie modyfikuj modeli, korpusów, holdoutów i zamrożonych
  raportów.
- Zachowaj zgodność konfiguracji category-only i dokładną tożsamość polityki
  `(source, category, operation, behavior_version, source_policy_version)`.
- Jeden issue daje jeden skupiony commit odnoszący się do #149 i jeden osobny
  PR; Paweł Cyroń pozostaje jedynym wskazywanym autorem.

---

### Task 1: Zapisz i zweryfikuj decyzję katalogu

**Files:**

- Create: `docs/architecture/decisions/0021-rule-catalog-ownership.md`
- Modify: `docs/architecture/README.md`
- Modify: `docs/architecture/rule-catalog-inventory.md`
- Modify: `tests/test_architecture_policy.py`
- Modify: `tests/test_rule_catalog_inventory.py`

**Interfaces:**

- Consumes: snapshot 12 źródeł z #148, ADR-0008, ADR-0018, ADR-0020 oraz
  obecne zachowanie `RuleRegistration` i `AnalysisOptions.categories`.
- Produces: niezmienny ADR-0021 i sprawdzalne powiązania dokumentacyjne dla
  implementacyjnych dzieci #150-#155.

- [ ] **Step 1: Dodaj zawodzący test integralności decyzji**

  Rozszerz testy tak, aby wymagały dwudziestu jeden zaakceptowanych ADR-ów,
  wpisu ADR-0021 w indeksie oraz dwukierunkowego powiązania ADR-u z inwentarzem
  #148. Test ma sprawdzać strukturę i istnienie referencji, a nie kopiować
  treść decyzji.

- [ ] **Step 2: Uruchom test i potwierdź RED**

  Run:

  ```console
  uv run --locked --extra dev pytest -q \
    tests/test_architecture_policy.py tests/test_rule_catalog_inventory.py
  ```

  Expected: FAIL, ponieważ ADR-0021 i jego wpis w indeksie jeszcze nie istnieją.

- [ ] **Step 3: Dodaj minimalny ADR i referencje**

  ADR-0021 ma rozstrzygać wszystkie dziesięć pytań z #148:

  - `polis.rules` posiada kuratorowany katalog 12 standardowych źródeł;
  - composition root posiada wyłącznie składanie katalogu i efektywnego
    rejestru;
  - minimalne metadane to `source`, `operation`, `behavior_version`, emitowane
    kategorie, domyślne włączenie, dostępność oraz opis;
  - `source` jest stabilnym kluczem, a zmiana zachowania wymaga nowego
    `behavior_version`; opis nie jest częścią tożsamości zgodności;
  - kolejność katalogu jest deterministyczną kolejnością rejestracji i pozostaje
    gwarancją zgodności linii 0.x;
  - opcjonalne źródło ma jedną tożsamość niezależną od wstrzykniętego, HTTP lub
    stdio transportu, a dostępność, konfiguracja i zdrowie transportu pozostają
    odrębnymi stanami;
  - pominięte `enabled_sources` zachowuje domyślny zestaw, jawny zbiór go
    zastępuje, `disabled_sources` zawsze odejmuje, a kategorie ograniczają
    wynik; wartości nieznane, zduplikowane, niepoprawne lub niedostępne kończą
    się deterministycznym błędem bez tekstu użytkownika;
  - konfiguracja category-only zachowuje dotychczasowe zachowanie;
  - niestandardowe `RuleRegistration` pozostają zgodne w 0.x, lecz nie trafiają
    automatycznie do kuratorowanego katalogu;
  - katalog nie zawiera dyspozycji ani progów automatycznych; włączenie źródła
    nie nadaje uprawnienia, a drift dokładnej tożsamości pozostaje review-only;
  - przyszła inspekcja rozróżnia kuratorowany katalog od efektywnego rejestru;
  - dynamiczny loader pluginów i spekulacyjne profile są jawnie odrzucone.

  Dodaj ADR do indeksu i zaktualizuj końcowy status inwentarza #148 bez zmiany
  jego maszynowego snapshotu JSON.

- [ ] **Step 4: Uruchom testy właściwe dla decyzji i potwierdź GREEN**

  Run:

  ```console
  uv run --locked --extra dev pytest -q \
    tests/test_architecture_policy.py tests/test_rule_catalog_inventory.py \
    tests/test_automatic_correction_policy.py tests/test_rules.py
  ```

  Expected: PASS bez zmiany wyników rejestru i polityki.

- [ ] **Step 5: Uruchom pełną kontrolę jakości**

  Run:

  ```console
  uv run --locked --extra dev ruff check .
  uv run --locked --extra dev ruff format --check .
  uv run --locked --extra dev mypy .
  uv run --locked --extra dev pytest -q -m "not research and not slow and not model" \
    --ignore=tests/test_residual_syntax_evaluation.py
  git diff --check
  ```

  Następnie osobno uruchom pełne `pytest -q` i zapisz znaną bazową awarię
  `test_committed_sentence_report_records_non_vacuous_policy_decision`, której
  przyczyną jest niezmienny hash #75 po dodaniu metadanych w #84. Nie naprawiaj
  jej w tym issue.

- [ ] **Step 6: Niezależny review, jeden commit i PR**

  Zweryfikuj diff względem #149, poproś niezależnego reviewera o ocenę zakresu,
  popraw wszystkie ważne ustalenia, a następnie utwórz jeden commit:

  ```console
  git add docs/architecture/README.md \
    docs/architecture/decisions/0021-rule-catalog-ownership.md \
    docs/architecture/rule-catalog-inventory.md \
    docs/superpowers/plans/2026-08-04-issue-149-rule-catalog-ownership.md \
    tests/test_architecture_policy.py tests/test_rule_catalog_inventory.py
  git commit -m "docs: decide rule catalog ownership (#149)"
  ```

  Wypchnij `codex/issue-149-rule-catalog-adr`, otwórz gotowy PR z
  `Closes #149`, poczekaj na zielone CI i nie scalaj przed niezależnym review.
