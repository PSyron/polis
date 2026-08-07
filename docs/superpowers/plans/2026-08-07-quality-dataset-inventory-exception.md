# Wyjątek inwentarza aktywnego zbioru jakości Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wyłączyć dokładny prefiks aktywnego zbioru `src/polis/evaluation/datasets/quality/` z heurystyki zamrożonych dowodów bez osłabienia ochrony pozostałych danych ewaluacyjnych.

**Architecture:** Walidator zachowa obecne korzenie i nazwy chronionych artefaktów, ale przed ich klasyfikacją rozpozna jeden stały prefiks aktywnych danych produktu. Test kompletności repozytorium odwzoruje tę samą granicę, a dokumentacja jawnie rozdzieli edytowalne dane jakości od historycznych dowodów badawczych.

**Tech Stack:** Python 3.12, pytest, Ruff, mypy, walidator CLI inwentarza dokumentacji.

## Global Constraints

- Wyjątek obejmuje wyłącznie `src/polis/evaluation/datasets/quality/`.
- `src/polis/evaluation/datasets/v1/cases.json` nadal wymaga dokładnej reguły `retain_research_evidence`.
- Nie zmieniaj `_EVIDENCE_ROOTS`, `_EVIDENCE_FILENAMES` ani schematu inwentarza.
- Nie dodawaj aktywnych danych jakości do `documentation-migration-inventory.json`.
- Dodaj oba nowe dokumenty `docs/superpowers/` jako dokładne ścieżki
  `retain_historical_evidence`, zgodnie z istniejącą polityką.
- Dokumentację projektu pisz po polsku.
- Issue #229 pozostaje jednym skupionym commitem; końcowy zapis wykonaj przez amend.

---

### Task 1: Granica aktywnych danych w walidatorze i dokumentacji

**Files:**
- Modify: `scripts/validate_documentation_inventory.py:52-225`
- Modify: `tests/test_documentation_migration_inventory.py:24-477`
- Modify: `docs/project/DOCUMENTATION-ROADMAP.md:56-64`
- Modify: `docs/project/documentation-migration-inventory.json:30-120`

**Interfaces:**
- Consumes: `_required_protected_disposition(path: str) -> str | None` i produkcyjny zbiór ścieżek z `git ls-files`.
- Produces: `_ACTIVE_PRODUCT_DATA_PREFIX = "src/polis/evaluation/datasets/quality/"` oraz identyczną granicę w regresyjnej kontroli kandydatów testowych.

- [ ] **Step 1: Write the failing tests**

Dodaj test jednostkowy importujący moduł walidatora i sprawdzający dokładną granicę:

```python
@pytest.mark.parametrize(
    "path",
    (
        "src/polis/evaluation/datasets/quality/v1/cases.json",
        "src/polis/evaluation/datasets/quality/v1/manifest.json",
    ),
)
def test_active_quality_dataset_is_not_protected_research_evidence(path: str) -> None:
    assert validator._required_protected_disposition(path) is None


def test_historical_evaluation_case_remains_protected() -> None:
    path = "src/polis/evaluation/datasets/unlisted-history/cases.json"
    assert validator._required_protected_disposition(path) == (
        "retain_research_evidence"
    )
```

W teście produkcyjnego inwentarza odfiltruj wyłącznie ścieżki rozpoczynające się od stałej `ACTIVE_PRODUCT_DATA_PREFIX`; pozostaw wszystkie inne warunki bez zmian.

- [ ] **Step 2: Run tests to verify the regression fails**

Run:

```bash
pytest tests/test_documentation_migration_inventory.py \
  -k 'active_quality_dataset or historical_evaluation_case or repository_markdown_inventory_is_complete or production_inventory_uses_exact_evidence_paths' -v
```

Expected: nowe przypadki aktywnego zbioru lub istniejąca kompletność produkcyjna zawodzą, ponieważ `cases.json` i `manifest.json` są nadal klasyfikowane jako `retain_research_evidence`.

- [ ] **Step 3: Implement the exact prefix exception**

W walidatorze dodaj stałą obok korzeni dowodów:

```python
_ACTIVE_PRODUCT_DATA_PREFIX: Final[str] = (
    "src/polis/evaluation/datasets/quality/"
)
```

Na początku `_required_protected_disposition`, przed heurystyką korzeni dowodów, dodaj:

```python
if path.startswith(_ACTIVE_PRODUCT_DATA_PREFIX):
    return None
```

W teście produkcyjnym dodaj odpowiadającą stałą:

```python
ACTIVE_PRODUCT_DATA_PREFIX = "src/polis/evaluation/datasets/quality/"
```

i ogranicz zbiór `tracked_candidates` warunkiem:

```python
if not path.startswith(ACTIVE_PRODUCT_DATA_PREFIX)
and (
    Path(path).name in PROTECTED_EVIDENCE_FILENAMES
    or Path(path).name.startswith("frozen_")
    and Path(path).suffix == ".json"
)
```

- [ ] **Step 4: Document the boundary**

Po zasadzie o zamrożonych dowodach w `DOCUMENTATION-ROADMAP.md` dopisz:

```markdown
- `src/polis/evaluation/datasets/quality/` zawiera aktywne, edytowalne dane
  produktu i nie jest klasyfikowane jako zamrożony dowód badawczy. Pozostałe
  zbiory ewaluacyjne zachowują ochronę wynikającą z dokładnych wpisów
  inwentarza.
```

Do istniejącej reguły `retain_historical_evidence` dodaj dokładne ścieżki:

```json
"docs/superpowers/plans/2026-08-07-quality-dataset-inventory-exception.md",
"docs/superpowers/specs/2026-08-07-quality-dataset-inventory-exception-design.md"
```

Nie dodawaj do inwentarza żadnej ścieżki pod
`src/polis/evaluation/datasets/quality/`.

- [ ] **Step 5: Run focused and full verification**

Run:

```bash
pytest tests/test_documentation_migration_inventory.py -v
python scripts/validate_documentation_inventory.py
ruff check .
ruff format --check .
mypy .
pytest -m "not research and not slow"
```

Expected: wszystkie polecenia kończą się kodem 0, a walidator wypisuje `documentation migration inventory is complete`.

- [ ] **Step 6: Amend the single issue commit**

Po finalnym review i manualnym QA dodaj wszystkie pliki issue #229 poza `.omo/`, sprawdź staged diff i wykonaj:

```bash
git commit --amend --no-edit
```

Expected: jeden commit z komunikatem `test(evaluation): establish editable quality protocol (#229)` i czysty indeks; `.omo/` pozostaje nieśledzone.
