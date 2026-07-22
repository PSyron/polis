# Release identity lifecycle

`pyproject.toml` is the authoritative version source. After `0.1.0`, development
continues as `0.2.0.dev0`. A release line advances without gaps or reuse:

1. `0.2.0.dev0` becomes the first candidate, `0.2.0rc1`.
2. A rejected candidate advances by one (`0.2.0rc2`, then `0.2.0rc3`); an rc
   number is never reused.
3. The accepted candidate becomes stable `0.2.0`.
4. Only after stable publication does source advance to the next planned
   `MAJOR.MINOR.PATCH.dev0` version.

In general, candidates are `0.2.0rcN`, stable releases are `0.2.0`, and every tag
is exactly `v<version>`. Update `uv.lock` with the source version. Do not maintain a
second runtime version constant.

## One identity

Before building, the requested version must be higher than the latest stable
version, absent from PyPI, and the next legal lifecycle step. Prepare a changelog
section headed `## <version> (<date>)` and `docs/release-notes/<version>.md` headed
`# Release notes: <version>`.

The release verifier requires exact agreement among:

- `pyproject.toml` and generated wheel/sdist metadata;
- artifact filenames;
- the requested `v<version>` tag;
- release notes and changelog section;
- the frozen `release-manifest.json` version, paths, and SHA-256 digests.

The manifest also records the full source commit. After tag creation,
`verify-tagged --manifest ...` requires the tag to resolve to that same commit and
supports both `rcN` and stable release tags.

Malformed, equal, lower, mismatched, skipped, reused, and already-published versions
are release blockers. PyPI lookups are explicit release-only operations through
`--check-pypi`; fast CI uses injected responses and never needs network access.

## Immutable evidence

Run `scripts/release_identity.py verify-tagged --tag v0.1.0` before a later release.
It compares the current historical notes and changelog section byte-for-byte with
the local tag. Do not move or replace a published tag, replace its assets, or edit a
historical release section. Restore accidental documentation drift from the tag,
place later work under `Unreleased`, and append a clarification to
`docs/release-errata.md` when readers need an explanation.

## Publication boundary

The candidate command must build exactly once. It hashes those two files into the
manifest; all installation and publication checks consume the same paths. Never
rebuild between verification and upload. After publication, compare PyPI filenames
and digests with the manifest. A mismatch is a failed release and must not be hidden
by rebuilding, moving a tag, or replacing evidence.
