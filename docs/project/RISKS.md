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
