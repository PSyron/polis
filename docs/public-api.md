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

## Status opcjonalnej morfologii

`Analyzer.morphology_status` zwraca niemutowalny `MorphologyStatus` zarejestrowany
podczas tworzenia analizatora. Pole `state` ma jedną z wartości:

- `active` — opcjonalny provider jest dostępny i ma oczekiwaną tożsamość;
- `unavailable` — provider nie jest dostępny, na przykład nie zainstalowano
  opcjonalnego extra `morphology`;
- `drifted` — provider jest dostępny, ale jego tożsamość różni się od
  przypiętej tożsamości runtime'u.

`MorphologyStatus` zawiera `state`, `expected_identity` oraz
`actual_identity`. Oba pola tożsamości mają typ `MorphologyProviderIdentity`,
który udostępnia `package_version`, `dictionary_id` i
`dictionary_notice_sha256`. Przy `unavailable` pole `actual_identity` ma wartość
`None`; przy pozostałych stanach zawiera faktycznie odczytaną tożsamość.

```python
from polis import Analyzer, AnalyzerConfig

status = Analyzer(AnalyzerConfig()).morphology_status
print(status.state)  # "active", "unavailable" albo "drifted"
if status.state == "drifted" and status.actual_identity is not None:
    print(status.expected_identity.package_version)
    print(status.actual_identity.package_version)
```

Odczyt statusu jest diagnostyką dostępności providera. Nie zmienia zasad
wyznaczania znalezisk ani polityki bezpiecznej korekty.

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

`Analyzer.correct(text)` jest metodą synchroniczną i należy ją wywoływać poza
działającą pętlą zdarzeń. W kodzie asynchronicznym należy użyć
`await Analyzer.correct_async(text)`. Próba wywołania `correct()` w działającej
pętli zgłasza `RuntimeError` z tą instrukcją, zanim powstanie coroutine, dzięki
czemu nie emituje ostrzeżenia o nieoczekiwanym braku `await`.

## Konfiguracja i błędy

`AnalyzerConfig(categories=None, minimum_confidence=0.0)` określa filtry
domyślnego analizatora. `AnalyzerConfig.from_toml(path)` i
`Analyzer.from_config(path)` wczytują lokalny plik z sekcją `[analysis]`.
Próg pewności musi być skończoną liczbą od `0.0` do `1.0`; `categories` musi
być `None` albo dokładnym wbudowanym zbiorem `frozenset` zawierającym wyłącznie
wartości `Category`. Klasy pochodne `frozenset` są odrzucane, także wtedy, gdy
pierwsze przejście po ich elementach wydawałoby się poprawne.
Bezpośrednie tworzenie `AnalyzerConfig(...)` zgłasza nieprawidłową wartość
jako `ConfigurationError` z kodem `configuration.invalid` i kontekstem
`operation`, przed rozpoczęciem analizy, bez ujawniania analizowanego tekstu
ani pełnej wartości konfiguracji.
Wczytywanie `AnalyzerConfig.from_toml(...)` zachowuje wcześniejszy kontrakt:
nieznana kategoria albo niepoprawny typ `analysis.categories` zgłasza kod
`configuration.invalid_value` z kontekstem `path`, a nieprawidłowe
`minimum_confidence` zgłasza kod `configuration.invalid` z kontekstem
`operation` i `path`.

Wszystkie kontrolowane błędy dziedziczą po `PolisError` i mają stabilne pola
`code`, `retryable` i bezpieczny `context`. Publiczne typy obejmują błędy
konfiguracji, analizy oraz wyboru korekt; pełną hierarchię określa
[ADR-0003](architecture/decisions/0003-public-api-and-exception-contract.md).

`polis.evaluation` nie jest głównym API korekty. Jego pełna obecna lista
18 eksportów — w tym `load_dataset`, `validate_dataset`, metryki, identyfikatory
i walidatory korpusów bezpieczeństwa — pozostaje zgodna importowo do wydania
1.0 włącznie zgodnie z [ADR-0023](architecture/decisions/0023-evaluation-namespace-1-0.md).
Kolejność i kompletność tej listy są kontraktem kompatybilności, a nie
zapowiedzią rozszerzenia runtime'u.

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
