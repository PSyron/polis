# Audyt prywatności i zależności przed wydaniem

Ten dokument zapisuje dowody dla bramki wydania M4-02 na `main`.

## Zakres

- Zależności runtime'u i ich licencje.
- Zachowanie sieciowe i gwarancje pracy offline.
- Gwarancje redakcji danych diagnostycznych.
- Kontrole zawartości artefaktów wydania.
- Skanowanie śledzonych plików repozytorium i zbudowanych dystrybucji pod kątem
  sekretów oraz plików modeli.

## Ustalenia

- `project.dependencies` **nie zawiera zależności runtime'u dla Pythona**.
- Wszystkie zależności build-time i deweloperskie są udokumentowane w
  [przeglądzie licencji zależności](development/dependency-licenses.md), a ich
  zgodność sprawdza `tests/test_dependency_licenses.py`.
- Zachowanie offline wymuszają testy uruchamiane z zablokowanym tworzeniem
  gniazd TCP w `tests/test_offline_verification.py` oraz
  `tests/test_privacy_dependency_audit.py::test_analyzer_without_model_backends_does_not_attempt_network`.
- Redakcja danych diagnostycznych jest walidowana przez sprawdzenie, że wybrane
  awarie nie zawierają tekstu użytkownika w komunikacie ani kontekście:
  `tests/test_privacy_dependency_audit.py::test_analysis_diagnostics_do_not_leak_user_text_by_default`.
- Poprawność pakowania artefaktów wydania jest walidowana przez
  `tests/test_distribution_artifacts.py` oraz
  `tests/test_privacy_dependency_audit.py::test_built_release_artifacts_do_not_include_model_files`.
- W śledzonych plikach nie znaleziono sekretów pasujących do wzorców
  repozytorium, a w zbudowanych wheel/sdist nie znaleziono znanych rozszerzeń
  artefaktów modeli ani plików binarnych
  (`tests/test_privacy_dependency_audit.py::test_no_secret_literals_in_versioned_files`).

## Polecenia odtwarzające dowody

- `uv run --locked --extra dev pytest -q tests/test_offline_verification.py tests/test_dependency_licenses.py tests/test_distribution_artifacts.py tests/test_privacy_dependency_audit.py`
- `uv run --locked --extra dev pytest -q tests/test_fast_ci_workflow.py`
- `uv run --locked --extra dev ruff check .`
- `uv run --locked --extra dev ruff format --check .`
- `uv run --locked --extra dev mypy .`

## Ryzyko rezydualne

- Maintainerzy repozytorium mogą dodać nowe zależności albo pliki modeli przez
  zmianę `pyproject.toml`, decyzji polityki zależności lub śledzonych plików;
  takie zmiany wymagają nowego audytu i review na poziomie issue.
- CLI wypisuje ustrukturyzowane szczegóły błędów. Jeśli wywołujący zapisują
  w logach pełne obiekty wyjątków, klucze kontekstu operacyjnego pozostają
  niewrażliwe zgodnie z kontraktem, ale zależnie od ustawień środowiska logi
  mogą nadal zawierać tracebacki wyjątków.
