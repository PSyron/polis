# Issue 1 Python, Platform, and Licensing Policy Implementation Plan

**Goal:** Record and verify the initial Python, platform, and licensing policy
required by GitHub issue #1.

**Architecture:** An accepted ADR owns the compatibility and licensing decision.
An architecture index exposes it, while a standard-library test checks its
normative clauses for later package metadata and CI work.

## Global constraints

- Use English for repository-authored technical documentation.
- Paweł Cyroń remains the sole credited author; add no attribution, co-author
  trailer, or generation disclosure.
- Do not create `pyproject.toml`, scaffold the package, select an NLP dependency,
  or select a model/backend.
- Distinguish installation metadata from tested support: declare
  `requires-python = ">=3.12"` without an upper bound; initially support and test
  CPython 3.12 through 3.14; treat newer minors as best-effort until CI promotion.
- Specify the initial representative CI matrix: `ubuntu-24.04` x86_64 on 3.12,
  3.13, and 3.14; `macos-15` arm64 and `windows-2025` x86_64 on 3.12 and 3.14.
- Specify M0-03 package metadata, built-distribution verification, dependency
  review, data provenance, model review, and external-asset requirements.

## Task 1: Accepted compatibility and licensing ADR

**Files:**

- `tests/test_architecture_policy.py`
- `docs/architecture/README.md`
- `docs/architecture/decisions/0001-python-platform-licensing-policy.md`
- `docs/superpowers/plans/2026-07-20-issue-1-policy.md`

**Interfaces:** Consumes GitHub issue #1 and `PROMPT.md`; produces ADR-0001
clauses for M0-03 package metadata and M0-04 CI configuration.

1. Add a failing documentation contract test for the Accepted index entry and the
   exact Python, runner, packaging, dependency, data, model, privacy, and
   authoritative-reference clauses.
2. Confirm the test is red because the stricter policy language is absent.
3. Add the index and ADR. Record the runner labels as pinned and reviewed when a
   provider retires an image; avoid claiming a Cartesian platform matrix.
4. Run `python3 -m unittest tests/test_architecture_policy.py -v` and
   `python3 -m unittest discover -s tests -v`.
5. Verify whitespace and scope, stage only the four task files, and create one
   focused issue #1 commit.
