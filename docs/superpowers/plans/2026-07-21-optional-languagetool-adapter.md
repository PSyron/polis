# Optional LanguageTool Adapter Implementation Plan

**Goal:** Add a disabled-by-default, allowlisted local LanguageTool 6.8
punctuation rule without adding a package dependency.

**Architecture:** A strict loopback HTTP transport is injected into one
fail-open rule. The rule validates version/schema/UTF-16 spans, normalizes only
reviewed comma insertions, and joins the existing registry only when configured.

**Tech Stack:** Python standard library, existing Rule protocol, pytest.

## Global Constraints

- Only LanguageTool 6.8 on a numeric loopback HTTP endpoint.
- No proxy, redirect, public API, download, Java bundle, or Python dependency.
- Allowlist only `BRAK_PRZECINKA_ZE` and `BRAK_PRZECINKA_ZEBY`.
- Confidence remains 0.85 and automatic correction remains disabled.
- One focused commit referencing #53 with Paweł Cyroń as sole author.

---

### Task 1: Strict rule and transport

**Files:** Create `src/polis/rules/languagetool.py`; create
`tests/test_languagetool_rule.py`.

- [x] Write failing tests for endpoint policy, no-proxy/no-redirect transport,
  preflight/version checks, response bounds, UTF-16 conversion, minimal comma
  normalization, ambiguity, allowlisting, conflicts, and fail-open behavior.
- [x] Verify the tests fail for missing interfaces.
- [x] Implement the minimal transport, parser, normalizer, and rule.
- [x] Run focused tests, Ruff, and mypy.

### Task 2: Optional Analyzer configuration

**Files:** Modify `src/polis/analyzer.py`, `src/polis/rules/__init__.py`, and
configuration/analyzer tests.

- [x] Write failing tests that omitted configuration performs no I/O, valid
  TOML registers the rule, invalid configuration is rejected, built-in findings
  survive sidecar failure, and `correct()` skips sidecar findings.
- [x] Implement optional construction without contacting the server.
- [x] Run focused and integration tests.

### Task 3: Quality evidence and documentation

**Files:** Add corpus quality tests; update ADR-0006, offline operation,
customization, rules, limitations, public API, and licensing documentation.

- [x] Assert 18 exact punctuation TPs, precision 1.0, recall 0.75, F1 0.857,
  and zero findings on negatives from recorded 6.8 responses.
- [x] Run the opt-in real-server test.
- [x] Document setup, removal, footprint, blocking timeout, allowlist, failure
  exception, and prohibited services.
- [x] Run full tests, Ruff, formatting, mypy, build, artifact verification, and
  independent review before commit and close.
