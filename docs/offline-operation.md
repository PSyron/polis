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
