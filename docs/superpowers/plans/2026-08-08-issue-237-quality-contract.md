# Kontrakt jakości automatycznej korekty, przeglądu i abstencji — plan implementacji

> **Dla agentów wykonawczych:** WYMAGANA UMIEJĘTNOŚĆ: użyj `superpowers:subagent-driven-development` (zalecane) albo `superpowers:executing-plans`, realizując zadania po kolei. Kroki używają składni checkbox (`- [ ]`).

**Cel:** Zapisać dla issue #237 obserwowalny kontrakt trzech wyników v1 i konserwatywną ścieżkę rozwoju fleksji oraz rekcji przy aktualnym runtime obejmującym 16 źródeł.

**Architektura:** Nowy append-only ADR-0024 zastępuje nieaktualne interpretacje liczebności w starszych zapisach, ale nie modyfikuje zaakceptowanych ADR-ów ani chronionych dowodów. Kontrakt rozdziela obecne zamknięte reguły od przyszłego, kwalifikowanego dostawcy morfologii, utrzymuje dokładną tożsamość polityki automatycznej i wymusza abstencję dla niepełnych, wieloznacznych lub wersyjnie zmienionych danych.

**Stos technologiczny:** Markdown ADR, indeks architektury, Python 3.12+ z `unittest`/`pytest`, `uv`, `ruff`, `mypy`.

## Ograniczenia globalne

- Nie zmieniaj ADR-0001–ADR-0023, zamrożonych raportów, manifestów, holdoutów ani innych chronionych dowodów.
- Nie zmieniaj runtime’u, katalogu reguł, danych ewaluacyjnych ani polityki automatycznej korekty.
- Dokumentacja aktywnie utrzymywana powstaje po polsku; identyfikatory protokołów pozostają po angielsku.
- Zachowaj granice offline-only, bez modelu, Javy i sieci oraz brak korekty stylu, semantyki, intencji, czasu i aspektu.
- Zachowaj dokładną tożsamość `(source, category, operation, behavior_version, source_policy_version)`.
- Issue #237 kończy się jednym skupionym commitem odwołującym się do `#237`.

---

### Zadanie 1: Strukturalny dowód RED dla nowego zaakceptowanego ADR-u

**Pliki:**
- Modyfikacja: `tests/test_architecture_policy.py:24-36`

**Interfejsy:**
- Konsumuje: pliki `docs/architecture/decisions/*.md` o statusie `Accepted` oraz linki indeksu.
- Produkuje: strukturalną ochronę dokładnie 24 zaakceptowanych ADR-ów, z których każdy jest zindeksowany raz.

- [ ] **Krok 1: Zmień oczekiwaną liczbę zaakceptowanych ADR-ów z 23 na 24**

```python
self.assertEqual(len(accepted), 24)
```

- [ ] **Krok 2: Uruchom test i potwierdź właściwy RED**

Uruchom: `uv run --locked --extra dev pytest tests/test_architecture_policy.py -q`

Oczekiwane: FAIL wyłącznie w `test_architecture_index_covers_every_accepted_adr_exactly_once`, ponieważ istnieją jeszcze 23 zaakceptowane ADR-y.

---

### Zadanie 2: ADR-0024 i aktualny indeks architektury

**Pliki:**
- Utworzenie: `docs/architecture/decisions/0024-automatic-review-abstention-quality-contract.md`
- Modyfikacja: `docs/architecture/README.md:8-40`
- Modyfikacja: `docs/project/documentation-migration-inventory.json`

**Interfejsy:**
- Konsumuje: kontrakt ADR-0022, rzeczywisty 16-elementowy composition root z `src/polis/analyzer.py`, zakres #236 oraz politykę źródeł 1.2.
- Produkuje: zaakceptowany kontrakt jakości #237 i aktualny wpis ADR-0024 w rejestrze.

- [ ] **Krok 1: Utwórz ADR-0024 z pełną decyzją**

ADR ma zawierać:

- obserwowalne definicje automatycznej korekty, znaleziska review-only i abstencji;
- wyjaśnienie, że #237 powstało przy 10 regułach, a aktualny runtime ma 16 źródeł po #230–#235;
- rozdzielenie obecnych zamkniętych przypadków fleksji/rekcji od ogólnej zdolności morfologicznej;
- uznanie fleksji i rekcji za docelowe zdolności v1 wdrażane wyłącznie konserwatywną ścieżką B1–B5 z #236;
- obowiązkową abstencję przy wyniku nieznanym, niepełnym, wieloznacznym, konfliktowym albo niezgodnym wersyjnie;
- niezmienną tożsamość polityki i wszystkie granice produktu;
- konsekwencje, alternatywy oraz jawne zastąpienie wyłącznie nieaktualnych interpretacji liczebności, bez edycji wcześniejszych ADR-ów.

- [ ] **Krok 2: Dodaj dokładnie jeden wiersz ADR-0024 do indeksu i popraw bieżącą liczbę źródeł z 13 na 16**

```markdown
| [ADR-0024](decisions/0024-automatic-review-abstention-quality-contract.md) | Zaakceptowany | Kontrakt automatycznej korekty, przeglądu i abstencji dla jakości v1 |
```

- [ ] **Krok 3: Uruchom test i potwierdź GREEN**

Uruchom: `uv run --locked --extra dev pytest tests/test_architecture_policy.py -q`

Oczekiwane: exit 0, 13 testów lub bieżąca liczba testów z 54 subtestami.

- [ ] **Krok 4: Sklasyfikuj nowy ADR i plan jako chronione rekordy**

Dodaj dokładne ścieżki ADR-0024 oraz tego planu odpowiednio do reguł
`accepted-architecture-decisions` i `superpowers-history` w
`docs/project/documentation-migration-inventory.json`.

Uruchom: `uv run --locked --extra dev pytest tests/test_documentation_migration_inventory.py::test_production_inventory_protects_immutable_and_upstream_documents -q`

Oczekiwane: exit 0; nowy zaakceptowany ADR ma dyspozycję
`retain_historical_evidence`.

---

### Zadanie 3: QA semantyczne i pełne bramki jakości

**Pliki:**
- Weryfikacja: `docs/architecture/decisions/0024-automatic-review-abstention-quality-contract.md`
- Weryfikacja: `docs/architecture/README.md`
- Weryfikacja: `tests/test_architecture_policy.py`

**Interfejsy:**
- Konsumuje: kryteria akceptacji #237.
- Produkuje: zapisane dowody spełnienia każdego kryterium i braku regresji chronionych rekordów.

- [ ] **Krok 1: Przeczytaj cały ADR i sprawdź kryteria jeden po drugim**

Uruchom: `sed -n '1,260p' docs/architecture/decisions/0024-automatic-review-abstention-quality-contract.md`

Oczekiwane: każda definicja ma obserwowalny wynik, a żadna część nie obiecuje szerokiej poprawności morfologicznej bez kwalifikacji.

- [ ] **Krok 2: Udowodnij brak zmian w zaakceptowanych ADR-ach**

Uruchom: `git diff --exit-code origin/main -- docs/architecture/decisions/0001-python-platform-licensing-policy.md docs/architecture/decisions/0002-polish-nlp-dependency-strategy.md docs/architecture/decisions/0003-public-api-and-exception-contract.md docs/architecture/decisions/0004-local-llm-backend-selection.md docs/architecture/decisions/0005-real-local-polish-model-benchmark.md docs/architecture/decisions/0006-local-languagetool-benchmark.md docs/architecture/decisions/0007-vendored-polish-languagetool-module.md docs/architecture/decisions/0008-hybrid-correction-policy.md docs/architecture/decisions/0009-specialist-prompt-benchmark.md docs/architecture/decisions/0010-inflection-candidate-generation.md docs/architecture/decisions/0011-reject-bielik-1.5b-qlora.md docs/architecture/decisions/0012-reject-constrained-qwen35-2b.md docs/architecture/decisions/0013-reject-sentence-category-routing.md docs/architecture/decisions/0014-qualify-broader-polish-languagetool-rules.md docs/architecture/decisions/0015-qualify-contextual-inflection-routing.md docs/architecture/decisions/0016-reject-qwen17-sentence-syntax-route.md docs/architecture/decisions/0017-reviewable-residual-sentence-syntax-rules.md docs/architecture/decisions/0018-runtime-composition-protocols.md docs/architecture/decisions/0019-evaluation-namespace-compatibility.md docs/architecture/decisions/0020-runtime-first-product-charter.md docs/architecture/decisions/0021-rule-catalog-ownership.md docs/architecture/decisions/0022-conservative-v1-product-scope.md docs/architecture/decisions/0023-evaluation-namespace-1-0.md`

Oczekiwane: exit 0 i pusty diff.

- [ ] **Krok 3: Uruchom wszystkie wymagane bramki**

Uruchom kolejno:

```bash
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
uv run --locked --extra dev pytest -m 'not research' -q
git diff --check
```

Oczekiwane: każde polecenie kończy się kodem 0.

---

### Zadanie 4: Niezależny review i skupiony commit

**Pliki:**
- Review: pełny diff issue #237 oraz artefakty QA.

**Interfejsy:**
- Konsumuje: wszystkie kryteria #237, wynik testów i dowód ochrony historii.
- Produkuje: bezwarunkową akceptację niezależnego review oraz jeden atomowy commit.

- [ ] **Krok 1: Zleć niezależny review bez prawa do edycji**

Reviewer ma sprawdzić kompletność kontraktu, zgodność z #236/ADR-0022, brak szerokiej obietnicy morfologicznej, dokładną politykę automatyczną i brak zmian chronionych rekordów.

- [ ] **Krok 2: Napraw wyłącznie blokery odnoszące się do kryteriów #237 i ponownie uruchom dotknięte scenariusze**

Oczekiwane: reviewer zatwierdza bezwarunkowo.

- [ ] **Krok 3: Sprawdź diff i utwórz jeden commit**

```bash
git diff --check
git diff --stat
git diff
git add docs/architecture/README.md docs/architecture/decisions/0024-automatic-review-abstention-quality-contract.md docs/project/documentation-migration-inventory.json docs/superpowers/plans/2026-08-08-issue-237-quality-contract.md tests/test_architecture_policy.py
git commit -m "docs(architecture): define v1 quality outcomes (#237)"
```

- [ ] **Krok 4: Potwierdź commit i czysty worktree**

Uruchom: `git log -1 --oneline && git status --short --branch`

Oczekiwane: jeden commit #237 ponad `origin/main`, brak niezacommitowanych plików.
