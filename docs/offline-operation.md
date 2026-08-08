# Praca offline

Domyślny `Analyzer(AnalyzerConfig())` wykonuje wyłącznie lokalne reguły
deterministyczne. Nie otwiera połączeń sieciowych, nie uruchamia procesu
pomocniczego i nie pobiera zasobów.

```python
from polis import Analyzer, AnalyzerConfig

result = Analyzer(AnalyzerConfig()).analyze("Witaj,świecie.")
```

Konfiguracja jest lokalnym plikiem TOML wskazanym przez wywołującego. Tylko
sekcja `[analysis]` jest interpretowana i wspierana; jej klucze to `categories`
i `minimum_confidence`. Dokładnie historyczne tabele `[backend]`, `[language_tool]`,
`[contextual_inflection]` i `[vendored_language_tool]` są odrzucane przez
`ConfigurationError` z kodem `configuration.unsupported_section`. Inne nieznane
tabele i klucze parser obecnie ignoruje; nie są wspieranym interfejsem i nie
należy na tym zachowaniu polegać.

Testy i dystrybucje weryfikują tę granicę w izolowanym środowisku. Aplikacja
wywołująca odpowiada za własne logowanie i magazynowanie tekstu; Polis nie
wysyła wejścia poza proces.

## Opcjonalna morfologia

Extra `polis-nlp[morphology]` instaluje Morfeusz2 1.99.15 wyłącznie dla trzech
zamkniętych sugestii: `Nie widzę czerwony samochód.` →
`Nie widzę czerwonego samochodu.`, `Te duże okno jest otwarte.` →
`To duże okno jest otwarte.` oraz `Oni czyta książkę.` →
`Oni czytają książkę.`. Wszystkie pozostają do przeglądu. Dostawca analizuje
i generuje formy lokalnie; nie otwiera połączenia, nie pobiera słownika i nie
uruchamia procesu Java.

Runtime sprawdza wersję pakietu, identyfikator słownika
`pl.sgjp.sgjp-2026.06.01` oraz skrót jego noty. Brak extra, błąd dostawcy,
niepełne dane, niejednoznaczna analiza lub dryft któregokolwiek elementu
powodują abstencję. Pozostałe reguły działają wtedy normalnie.
