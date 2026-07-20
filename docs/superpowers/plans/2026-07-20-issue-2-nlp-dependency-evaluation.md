# Polish NLP Dependency Evaluation Plan

**Goal:** Produce reproducible evidence for the minimum deterministic Polish NLP
dependency strategy and record the accepted architecture decision for issue #2.

**Approach:** Keep the spike under `experiments/` and run each optional candidate
in an isolated temporary environment against one versioned case manifest. Commit
only the small runner, inputs, raw JSON observations, derived measurements, and
documentation. The architecture decision selects only what the evidence supports;
it does not add production dependencies or implement production segmentation or
rules.

**Constraints:**

- Preserve the offline-only analysis boundary.
- Compare at least two viable approaches on identical positive and hard-negative
  Polish examples.
- Cover tokenization, sentence segmentation, morphology, spelling support,
  licensing, install footprint, offline behavior, Python/platform availability,
  and operational complexity.
- Use official primary references and exact package metadata; record uncertainty
  instead of inferring unverified legal or installation facts.
- Do not select an LLM backend or commit models, caches, corpora, virtual
  environments, or bulky generated artifacts.
- Keep all repository changes and the single issue commit in the issue #2
  worktree and branch.

## Task 1: Establish the experiment contract with failing tests

**Files:**

- Create: `tests/test_nlp_dependency_evaluation.py`
- Create later: `experiments/nlp_dependencies/cases.json`
- Create later: `experiments/nlp_dependencies/results.json`
- Create later: `experiments/nlp_dependencies/run_comparison.py`
- Create later: `docs/architecture/decisions/0002-polish-nlp-dependency-strategy.md`
- Modify later: `docs/architecture/README.md`

- [ ] Write standard-library tests that require a versioned case manifest, at
  least two candidate results with the same case IDs, exact environment and
  candidate versions, raw token/sentence/morphology/spelling observations,
  footprint measurements, limitations, a reproducible runner, an accepted ADR,
  and the ADR index link.
- [ ] Run `python3 -m unittest tests/test_nlp_dependency_evaluation.py -v` and
  confirm it fails because the experiment artifacts do not exist.

## Task 2: Build and run the bounded comparison

**Files:**

- Create: `experiments/nlp_dependencies/cases.json`
- Create: `experiments/nlp_dependencies/run_comparison.py`
- Create: `experiments/nlp_dependencies/results.json`
- Create: `experiments/nlp_dependencies/README.md`

- [ ] Define synthetic, project-authored Polish cases with explicit expected
  token and sentence boundaries, morphology probes, spelling probes, and
  positive versus hard-negative classification.
- [ ] Implement a standard-library experiment runner whose candidate adapters
  are selected explicitly and whose JSON output records half-open offsets into
  the original input.
- [ ] Create temporary candidate environments outside the repository, install
  pinned candidate versions, and measure installed-file and dependency-closure
  footprints without retaining the environments.
- [ ] Run every candidate against the same manifest, store compact raw results,
  and document the exact host, interpreter, commands, package versions, sources,
  observed behavior, derived comparison, limitations, and cleanup procedure.
- [ ] Run the experiment validation test and confirm the data contract passes.

## Task 3: Record and index the decision

**Files:**

- Create: `docs/architecture/decisions/0002-polish-nlp-dependency-strategy.md`
- Modify: `docs/architecture/README.md`
- Modify: `tests/test_nlp_dependency_evaluation.py`

- [ ] Record an accepted standard-library-first or minimum-dependency decision,
  its boundaries, consequences, rejected alternatives, reevaluation triggers,
  evidence links, and explicit statement that no LLM/model backend is selected.
- [ ] Add ADR-0002 to the architecture index.
- [ ] Run `python3 -m unittest tests/test_nlp_dependency_evaluation.py -v` and
  confirm all decision-contract tests pass.

## Task 4: Verify, review, and create the focused commit

**Files:** All issue #2 files above.

- [ ] Review the issue body and verify every acceptance criterion against the
  committed artifacts and fresh experiment output.
- [ ] Confirm `git diff --check`, the full standard-library test suite, and every
  configured lint, format, and type check pass; if a tool is not configured,
  record that fact rather than adding unrelated scaffolding.
- [ ] Confirm no model, cache, corpus, environment, private text, secret, or bulky
  artifact is tracked and that the diff is limited to issue #2.
- [ ] Configure the repository-local author as Paweł Cyroń using the existing
  email and create exactly one commit: `docs: evaluate Polish NLP dependencies (#2)`.

## Task 5: Deterministic result assembly

**Files:**

- Create: `experiments/nlp_dependencies/assembly.json`
- Create: `experiments/nlp_dependencies/raw/*.json`
- Modify: `experiments/nlp_dependencies/run_comparison.py`
- Modify: `experiments/nlp_dependencies/README.md`
- Modify: `tests/test_nlp_dependency_evaluation.py`

- [ ] Commit the four small canonical candidate outputs and their SHA-256 hashes.
- [ ] Add a standard-library assembly command that verifies input hashes,
  candidate identity and versions, observations, per-case scores, derived totals,
  environment metadata, install metadata, and model metadata.
- [ ] Require byte-for-byte reproduction of the committed normalized results and
  reject any raw-input drift.
- [ ] Document exact candidate-run, assembly, and comparison commands.
- [ ] Run the complete pipeline and amend the existing issue #2 commit without
  adding another commit.

## Task 6: Pin the complete candidate closures and bootstrap toolchain

**Files:**

- Create: `experiments/nlp_dependencies/closures/*.txt`
- Modify: `experiments/nlp_dependencies/assembly.json`
- Modify: `experiments/nlp_dependencies/results.json`
- Modify: `experiments/nlp_dependencies/run_comparison.py`
- Modify: `experiments/nlp_dependencies/README.md`
- Modify: `tests/test_nlp_dependency_evaluation.py`

- [ ] Bootstrap the recorded `uv 0.11.2` artifact by its SHA-256 and install
  CPython 3.12.13 into the temporary experiment directory.
- [ ] Record every resolved distribution for each candidate, including hashed
  direct wheels and exact Stanza resource and model repository revisions.
- [ ] Make candidate installation consume only the committed closure files.
- [ ] Verify closure-file hashes and exact distribution maps during assembly,
  rejecting added, removed, or version-drifted distributions.
- [ ] Re-run all candidates in fresh environments, reproduce the canonical raw
  hashes and normalized result, and amend the existing issue #2 commit.
