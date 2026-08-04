# Szybki start z Polis

Ten projekt stawia runtime na pierwszym miejscu i działa offline: domyślny
analizator działa w procesie i nie wysyła danych wejściowych do usług
zewnętrznych. Żaden przetestowany model lokalny nie został zakwalifikowany do
poprawek ani sugestii produkcyjnych.

Domyślna instalacja nie zawiera modelu produkcyjnego ani zależności od
LanguageTool. LanguageTool jest opcjonalnym adapterem lokalnym o wąskim zakresie
ograniczonym do pojedynczych zdań; włączaj go wyłącznie przez jawnie dostarczoną
przez wywołującego usługę na interfejsie loopback albo osobno zbudowany plik
wykonywalny z dostarczonych źródeł. Polis nie zawiera adapterów DOCX/ODT/RTF,
GUI ani przepisywania stylistycznego.

## Instalacja zależności

```console
uv sync --locked --extra dev
```

## Użycie API

```python
from polis import Analyzer, AnalyzerConfig, AnalysisOptions

analyzer = Analyzer(AnalyzerConfig())
result = analyzer.analyze("Witaj, świecie.")

options = AnalysisOptions(categories={"spelling", "punctuation"}, minimum_confidence=0.5)
filtered = analyzer.analyze("Witaj, świecie.", options=options)
print(len(filtered.issues))
```

## Użycie CLI

```console
python -m polis.cli analyze --json "Witaj,świecie."
printf 'Witaj,świecie.' | python -m polis.cli analyze --stdin --json
```

## Stosowanie wybranych znalezisk

```python
result = analyzer.analyze("Witaj,świecie.")
first = result.issues[0].id
corrected = result.apply((first,))
print(corrected)
```

Automatyczna korekta jest zachowawcza: stosowane są wyłącznie objęte polityką,
deterministyczne znaleziska o wysokiej pewności i bez konfliktów. Znaleziska
pochodzące od modelu oraz znaleziska kontekstowe podlegają przeglądowi, dopóki
wywołujący nie wybierze ich jawnie.

Korpusy badawcze, narzędzia uruchamiające benchmarki i procesy dotyczące
holdoutów są zasobami programistycznymi dostępnymi wyłącznie w repozytorium.
Uruchamiaj je za pomocą poleceń z przewodnika po procesie badawczym, a nie w
ramach domyślnego szybkiego startu runtime'u. `polis.evaluation` zachowuje
zgodność importów jako przestrzeń nazw ewaluatora w bieżącej linii 0.x; nie jest
głównym API analizy.
