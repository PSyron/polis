# Publiczne API

`polis` jest główną przestrzenią importów. Jej dokładny zestaw eksportów i
wersję schematu zabezpiecza [snapshot API](../tests/fixtures/public_api_snapshot.json).

```python
from polis import AnalysisOptions, Analyzer, AnalyzerConfig

analyzer = Analyzer(AnalyzerConfig())
result = analyzer.analyze(
    "Ona jestem tutaj.",
    options=AnalysisOptions(categories={"agreement"}, minimum_confidence=0.8),
)
correction = analyzer.correct("Zeby jutro,powiem o tym.")
```

## Analiza

`Analyzer.analyze(text, *, options=None)` zwraca pełny `AnalysisResult` albo
kontrolowany wyjątek. `analyze_async()` ma te same wejścia i semantykę. Wynik
zawiera tekst, uporządkowaną krotkę `issues` i użyte opcje.

`Finding` zawiera stabilny identyfikator, kategorię, ważność, komunikat,
wyjaśnienie, fragment oryginalny, minimalną sugestię, pewność i `Source`.
Zakres `start`, `end` jest półotwarty, odnosi się do oryginalnego napisu Pythona
i jest walidowany względem `original`. `AnalysisResult.apply(issue_ids)` stosuje
wyłącznie jawnie wybrane, zgodne znaleziska; błędny wybór nie zwraca częściowo
zmienionego tekstu.

`analysis_result_to_json()` i `analysis_result_from_json()` serializują schemat
w wersji 1. `SourceKind.LLM`, `SuggestionOutcome` i `SuggestionStatus` pozostają
w publicznym schemacie dla zgodności danych linii 0.x, lecz domyślny runtime v1
nie generuje takich wyników.

## Korekta

`Analyzer.correct(text)` zwraca `CorrectionResult` z polami:

- `original_text` i `corrected_text`;
- `applied_findings` i `skipped_findings`;
- `suggestion_outcomes` (pusta krotka w runtime v1);
- `source_policy_version`.

Automatycznie stosowane są tylko kwalifikowane, niekolidujące znaleziska
deterministyczne. `apply_suggestions(finding_ids)` pozwala jawnie dołączyć
wybrane pominięte znaleziska. Brak lokalnego uzasadnienia, konflikt lub ryzyko
zmiany znaczenia oznaczają wstrzymanie korekty.

## Konfiguracja i błędy

`AnalyzerConfig(categories=None, minimum_confidence=0.0)` określa filtry
domyślnego analizatora. `AnalyzerConfig.from_toml(path)` i
`Analyzer.from_config(path)` wczytują lokalny plik z sekcją `[analysis]`.

Wszystkie kontrolowane błędy dziedziczą po `PolisError` i mają stabilne pola
`code`, `retryable` i bezpieczny `context`. Publiczne typy obejmują błędy
konfiguracji, analizy oraz wyboru korekt; pełną hierarchię określa
[ADR-0003](architecture/decisions/0003-public-api-and-exception-contract.md).

`polis.evaluation.load_dataset` i `polis.evaluation.validate_dataset` pozostają
zgodne importowo w 0.x zgodnie z [ADR-0019](architecture/decisions/0019-evaluation-namespace-compatibility.md).
Nie są głównym API korekty.

## Zgodność wyjątków

Wersjonowany kontrakt [ADR-0003](architecture/decisions/0003-public-api-and-exception-contract.md)
zachowuje publiczne typy błędów. Analiza zwraca kompletny wynik albo zgłasza
kontrolowany błąd; nie zwraca częściowego `AnalysisResult`. Każdy przykład
odczytuje tylko bezpieczny kontekst błędu:

```python
from polis import (
    AnalysisTimeoutError,
    BackendUnavailableError,
    ConfigurationError,
    CorrectionConflictError,
    InvalidBackendResponseError,
    UncorrectableFindingError,
    UnknownFindingError,
)

try:
    raise ConfigurationError("invalid", code="configuration.invalid", retryable=False, context={"path": "polis.toml"})
except ConfigurationError as error:
    assert error.context["path"] == "polis.toml"

try:
    raise BackendUnavailableError("unavailable", code="backend.unavailable", retryable=True, context={"backend": "archived"})
except BackendUnavailableError as error:
    assert error.context["backend"] == "archived"

try:
    raise AnalysisTimeoutError("timeout", code="analysis.timeout", retryable=True, context={"backend": "archived"})
except AnalysisTimeoutError as error:
    assert error.context["backend"] == "archived"

try:
    raise InvalidBackendResponseError("invalid", code="backend.invalid_response", retryable=False, context={"backend": "archived"})
except InvalidBackendResponseError as error:
    assert error.context["backend"] == "archived"

try:
    raise UnknownFindingError("unknown", code="correction.unknown_finding", retryable=False, context={"finding_ids": "finding_missing"})
except UnknownFindingError as error:
    assert error.context["finding_ids"] == "finding_missing"

try:
    raise UncorrectableFindingError("uncorrectable", code="correction.uncorrectable_finding", retryable=False, context={"finding_ids": "finding_missing"})
except UncorrectableFindingError as error:
    assert error.context["finding_ids"] == "finding_missing"

try:
    raise CorrectionConflictError("conflict", code="correction.conflict", retryable=False, context={"finding_ids": "finding_one,finding_two"})
except CorrectionConflictError as error:
    assert error.context["finding_ids"] == "finding_one,finding_two"
```
