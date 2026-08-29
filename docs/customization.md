# Personalizacja

Wspierana konfiguracja v1 ogranicza się do lokalnego pliku TOML:

```toml
[analysis]
categories = ["inflection", "agreement", "syntax", "spelling", "punctuation"]
minimum_confidence = 0.8
```

`AnalyzerConfig.from_toml(path)` i `Analyzer.from_config(path)` odczytują tylko
jawnie wskazany plik. `categories` ogranicza analizę do wartości `Category`, a
`minimum_confidence` odrzuca mniej pewne znaleziska. Niepodana kategoria
oznacza wszystkie kategorie.
Znaczenie pięciu kategorii emitowanych przez analizator, ich ograniczenia i
zgodnościową wartość `style` opisuje [słownik kategorii](categories.md).
`style` można przekazać jako wartość enumu, ale domyślny analizator nie emituje
znalezisk stylu, więc taki filtr może zwrócić pusty wynik.
`minimum_confidence` musi być liczbą skończoną z przedziału domkniętego
`0.0`–`1.0`; wartości logiczne, tekstowe, nieskończone i spoza zakresu kończą
się kontrolowanym `ConfigurationError` już podczas tworzenia lub wczytywania
konfiguracji.

W CLI obowiązuje kolejność: jawna flaga `--category` albo
`--minimum-confidence`, następnie wartość z pliku TOML, a na końcu wbudowana
wartość domyślna. Flaga zastępuje tylko odpowiadające jej pole, więc na przykład
`--category punctuation` zachowuje `analysis.minimum_confidence` z pliku.
Wywołanie bez pliku i bez tych flag analizuje wszystkie kategorie z progiem
`0.0`. Efektywne wartości są widoczne w polu `options` wyniku `--json`.

Regułę można dodać wyłącznie w zmianie runtime'u: implementuje ona `Rule`, ma
unikatowe stabilne `source`, deklaruje kategorie oraz zachowanie i przechodzi
testy przesunięć, filtrowania i polityki automatycznej. Nie twórz rozszerzenia
bez bieżącego konsumenta. Szczegóły rejestru opisują [reguły](rules.md).
