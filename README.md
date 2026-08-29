# Polis

Polis to biblioteka Pythona działająca domyślnie offline. Wykrywa i proponuje
minimalne, deterministyczne poprawki polskiego tekstu. Runtime v1 działa bez
sieci, modelu językowego, procesu Java i usług zewnętrznych.

## Granica v1

Polis poprawia tylko jednoznaczną lokalną formę tekstu. Nie zmienia znaczenia,
intencji, faktów, czasu, aspektu, stylu ani tonu. Gdy reguła nie ma
uzasadnionej minimalnej poprawki, nie zwraca sugestii. Automatyczna korekta
stosuje tylko zakwalifikowane, niekolidujące znaleziska; pozostałe są dostępne
do jawnego wyboru przez wywołującego.

Obsługiwane kategorie analizatora v1, ich granice i znaczenie wartości
zgodnościowej `style` opisuje [słownik kategorii](docs/categories.md). Pełny
wykaz źródeł znajduje się w [opisie reguł](docs/rules.md), a bezpieczny proces
rozszerzania opisuje [przewodnik autorstwa reguł deterministycznych](docs/rule-
authoring.md).
Historia badań v2 nie jest funkcją produktu; jej odtwarzalną lokalizację podaje
[manifest archiwum](docs/project/v2-research-archive-manifest.md).
Żaden przetestowany model lokalny nie został zakwalifikowany do runtime'u v1;
LanguageTool również nie stanowi jego składnika.
Opcjonalne badania nad modelem nigdy nie blokują wydania runtime'u. Ścieżka
wydania runtime'u nie wymaga modelu, procesu Java, usługi sieciowej, korpusu
badawczego ani zużytego holdoutu.

## Szybki start

Polis wymaga Pythona 3.12 lub nowszego.

Do pracy deweloperskiej używaj przypiętego uv 0.11.2. Oficjalne instalatory to
<https://astral.sh/uv/0.11.2/install.sh> dla powłok POSIX oraz
<https://astral.sh/uv/0.11.2/install.ps1> dla PowerShell.

```console
python -m pip install polis-nlp
```

Domyślna instalacja pozostaje kompletnym runtime'em. Czterej opcjonalni, lokalni
konsumenci Morfeusz2 dla zamkniętych wzorców wymagają osobnego extra:

```console
python -m pip install 'polis-nlp[morphology]'
```

Po tej instalacji `Analyzer.analyze("Nie widzę czerwony samochód.")` zwraca
jedną sugestię `czerwonego samochodu`, a
`Analyzer.analyze("Te duże okno jest otwarte.")` jedną sugestię `To`, zawsze
do przeglądu, a `Analyzer.analyze("Oni czyta książkę.")` jedną sugestię
`czytają` w zakresie `[4, 9)`, także wyłącznie do przeglądu.
`Analyzer.analyze("Potrzebuję pomoc.")` zwraca jedną sugestię `pomocy` w zakresie
`[11, 16)`, również wyłącznie do przeglądu.
`Analyzer.correct()` nie stosuje ich automatycznie; można je
zastosować przez
`CorrectionResult.apply_suggestions()`. Brak dostawcy, dryft jego dokładnej
tożsamości albo niejednoznaczny wynik oznacza abstencję bez częściowej sugestii.
Wszystkie cztery konstrukcje działają bez sieci, modelu i procesu Java.

```python
from polis import correct

assert correct("Zeby jutro,powiem o tym.").corrected_text == (
    "Żeby jutro, powiem o tym."
)
```

Jednorazowe wywołania mogą korzystać z `polis.analyze(text)` i
`polis.correct(text)`. Obie funkcje leniwie współdzielą analizator dla każdej
wartości `AnalyzerConfig`, więc przy wielu wywołaniach warto zbudować jeden
`Analyzer` jawnie:

```python
from polis import Analyzer, AnalyzerConfig

analyzer = Analyzer(AnalyzerConfig())
texts = ["Te zdanie.", "Ona jestem tutaj."]
for text in texts:
    result = analyzer.analyze(text)
```

`Analyzer.analyze()` oraz `polis.analyze()` zwracają `AnalysisResult` ze
znaleziskami i przesunięciami `[start, end)`. `Analyzer.correct()` oraz
`polis.correct()` zwracają oryginalny oraz poprawiony tekst, znaleziska
zastosowane i pominięte. Szczegóły zawiera
[publiczne API](docs/public-api.md), [szybki start](docs/quick-start.md) oraz
[przewodnik CLI](docs/cli.md).

## Konfiguracja

Jedyną wspieraną sekcją pliku TOML jest `[analysis]`. Może określać
`categories` i `minimum_confidence`; znaczenie kategorii oraz przykładowe
wartości opisuje [słownik kategorii](docs/categories.md), a kompletny przykład
znajduje się w [`examples/polis.toml`](examples/polis.toml). Konfiguracja jest
odczytywana z lokalnego, jawnie wskazanego pliku i nie szuka ustawień niejawnych.
Dokładnie historyczne tabele `[backend]`, `[language_tool]`,
`[contextual_inflection]` i `[vendored_language_tool]` są odrzucane przez
`ConfigurationError`. Inne nieznane tabele i klucze parser obecnie ignoruje;
nie są one wspieranym interfejsem i nie należy na tym zachowaniu polegać.

## Jakość i prywatność

Tekst nie opuszcza procesu. Polis nie zapisuje go w błędach bez jawnego
działania aplikacji wywołującej. Zobacz [pracę offline](docs/offline-operation.md),
[ograniczenia](docs/limitations.md), [prywatność](docs/privacy.md) i
[audyt prywatności](docs/privacy-audit.md).

W repozytorium kontrole deweloperskie uruchamia się w zablokowanym środowisku:

```console
uv sync --locked --extra dev
uv run --locked --extra dev pytest -m "not research and not slow"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
```

Zasady zgodności, dystrybucji i kandydata wydania opisują odpowiednio
[compatibility](docs/compatibility.md),
[verification](docs/distribution-verification.md) i
[prerelease candidate](docs/prerelease-candidate.md).
