# Release Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent reuse or divergence of a Polis release version by verifying
one immutable identity across source metadata, artifacts, release evidence, and
publication records.

**Architecture:** Add a standard-library release verifier in
`scripts/release_identity.py`. It reads project metadata, validates a PEP 440
release line, binds a candidate tag to exactly one source commit, builds and
records one wheel/sdist pair in a JSON manifest, and checks that protected
historical evidence is byte-identical to the tagged content. The offline
verifier receives publication observations as explicit data; a separate
release-only command obtains those observations from GitHub, git remotes, and a
configured package index.

**Tech Stack:** Python 3.12+, standard library, `packaging.version`, pytest,
Ruff, mypy, uv, Hatchling build artifacts, JSON manifests, git and GitHub CLI.

## Global Constraints

- Preserve the offline-only product boundary and add no production dependency.
- `pyproject.toml` remains the authoritative package-version source.
- Release source must move to `0.2.0.dev0`; candidate and stable forms are
  `0.2.0rcN` and `0.2.0`, tagged as `v<version>`.
- Never move `v0.1.0`, replace its assets, or rewrite its public release.
- Protected notes and changelog sections compare raw bytes, not decoded or
  newline-normalized text.
- Fast CI runs only offline checks. Network publication checks are explicit
  release-only commands and their fast tests use injected fakes.
- Keep the change in one focused commit credited only to Paweł Cyroń.

---

### Task 1: Define the release identity contract with failing tests

**Files:**
- Create: `tests/test_release_identity.py`
- Create: `scripts/release_identity.py`

**Interfaces:**
- Produces: `ReleaseIdentity`, `ArtifactDigest`, `ReleaseManifest`,
  `validate_candidate()`, `verify_artifacts()`, `verify_tagged_evidence()`, and
  `verify_published_digests()`.

- [ ] **Step 1: Write failing unit tests for accepted release forms and rejected identities.**

```python
def test_candidate_accepts_next_dev_rc_and_stable_versions() -> None:
    for version in ("0.2.0.dev0", "0.2.0rc1", "0.2.0"):
        assert validate_candidate(version, latest="0.1.0") == f"v{version}"


def test_candidate_rejects_reused_lower_malformed_and_mismatched_versions() -> None:
    for version in ("0.1.0", "0.1.0.dev1", "0.2", "release-0.2.0"):
        with pytest.raises(ReleaseIdentityError):
            validate_candidate(version, latest="0.1.0")
```

- [ ] **Step 2: Run the focused test and verify RED.**

Run: `uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest -q tests/test_release_identity.py`

Expected: FAIL because `scripts.release_identity` does not exist.

- [ ] **Step 3: Implement only the typed immutable data models and candidate validator required by the tests.**

```python
@dataclass(frozen=True)
class ReleaseIdentity:
    version: Version
    tag: str
    source_commit: str


def validate_candidate(version: str, *, latest: str) -> str:
    candidate = Version(version)
    if candidate <= Version(latest) or candidate.epoch or candidate.local:
        raise ReleaseIdentityError("candidate version is not a new public release")
    return f"v{candidate}"
```

- [ ] **Step 4: Run the focused test and verify GREEN.**

Run: `uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest -q tests/test_release_identity.py`

Expected: PASS for the new candidate tests.

### Task 2: Bind source, artifacts, and manifest to one release identity

**Files:**
- Modify: `scripts/release_identity.py`
- Modify: `tests/test_release_identity.py`
- Modify: `scripts/verify_prerelease_candidate.py`

**Interfaces:**
- Consumes: `ReleaseIdentity(version, tag, source_commit)` and a directory with
  exactly one wheel and one source distribution.
- Produces: `ReleaseManifest.to_json()` with filename/SHA-256 pairs and
  `verify_artifacts(manifest, dist)`.

- [ ] **Step 1: Write failing tests for artifact names and embedded metadata.**

```python
def test_manifest_rejects_artifact_version_or_digest_mismatch(tmp_path: Path) -> None:
    manifest = manifest_for(tmp_path, version="0.2.0rc1")
    (tmp_path / "polis_nlp-0.2.0rc1-py3-none-any.whl").write_bytes(b"wheel")
    with pytest.raises(ReleaseIdentityError, match="digest"):
        verify_artifacts(manifest, tmp_path)
```

- [ ] **Step 2: Run the focused artifact tests and verify RED.**

Run: `uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest -q tests/test_release_identity.py -k artifact`

Expected: FAIL because artifact verification is not implemented.

- [ ] **Step 3: Implement build-once manifest creation, filename/version checks, archive metadata checks, and SHA-256 verification.**

```python
def create_manifest(identity: ReleaseIdentity, dist: Path) -> ReleaseManifest:
    artifacts = tuple(_digest(path) for path in _collect_artifacts(dist))
    _require_artifact_versions(artifacts, identity.version)
    return ReleaseManifest(identity=identity, artifacts=artifacts)
```

- [ ] **Step 4: Integrate manifest generation into the prerelease command without uploading artifacts.**

Run: `uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest -q tests/test_release_identity.py tests/test_distribution_artifacts.py`

Expected: PASS.

### Task 3: Protect tagged release evidence with byte comparisons

**Files:**
- Modify: `scripts/release_identity.py`
- Modify: `tests/test_release_identity.py`
- Modify: `CHANGELOG.md`
- Modify: `docs/release-notes/0.1.0.md`

**Interfaces:**
- Consumes: a tag, a git-content reader returning `bytes`, and paths to release
  notes and changelog.
- Produces: `verify_tagged_evidence()` which accepts byte-identical history and
  rejects any changed note or tagged changelog section.

- [ ] **Step 1: Write byte-oriented failing tests for changed tagged notes and changelog sections.**

```python
def test_tagged_evidence_compares_raw_bytes_across_platforms(tmp_path: Path) -> None:
    note = tmp_path / "0.2.0.md"
    note.write_bytes(b"heading\\n")
    with pytest.raises(ReleaseIdentityError, match="release note"):
        verify_tagged_evidence(note, b"heading\\r\\n")
```

- [ ] **Step 2: Run the evidence tests and verify RED.**

Run: `uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest -q tests/test_release_identity.py -k evidence`

Expected: FAIL because evidence verification is not implemented.

- [ ] **Step 3: Implement raw-byte comparison and extract exactly one changelog section per published version.**

```python
def require_equal_bytes(current: bytes, tagged: bytes, *, label: str) -> None:
    if current != tagged:
        raise ReleaseIdentityError(f"{label} differs from its tagged evidence")
```

- [ ] **Step 4: Restore the 0.1.0 note and changelog section from `v0.1.0`; move later changes to `Unreleased`.**

Run: `git diff --no-index docs/release-notes/0.1.0.md <(git show v0.1.0:docs/release-notes/0.1.0.md)`

Expected: no differences (use a temporary file instead of shell process substitution on Windows).

### Task 4: Separate explicit publication checks from offline verification

**Files:**
- Modify: `scripts/release_identity.py`
- Modify: `tests/test_release_identity.py`
- Modify: `docs/prerelease-candidate.md`
- Modify: `docs/distribution-verification.md`
- Modify: `docs/compatibility.md`
- Modify: `README.md`
- Create: `docs/release-notes/0.1.0-erratum.md` only if current published
  GitHub evidence disagrees with the immutable tag evidence.

**Interfaces:**
- Consumes: fake `tag_exists`, `release_exists`, `published_versions`, and
  `published_digests` callables in fast tests; real adapters only when a
  maintainer invokes the release-only CLI.
- Produces: explicit candidate uniqueness and post-publication digest checks.

- [ ] **Step 1: Write failing tests for existing tag, existing release, package-index version, and published digest mismatch.**

```python
def test_publication_checks_reject_existing_identity_and_digest_mismatch() -> None:
    with pytest.raises(ReleaseIdentityError, match="already published"):
        verify_publication(identity, tag_exists=lambda _: True)
```

- [ ] **Step 2: Run the publication tests and verify RED.**

Run: `uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest -q tests/test_release_identity.py -k publication`

Expected: FAIL because publication verification is not implemented.

- [ ] **Step 3: Implement injectable publication verification and a CLI whose network mode is opt-in.**

```python
def verify_publication(identity: ReleaseIdentity, *, tag_exists: TagExists) -> None:
    if tag_exists(identity.tag):
        raise ReleaseIdentityError("release tag already exists")
```

- [ ] **Step 4: Document SemVer release selection versus PEP 440 dev/RC syntax, build-once evidence, immutable history, and append-only errata.**

Run: `uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest -q tests/test_release_identity.py tests/test_fast_ci_workflow.py`

Expected: PASS without network access.

### Task 5: Verify the complete release identity workflow

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `tests/test_package_smoke.py`
- Modify: `.github/workflows/fast-ci.yml` only if the offline verifier is not
  already covered by the existing fast test command.

**Interfaces:**
- Consumes: the completed verifier, release documentation, and the `0.2.0.dev0`
  project metadata.
- Produces: a fast, offline regression suite and a documented release-only
  checklist.

- [ ] **Step 1: Write failing metadata tests that require `0.2.0.dev0`.**

```python
def test_distribution_version_is_declared() -> None:
    assert version("polis-nlp") == "0.2.0.dev0"
```

- [ ] **Step 2: Run the focused version test and verify RED.**

Run: `uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest -q tests/test_package_smoke.py -k version`

Expected: FAIL because source metadata still declares `0.1.0`.

- [ ] **Step 3: Update source metadata and regenerate the locked metadata with the required uv version.**

Run: `uvx --from 'uv==0.11.2' uv lock`

Expected: lock metadata agrees with `0.2.0.dev0` and no production dependency is added.

- [ ] **Step 4: Run focused, fast, packaging, static-analysis, and build verification.**

Run: `uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest -m "not slow and not model"`

Expected: PASS.

Run: `uvx --from 'uv==0.11.2' uv run --locked --extra dev ruff check . && uvx --from 'uv==0.11.2' uv run --locked --extra dev ruff format --check . && uvx --from 'uv==0.11.2' uv run --locked --extra dev mypy .`

Expected: PASS.

- [ ] **Step 5: Review every #91 acceptance criterion, then make one focused commit.**

```bash
git add pyproject.toml uv.lock scripts/release_identity.py scripts/verify_prerelease_candidate.py \\
  tests/test_release_identity.py tests/test_package_smoke.py CHANGELOG.md \\
  docs README.md docs/superpowers/plans/2026-07-22-issue-91-release-identity.md
git commit -m "feat: enforce immutable release identity (#91)"
```
