# Real Local LLM Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a repeatable local benchmark that selects or rejects compact models for Polish correction before a production backend adapter is built.

**Architecture:** An experiment-only Ollama client sends the existing strict prompt to a configured localhost endpoint and validates responses through the package contract. The runner maps valid findings to the v2 E2E cases, derives quality and latency metrics, and writes local results outside version control. It never changes `Analyzer` or downloads a model itself.

**Tech Stack:** Python 3.12+, standard-library `urllib`, pytest, existing `polis.llm.contracts` validation, Ollama CLI/API.

## Global Constraints

- Work only on GitHub issue #42; #43 starts after a documented selection.
- All inference is local; the benchmark sends requests only to loopback.
- Models are explicitly installed outside the repository; do not commit weights, cache, prompts containing private text, or result artifacts.
- Candidates are Bielik 1.5B/4.5B GGUF and Qwen3 0.6B/1.7B/4B; unavailable gated models are recorded as unavailable.
- A candidate cannot be selected if it changes a corpus `negative` case or returns invalid JSON.

---

### Task 1: Define benchmark case loading and report validation

**Files:**
- Create: `experiments/real_llm_benchmark/run_benchmark.py`
- Create: `tests/test_real_llm_benchmark.py`

**Interfaces:**
- Consumes: `tests/fixtures/e2e/polish_correction_corpus.json`.
- Produces: `load_cases(path: Path) -> tuple[BenchmarkCase, ...]` and `validate_report(payload: dict[str, object]) -> None`.

- [ ] **Step 1: Write the failing test**

```python
from experiments.real_llm_benchmark.run_benchmark import load_cases

def test_loader_uses_llm_and_negative_v2_cases() -> None:
    cases = load_cases(CORPUS_PATH)
    assert {case.verification for case in cases} == {"llm_planned", "negative"}
```

- [ ] **Step 2: Verify red**

Run: `uv run --locked --extra dev pytest -q tests/test_real_llm_benchmark.py`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement minimal typed case loader and report schema validator**

Read JSON only, reject unknown verification modes and require a non-empty model identifier plus per-category metrics in every report.

- [ ] **Step 4: Verify green**

Run: `uv run --locked --extra dev pytest -q tests/test_real_llm_benchmark.py`

Expected: PASS.

### Task 2: Add a localhost-only Ollama experiment client

**Files:**
- Modify: `experiments/real_llm_benchmark/run_benchmark.py`
- Modify: `tests/test_real_llm_benchmark.py`

**Interfaces:**
- Consumes: `OllamaClient(base_url: str, model: str, timeout_seconds: float)`.
- Produces: `generate(prompt: str) -> TimedResponse` with raw text and timing fields.

- [ ] **Step 1: Write failing tests**

```python
def test_client_rejects_non_loopback_url() -> None:
    with pytest.raises(ValueError, match="loopback"):
        OllamaClient("http://example.test", "qwen3:0.6b", 10.0)
```

- [ ] **Step 2: Verify red**

Run: `uv run --locked --extra dev pytest -q tests/test_real_llm_benchmark.py`

Expected: FAIL because `OllamaClient` does not exist.

- [ ] **Step 3: Implement standard-library request handling**

Allow only `localhost`, `127.0.0.1`, and `::1`; call `/api/generate` with `stream=false`, `format="json"`, deterministic generation options, and no automatic model pull. Convert connection failures into recorded unavailable candidate status.

- [ ] **Step 4: Verify green**

Run: `uv run --locked --extra dev pytest -q tests/test_real_llm_benchmark.py`

Expected: PASS.

### Task 3: Score candidates and document reproducible execution

**Files:**
- Modify: `experiments/real_llm_benchmark/run_benchmark.py`
- Create: `experiments/real_llm_benchmark/README.md`
- Modify: `tests/test_real_llm_benchmark.py`

**Interfaces:**
- Consumes: validated findings and corpus cases.
- Produces: per-category precision/recall/F1, exact correction accuracy, JSON validity, latency, throughput, status, and a deterministic candidate ranking.

- [ ] **Step 1: Write failing scoring tests**

```python
def test_negative_finding_disqualifies_candidate() -> None:
    report = score_case(negative_case, findings=(unexpected_finding,))
    assert report.disqualified is True
```

- [ ] **Step 2: Verify red**

Run: `uv run --locked --extra dev pytest -q tests/test_real_llm_benchmark.py`

Expected: FAIL because scoring functions do not exist.

- [ ] **Step 3: Implement scorer and CLI**

Run each configured candidate over identical cases, call existing `validate_llm_response`, derive metrics, mark invalid/negative-changing runs ineligible, and write an explicitly requested output path only.

- [ ] **Step 4: Document commands**

Document manual model preparation, including a local Modelfile for a Bielik GGUF, CLI candidate flags, output path, offline verification, and the fact that gated Hugging Face access requires user action.

- [ ] **Step 5: Verify full quality gate**

Run: `uv run --locked --extra dev pytest -q && uv run --locked --extra dev ruff check . && uv run --locked --extra dev ruff format --check . && uv run --locked --extra dev mypy .`

Expected: all commands exit 0.

- [ ] **Step 6: Commit**

```bash
git add experiments/real_llm_benchmark tests/test_real_llm_benchmark.py
git commit -m "feat: benchmark local Polish LLM candidates (#42)"
```
