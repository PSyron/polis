# Project Risks and Open Decisions

Each risk has a roadmap owner. Closing the owner issue must either resolve the risk or record an accepted residual risk.

| Risk | Impact | Mitigation and evidence | Owner |
| --- | --- | --- | --- |
| Unsupported or overly broad Python/platform matrix | Packaging failures and excessive compatibility work | Record supported versions and platforms before scaffolding; validate them in CI | M0-01 |
| NLP dependency has unsuitable license, size, quality, or offline behavior | Core architecture becomes costly or non-compliant | Compare realistic candidates against explicit criteria and record an ADR | M0-02 |
| Public model or JSON schema changes after consumers adopt it | Breaking API changes and unstable issue identifiers | Version the schema and test round-trip serialization before downstream modules | M0-05 |
| Proposed API and error behavior remain ambiguous | Adapters and callers implement incompatible assumptions | Approve examples, exception boundaries, partial-result behavior, and correction semantics | M0-06 |
| Evaluation data lacks provenance or difficult negative examples | Misleading quality results and licensing risk | Start with licensed or project-authored cases and record provenance per case | M0-08 |
| A named runtime or model becomes unavailable | LLM integration blocks releases or couples core to a vendor | Benchmark multiple candidates and depend only on the backend protocol | M2-01 |
| Model output is malformed, injected, slow, or over-broad | Crashes, privacy leaks, or unsafe corrections | Validate a versioned schema, constrain ranges, apply timeouts, and fail safely | M2-02, M2-04 |
| Confidence scores are uncalibrated | Excessive false positives or misleading severity | Measure a baseline and derive thresholds from evaluation data | M3-02 |
| Performance targets are guessed | Release gates are either meaningless or unattainable | Measure latency, throughput, and memory on documented configurations | M3-03 |
| The optional CLI accumulates business logic | Duplicate behavior and unstable interfaces | Keep it as a thin caller of the public API and test examples end to end | M3-05 |
| Private texts, models, or generated corpora enter version control | Privacy, repository-size, and licensing incidents | Ignore local artifacts, audit tracked files, and document privacy-safe diagnostics | M4-02 |
| GitHub bootstrap stops after a partial write | Duplicate or inconsistent project metadata | Discover resources by exact stable name and make every operation idempotent | Planning bootstrap |
| Evaluation leakage between prompt, training, development, and holdout data | Reported quality does not generalize and model selection is invalid | Hash and compare every split, freeze the holdout, prohibit holdout-driven prompt changes, and record one final holdout run | #55, #56, #62, #63 |
| Circular benchmark logic recognizes corpus text or encodes expected answers | The evaluator measures lookup behavior rather than Polish correction | Keep benchmark execution independent from gold data, add unseen probes, inspect runners for corpus-specific branches, and require reproducible evidence metadata | #55 |
| Morphology ambiguity produces many valid forms without resolving context | Candidate recall looks high while selected corrections remain unsafe | Report recall and ambiguity separately, retain unchanged as a candidate, and let a model select only from finite IDs | #58, #59 |
| Suggestion false positives alter correct names, inflection, word order, or protected tokens | Review burden and user trust regress even without automatic application | Require zero findings on protected hard negatives and at least 0.90 exact edit precision on a frozen holdout | #57, #60, #64 |
| Runtime availability differs across MLX, GGUF, and local service configurations | A selected model cannot run offline on the supported machine | Require explicit local preflight, exact runtime and artifact metadata, no implicit downloads, and a deterministic-only outcome when the optional suggestion path is unavailable | #61, #43 |
| Memory pressure invalidates latency measurements or makes the pipeline impractical on 16 GB Apple Silicon | Benchmarks select a configuration that swaps or destabilizes the host | Measure loaded memory with cold and warm latency, reject pressured runs, and select the smallest configuration that passes quality gates | #61, #63, #64 |
| Fine-tuning overfit improves templated development examples but harms protected negatives or unseen text | An adapter appears better than the prompt-only baseline without generalizing | Train only after the prompt baseline, use independent authored data, run leakage checks and ablations, and reject the adapter unless frozen validation and holdout gates pass | #62, #63 |
