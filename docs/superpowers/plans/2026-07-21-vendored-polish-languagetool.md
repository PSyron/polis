# Vendored Polish LanguageTool Module Implementation Plan

**Goal:** create a pinned, source-based `third_party/languagetool-pl` Java subset for Polish-only
LanguageTool checking without adding Python runtime dependencies or changing Python package artifacts.

**Architecture:** keep all LanguageTool/JVM work isolated under
`third_party/languagetool-pl`, build the pinned copied core and Polish sources,
and expose the two qualified upstream rules through a thin persistent stdio
bridge. The existing Polis HTTP adapter contract remains unchanged.

**Tech Stack:** Java 17, Maven, Bash scripts, Python tests for guardrails.

## Global Constraints

- Keep Polis production runtime free of new Python dependencies.
- Keep Polish LanguageTool sources isolated from `src/polis` and excluded from wheel/sdist artifacts.
- Keep module operation offline after build; allow network only in explicit bootstrap/build preparation.
- Preserve upstream LGPL-2.1-or-later provenance and local source record.
- Never fall back to a corpus lookup or a wrapper that does not execute the copied modules.

---

### Task 1: Create vendored module scaffold and provenance documentation

**Files:**
- Create: `third_party/languagetool-pl/README.md`
- Create: `third_party/languagetool-pl/UPSTREAM.md`
- Create: `third_party/languagetool-pl/LICENSE-LGPL-2.1.txt`
- Create: `third_party/languagetool-pl/NOTICE`
- Create: `third_party/languagetool-pl/manifest.json`
- Create: `docs/superpowers/plans/2026-07-21-vendored-polish-languagetool.md`

- [x] **Step 1: Write the full plan document with required task breakdown and acceptance checkpoints**

```markdown
# Vendored Polish LanguageTool Module Implementation Plan
```

- [x] **Step 2: Add upstream provenance docs**

```markdown
# in UPSTREAM.md
repository: https://github.com/languagetool-org/languagetool.git
```

- [x] **Step 3: Add manifest and legal notices**

```json
{
  "upstream_commit": "5632fa2c75a544c05ded53d842302381d253f2d0"
}
```

### Task 2: Add reproducible bootstrap and build scripts

**Files:**
- Create: `third_party/languagetool-pl/scripts/bootstrap.sh`
- Create: `third_party/languagetool-pl/scripts/build.sh`
- Create: `third_party/languagetool-pl/scripts/run_stdio.sh`
- Create: `third_party/languagetool-pl/scripts/verify.sh`

**Interfaces:**
- `bootstrap.sh` fetches pinned upstream sources into `third_party/languagetool-pl/sources`.
- `build.sh` creates local Maven artifacts from the pinned parent, core, and Polish sources, then the thin bridge.
- `run_stdio.sh` launches the vendored stdio bridge in foreground.
- `verify.sh` validates manifest, expected file set, and runtime executable bits.

- [x] **Step 1: Implement bootstrap script**

```bash
./third_party/languagetool-pl/scripts/bootstrap.sh
```

- [x] **Step 2: Implement build and stdio launch scripts**

```bash
./third_party/languagetool-pl/scripts/build.sh
./third_party/languagetool-pl/scripts/run_stdio.sh
```

- [x] **Step 3: Implement module verification script**

```bash
./third_party/languagetool-pl/scripts/verify.sh
```

### Task 3: Add artifact and distribution safety checks

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_distribution_artifacts.py`
- Create: `tests/test_languagetool_vendor_artifacts.py`
- Modify: `.gitignore`
- Modify: `docs/development/dependency-licenses.md`

- [x] **Step 1: Add tests for vendor manifest and required legal files**

```python
from pathlib import Path
manifest = json.loads(Path(...).read_text(encoding="utf-8"))
assert manifest["upstream"]["commit"]
```

- [x] **Step 2: Keep vendored source out of Python artifacts**

```toml
[tool.hatch.build.targets.sdist]
exclude = ["/third_party/languagetool-pl"]
```

- [x] **Step 3: Extend distribution artifact assertions**

```python
assert not any("third_party/languagetool-pl" in name for name in wheel_names + sdist_names)
```

### Task 4: Update optional Java integration notes

**Files:**
- Modify: `docs/offline-operation.md`
- Modify: `docs/architecture/README.md`

- [x] **Step 1: Add an explicit entry for optional vendored LanguageTool module path**

```markdown
third_party/languagetool-pl is build-time only and never runtime-distributed.
```

- [x] **Step 2: Add ADR-style traceability marker if required by reviewer**

```markdown
Add ADR-0007 row only if a policy decision is reached in review.
```

## Self-Review

1. Spec coverage: each requirement from issue #54 maps to Task 1–4 plus the
   real-engine corpus benchmark documented in `BENCHMARK.md`.
2. Integrity: the wrapper invokes `JLanguageTool(new Polish())`; no corpus text
   or expected offset table exists in production code.
3. Provenance: v6.8 commit, unmodified included source paths, exclusions, and
   project-authored files are recorded in `manifest.json`.
4. Type consistency: no untyped production Python APIs were introduced.

Plan complete and saved to `docs/superpowers/plans/2026-07-21-vendored-polish-languagetool.md`.
