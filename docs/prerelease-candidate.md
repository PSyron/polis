# Kandydat do wydania

Kandydat v1 dotyczy wyłącznie deterministycznego runtime'u offline. Przed
publikacją uruchom:

```console
uv run --locked --extra dev pytest
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
uv run --locked --extra dev python scripts/validate_documentation_inventory.py
uv run --locked --extra dev python scripts/prepare_build_wheelhouse.py \
  --lock uv.lock --output build-wheelhouse \
  --manifest build-wheelhouse-manifest.json
uv run --locked --extra dev python -m build --no-isolation --outdir dist
uv run --locked --extra dev python scripts/verify_distribution_artifacts.py \
  --dist dist
uv run --locked --extra dev python scripts/verify_distribution_install.py \
  --dist dist --wheelhouse build-wheelhouse \
  --wheelhouse-manifest build-wheelhouse-manifest.json
uv run --locked --extra dev python scripts/verify_prerelease_candidate.py \
  --dist dist --wheelhouse build-wheelhouse \
  --wheelhouse-manifest build-wheelhouse-manifest.json \
  --source-commit "$(git rev-parse HEAD)"
```

Potwierdź zgodność wersji, skróty artefaktów, test instalacji offline i stan
publicznego API. Wydanie nie zależy od uruchomienia badań ani od otwierania
zamrożonych danych. Opcjonalne badania nad modelem nigdy nie blokują wydania
runtime'u. Ścieżka wydania runtime'u nie wymaga modelu, procesu Java, usługi
sieciowej, korpusu badawczego ani zużytego holdoutu. Szczegóły zawiera
[weryfikacja dystrybucji](distribution-verification.md).
