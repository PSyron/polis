# Personalizacja

Wspierana konfiguracja v1 ogranicza się do lokalnego pliku TOML:

```toml
[analysis]
categories = ["agreement", "spelling", "syntax", "punctuation"]
minimum_confidence = 0.8
```

`AnalyzerConfig.from_toml(path)` i `Analyzer.from_config(path)` odczytują tylko
jawnie wskazany plik. `categories` ogranicza analizę do wartości `Category`, a
`minimum_confidence` odrzuca mniej pewne znaleziska. Niepodana kategoria
oznacza wszystkie kategorie.

Regułę można dodać wyłącznie w zmianie runtime'u: implementuje ona `Rule`, ma
unikatowe stabilne `source`, deklaruje kategorie oraz zachowanie i przechodzi
testy przesunięć, filtrowania i polityki automatycznej. Nie twórz rozszerzenia
bez bieżącego konsumenta. Szczegóły rejestru opisują [reguły](rules.md).
