# LanguageTool upstream provenance

- Repository: https://github.com/languagetool-org/languagetool.git
- Release tag: `v6.8`
- Pinned commit: `e807fcde6a6506191e1470744d2345da28c26be6`
- Language: `pl-PL`
- Retrieval date: 2026-07-21

## Exact source checkout

```bash
git clone https://github.com/languagetool-org/languagetool.git
cd languagetool
git checkout e807fcde6a6506191e1470744d2345da28c26be6
```

## Included modules

- `languagetool-language-modules/pl`
- `languagetool-core`

The files under `sources/` are produced with `git archive` from this commit and
then receive the reviewed patch
`patches/0001-reproducible-build-metadata.patch`. The patch fixes the JAR
manifest date, disables collection of metadata from the enclosing repository,
and supplies the pinned v6.8 identity expected by `LtBuildInfo`.
`manifest.json` lists the exact included paths and both modified upstream files.
The stdio bridge and build scripts are project-authored files outside those
source trees.

The goal for this issue is a minimal Polish-only derivative for reproducible local
evaluation, not a full LanguageTool replacement.
