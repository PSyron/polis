# Kandydat do wydania

Kandydat v1 dotyczy wyłącznie deterministycznego runtime'u offline. Przed
publikacją uruchom:

```console
uv run --locked --extra dev pytest
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
uv run --locked --extra dev python scripts/validate_documentation_inventory.py
uv build
uv run python scripts/verify_distribution_artifacts.py dist/*.whl dist/*.tar.gz
uv run python scripts/verify_distribution_install.py dist/*.whl
```

Potwierdź zgodność wersji, skróty artefaktów, test instalacji offline i stan
publicznego API. Wydanie nie zależy od uruchomienia badań ani od otwierania
zamrożonych danych. Opcjonalne badania nad modelem nigdy nie blokują wydania
runtime'u. Ścieżka wydania runtime'u nie wymaga modelu, procesu Java, usługi
sieciowej, korpusu badawczego ani zużytego holdoutu. Szczegóły zawiera
[weryfikacja dystrybucji](distribution-verification.md).
