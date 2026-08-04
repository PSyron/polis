# Manifest kompletnego archiwum badawczego v2

Ten manifest jest bramką bezpieczeństwa przed usuwaniem z `main`. Zapisuje
pełny stan repozytorium po scaleniu #185 i przed pierwszym porządkowaniem
powierzchni badawczej, vendorowej lub runtime'u. Archiwum nie jest gałęzią
wydawniczą i nie upoważnia do ponownego uruchamiania, generowania ani
dostrajania zamrożonych ewaluacji.

repository: PSyron/polis
branch: feature/v2-research-archive
baseline_sha: ca27d2df5416fdce24fff9f0a1b99e8c55bfe8e8
remote_ref_sha: ca27d2df5416fdce24fff9f0a1b99e8c55bfe8e8

## Zdalna gałąź i baza

Z czystego worktree wykonano kolejno:

```text
git fetch origin --prune
git rev-parse origin/main
git branch feature/v2-research-archive origin/main
git push origin feature/v2-research-archive:feature/v2-research-archive
git ls-remote --heads origin feature/v2-research-archive
```

`git rev-parse origin/main` zwróciło
`ca27d2df5416fdce24fff9f0a1b99e8c55bfe8e8`. Przed utworzeniem ref zdalny
nie istniał. Po wypchnięciu `git ls-remote --heads` zwróciło ten sam SHA dla
`refs/heads/feature/v2-research-archive`. Zgodność obu pól metadanych jest
sprawdzana przez `tests/test_v2_research_archive_manifest.py`.

## Metoda inwentaryzacji obecności

Poniższe wyniki pochodzą dokładnie z:

```text
git ls-tree -r --name-only ca27d2df5416fdce24fff9f0a1b99e8c55bfe8e8 -- <prefix>
```

Każda pozycja checklisty była obecna w drzewie bazowego commita.

- [x] `experiments/`
- [x] `data/`
- [x] `third_party/languagetool-pl/`
- [x] `src/polis/llm/`
- [x] `src/polis/evaluation/`
- [x] `docs/architecture/decisions/`
- [x] `docs/release-notes/`
- [x] `docs/superpowers/`

| Prefiks | Liczba ścieżek z `git ls-tree` |
| --- | ---: |
| `experiments/` | 108 |
| `data/` | 5 |
| `third_party/languagetool-pl/` | 429 |
| `src/polis/llm/` | 4 |
| `src/polis/evaluation/` | 9 |
| `docs/architecture/decisions/` | 21 |
| `docs/release-notes/` | 2 |
| `docs/superpowers/` | 81 |

## Zamrożone raporty, markery i manifesty

Pełne wyszukiwanie wykonano poleceniem:

```text
git ls-tree -r --name-only ca27d2df5416fdce24fff9f0a1b99e8c55bfe8e8 \
  | rg '(^|/)(holdout\.started|frozen_.*\.json|report\.json|results\.json|manifest\.json)$'
```

Wynik zawierał dokładnie te 22 ścieżki:

```text
data/finetuning/bielik_1_5b_v1/manifest.json
experiments/contextual_inflection_routing/frozen_router.json
experiments/contextual_inflection_routing/holdout.started
experiments/contextual_inflection_routing/report.json
experiments/languagetool_rule_inventory/frozen_allowlist.json
experiments/languagetool_rule_inventory/holdout.started
experiments/languagetool_rule_inventory/report.json
experiments/languagetool_stdio_session/report.json
experiments/llm_backends/results.json
experiments/nlp_dependencies/results.json
experiments/qlora_benchmark/report.json
experiments/residual_syntax_rules/frozen_rules.json
experiments/residual_syntax_rules/holdout.started
experiments/residual_syntax_rules/report.json
experiments/sentence_category_routing/report.json
experiments/sentence_safety_gate/frozen_gate.json
experiments/sentence_safety_gate/holdout.started
experiments/sentence_safety_gate/report.json
experiments/sentence_safety_gate_v2/report.json
experiments/sentence_syntax_qualification/report.json
experiments/two_pass_qwen35/report.json
third_party/languagetool-pl/manifest.json
```

Trzy zamrożone checklisty ręcznego przeglądu również istnieją w bazie i mają
następujące SHA-256 ich treści:

| Ścieżka | SHA-256 |
| --- | --- |
| `docs/evaluation-corpus-v3-review-checklist.md` | `9793329b5ee1f7f71d2de6a0e652f0a67eff5d8f795b150ba1ff91b81db94847` |
| `docs/evaluation-safety-corpus-v1-review-checklist.md` | `6aef2d479c4806be2b3f3379aad20ef2bc695c04ade93c331bb3edaacdd9fc2e` |
| `docs/evaluation-safety-corpus-v2-review-checklist.md` | `b63e8ab7beaee16984c28c80dfea84b95ba740dbb26b67248be90a8adcf3eae9` |

## Zaakceptowane ADR-y i opublikowane release notes

`git ls-tree -r --name-only` dla `docs/architecture/decisions/` zwróciło:

```text
docs/architecture/decisions/0001-python-platform-licensing-policy.md
docs/architecture/decisions/0002-polish-nlp-dependency-strategy.md
docs/architecture/decisions/0003-public-api-and-exception-contract.md
docs/architecture/decisions/0004-local-llm-backend-selection.md
docs/architecture/decisions/0005-real-local-polish-model-benchmark.md
docs/architecture/decisions/0006-local-languagetool-benchmark.md
docs/architecture/decisions/0007-vendored-polish-languagetool-module.md
docs/architecture/decisions/0008-hybrid-correction-policy.md
docs/architecture/decisions/0009-specialist-prompt-benchmark.md
docs/architecture/decisions/0010-inflection-candidate-generation.md
docs/architecture/decisions/0011-reject-bielik-1.5b-qlora.md
docs/architecture/decisions/0012-reject-constrained-qwen35-2b.md
docs/architecture/decisions/0013-reject-sentence-category-routing.md
docs/architecture/decisions/0014-qualify-broader-polish-languagetool-rules.md
docs/architecture/decisions/0015-qualify-contextual-inflection-routing.md
docs/architecture/decisions/0016-reject-qwen17-sentence-syntax-route.md
docs/architecture/decisions/0017-reviewable-residual-sentence-syntax-rules.md
docs/architecture/decisions/0018-runtime-composition-protocols.md
docs/architecture/decisions/0019-evaluation-namespace-compatibility.md
docs/architecture/decisions/0020-runtime-first-product-charter.md
docs/architecture/decisions/0021-rule-catalog-ownership.md
```

Wynik dla `docs/release-notes/`:

```text
docs/release-notes/0.1.0-erratum.md
docs/release-notes/0.1.0.md
```

## Reguła dalszych prac

Każde issue usuwające element z `main` musi wskazać #188 jako zależność,
zachować ten manifest oraz najpierw potwierdzić odpowiednią klasyfikację
chronionego dowodu. Żaden element wymieniony wyżej nie może zostać usunięty,
przeniesiony, zregenerowany ani przepisany w ramach tego issue.
