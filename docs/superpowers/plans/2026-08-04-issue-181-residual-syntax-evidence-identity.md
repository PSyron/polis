# Issue #181: plan naprawy tożsamości dowodu residual-syntax

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Naprawić test zamrożonego raportu #75 tak, aby weryfikował dokładną
historyczną tożsamość dowodu i nie porównywał jej z mutowalnym źródłem na
`HEAD`.

**Architecture:** Raport, manifest `frozen_rules.json` i jednorazowy marker
`holdout.started` tworzą jeden niezmienny dowód historyczny. Test wyprowadzi
oczekiwaną tożsamość niezależnie jako literalne hashe #75, porówna z nią każdy
artefakt i zachowa wykonywalne asercje niepustej decyzji; bieżący
`src/polis/rules/syntax.py` pozostaje poza tym kontraktem.

**Tech Stack:** Python 3.12+, pytest, Ruff, mypy, Git.

## Global Constraints

- Nie uruchamiaj ponownie ewaluacji ani zużytego holdoutu residual-syntax.
- Nie zmieniaj `report.json`, `frozen_rules.json`, `holdout.started`, konfiguracji,
  ewaluatora, digestów ani `src/polis/rules/syntax.py`.
- Nie dotykaj zakresu #150, #179, #180 ani wyłączonych katalogów benchmarków.
- Zachowaj niepuste asercje decyzji i metryk development/holdout.
- Jeden issue daje jeden skupiony commit odnoszący się do #181 i osobny PR;
  Paweł Cyroń pozostaje jedynym wskazywanym autorem.

---

### Task 1: Oddziel historyczną tożsamość dowodu od bieżącego źródła

**Files:**

- Create: `docs/superpowers/plans/2026-08-04-issue-181-residual-syntax-evidence-identity.md`
- Modify: `tests/test_residual_syntax_evaluation.py`

**Interfaces:**

- Consumes: zamrożone hashe #75 zapisane w raporcie, manifeście i markerze oraz
  decyzję ADR-0017 o pozostawieniu reguł review-only.
- Produces: test, którego oczekiwanie nie zależy od mutowalnego pliku runtime'u,
  ale nadal wykrywa zmianę lub rozjazd dowolnego z trzech historycznych
  artefaktów.

- [ ] **Step 1: Potwierdź RED istniejącego testu kontraktu**

  Run:

  ```console
  uv run --locked --extra dev pytest -q \
    tests/test_residual_syntax_evaluation.py::test_committed_sentence_report_records_non_vacuous_policy_decision
  ```

  Expected: FAIL z różnicą `rules_sha256`: zamrożone `74d0b770...` wobec
  bieżącego `f63a0064...`. To jest RED błędu kontraktu: test zestawia dowód #75
  z zaakceptowaną późniejszą rewizją #84.

- [ ] **Step 2: Zaostrz test historycznej tożsamości**

  W teście zdefiniuj niezależne literalne oczekiwanie:

  ```python
  expected_evidence_identity = {
      "configuration_sha256": "6aa1cf64dc54e723cbce79b5985f751782bc312adba1c4236a70b9a74ec6c5e0",
      "evaluator_sha256": "8a905a6fffbe8239ee44c4f2c99628f7b641099bc56a799904176540b96fba38",
      "rules_sha256": "74d0b770aca6326e8625699b82bac634ddecaa005009eca5b5f8188934f086d8",
  }
  report_evidence_identity = {
      key: report[key] for key in expected_evidence_identity
  }
  assert report_evidence_identity == frozen == marker == expected_evidence_identity
  ```

  Usuń wyłącznie porównanie `rules_sha256` z bieżącym `syntax.py`. Zachowaj
  wszystkie asercje decyzji i metryk, aby test nie stał się vacuous.

- [ ] **Step 3: Potwierdź GREEN i testy skoncentrowane**

  Run:

  ```console
  uv run --locked --extra dev pytest -q \
    tests/test_residual_syntax_evaluation.py \
    tests/test_residual_syntax_rules.py \
    tests/test_automatic_correction_policy.py \
    tests/test_rules.py
  ```

  Expected: PASS; raport, manifest i marker mają jedną dokładną historyczną
  tożsamość, a zachowanie bieżących reguł pozostaje pokryte osobnymi testami.

- [ ] **Step 4: Uruchom pełną weryfikację i ochronę dowodów**

  Run:

  ```console
  uv run --locked --extra dev pytest -q
  uv run --locked --extra dev ruff check .
  uv run --locked --extra dev ruff format --check .
  uv run --locked --extra dev mypy .
  git diff --check
  git diff --exit-code main -- \
    experiments/residual_syntax_rules/report.json \
    experiments/residual_syntax_rules/frozen_rules.json \
    experiments/residual_syntax_rules/holdout.started \
    experiments/residual_syntax_rules/config.json \
    experiments/residual_syntax_rules/run_evaluation.py \
    src/polis/rules/syntax.py
  ```

  Expected: wszystkie kontrole przechodzą, a ostatnie polecenie nie pokazuje
  żadnej zmiany chronionych artefaktów ani źródła reguł.

- [ ] **Step 5: Niezależny review, jeden commit i PR**

  Poproś niezależnego reviewera o sprawdzenie diffu względem `main`, popraw
  wszystkie ważne uwagi, a następnie utwórz jeden commit:

  ```console
  git add tests/test_residual_syntax_evaluation.py \
    docs/superpowers/plans/2026-08-04-issue-181-residual-syntax-evidence-identity.md
  git commit -m "test: preserve residual syntax evidence identity (#181)"
  ```

  Wypchnij `bug/residual-syntax-evidence-identity`, otwórz gotowy PR z
  `Closes #181`, poczekaj na zielone CI i niezależny review, a następnie scal
  bez przepisywania historii.
