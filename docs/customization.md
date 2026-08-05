# Przewodniki personalizacji

`polis` udostępnia stabilne punkty rozszerzeń dla reguł deterministycznych
i backendów generowania lokalnego. Runtime'owy `Analyzer` jest obecnie celowo
wąski; zaawansowana kompozycja korzysta obecnie z wewnętrznych funkcji
pomocniczych potoku.

## Dodawanie własnej reguły deterministycznej

Zaimplementuj `polis.core.Rule` i zarejestruj ją w `DeterministicRuleRegistry`.

```python
from polis.core import AnalysisOptions, Category, Confidence, Finding, Source, SourceKind, Severity
from polis.rules import DeterministicRuleRegistry, RuleRegistration
from polis.analysis.pipeline import analyze_text


class DoubleSpaceRule:
    @property
    def source(self) -> Source:
        return Source(SourceKind.RULE, "double_space")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if "  " not in text:
            return ()

        index = text.index("  ")
        return (
            Finding.create(
                category=Category.STYLE,
                severity=Severity.WARNING,
                message="Double space",
                explanation="Two spaces are rarely intentional in running text.",
                original="  ",
                suggestion=" ",
                start=index,
                end=index + 2,
                confidence=Confidence(0.95),
                source=Source(SourceKind.RULE, "double_space"),
            ),
        )


registry = DeterministicRuleRegistry(
    [
        RuleRegistration(
            rule=DoubleSpaceRule(),
            categories=frozenset({Category.STYLE}),
        )
    ]
)

result = analyze_text(
    "To  jest tekst z podwójną spacją.",
    registry=registry,
    local_backend=None,
)
```

Reguły powinny być deterministyczne i lekkie; zachowuj jedną odpowiedzialność na
regułę i preferuj stabilne identyfikatory źródeł.

## Włączanie warstwy zdaniowej dostarczanej ze źródłami

Preferowana konfiguracja wyłącznie zdaniowa współdzieli jeden trwały proces
lokalny między pięcioma zweryfikowanymi regułami przecinkowymi a generowaniem
kandydatów fleksji kontekstowej. Najpierw jawnie zbuduj przypięty podzbiór; Polis
nie pobiera ani nie aktualizuje artefaktów Java:

```console
cd third_party/languagetool-pl
./scripts/build.sh
```

Następnie użyj bezwzględnej ścieżki do pliku wykonywalnego:

```toml
[vendored_language_tool]
stdio_path = "/absolute/path/to/polis/third_party/languagetool-pl/scripts/run_stdio.sh"
timeout_seconds = 2.0
```

Utwórz analizator za pomocą `Analyzer.from_config(...)` i zamknij go przez blok
`with` albo `Analyzer.close()`. Powtarzane wywołania zdaniowe ponownie używają
jednej JVM. Kontrakt source-policy `1.1` automatycznie stosuje wyłącznie
zakwalifikowane znaleziska interpunkcyjne; znaleziska fleksji kontekstowej
pozostają do przeglądu
i wymagają jawnego wyboru przez `apply_suggestions()`. Awarie ścieżki, timeoutu,
niepoprawnej odpowiedzi i procesu są ograniczone i zachowują wbudowane
znaleziska deterministyczne.

Usunięcie `[vendored_language_tool]` wyłącza współdzielony proces.
Skonfigurowana ścieżka musi być bezwzględna i wykonywalna. Ta sekcja wzajemnie
wyklucza się z poniższymi starszymi trybami `[language_tool]`
i `[contextual_inflection]`.

## Włączanie zweryfikowanej warstwy HTTP LanguageTool

Ten tryb kompatybilności jest opcjonalny i domyślnie wyłączony. Uruchom osobno
zainstalowany serwer LanguageTool 6.8 na numerycznym adresie pętli zwrotnej
i dodaj:

```toml
[language_tool]
base_url = "http://127.0.0.1:8081"
timeout_seconds = 1.0
```

Endpoint musi używać zwykłego HTTP, jawnego portu i literału `127.0.0.0/8` albo
`::1`; nazwy hostów, dane uwierzytelniające, ścieżki, zapytania, proxy,
przekierowania, inne wersje i usługi zdalne są odrzucane. Adapter zachowuje tylko
pięć jawnie zweryfikowanych identyfikatorów polskich reguł przecinkowych. Wersja
Source-policy `1.1` automatycznie stosuje ich niekolidujące wstawienia
przecinków; każda inna reguła LanguageTool pozostaje odfiltrowana.

Wywołanie jest synchroniczne i może czekać przez `timeout_seconds`, również
przez `analyze_async()`. Jeśli opcjonalny serwer jest niedostępny albo zwraca
niepoprawne dane, analiza jest kontynuowana z wbudowanymi regułami i bez
znalezisk LanguageTool. Usunięcie `[language_tool]` całkowicie usuwa adapter
z rejestru analizatora.

## Włączanie sugestii fleksji kontekstowej dla każdego wywołania

Zbuduj przypięty moduł lokalny, a następnie wskaż Polis bezwzględną ścieżkę do
jego programu obsługującego stdio:

```toml
[contextual_inflection]
stdio_path = "/absolute/path/to/polis/third_party/languagetool-pl/scripts/run_stdio.sh"
timeout_seconds = 2.0
```

Plik wykonywalny jest wywoływany bezpośrednio, bez powłoki, i dla każdego
kwalifikującego się wywołania otrzymuje jedno zdanie przez standardowe wejście
w nowym procesie. Zwraca wyłącznie skończony zbiór lokalnych kandydatów. Zakwalifikowane
znaleziska nazwisk i wąskiej rekcji pozostają do przeglądu:
`correct()` ich nie stosuje, a wywołujący muszą wybrać ich identyfikatory przez
`apply_suggestions()`. Pominięcie sekcji wyłącza wszystkie operacje wejścia
i wyjścia morfologii kontekstowej. Wejście wielozdaniowe również pomija tę regułę bez uruchamiania
procesu.

Ta sama konfiguracja działa ze zdaniowym przykładem CLI:

```console
python -m polis.cli --config examples/polis.toml analyze --json \
  "Rozmawiałem z Janem Nowak po przerwie."
```

Wyjście JSON zawiera sugestię `Nowakiem` wymagającą przeglądu. CLI nie stosuje jej,
dopóki identyfikator znaleziska nie zostanie jawnie przekazany przez `--apply`.
