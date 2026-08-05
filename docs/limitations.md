# Ograniczenia v1

- Polis obsługuje wyłącznie mały zbiór deterministycznych reguł opisanych w
  [rules.md](rules.md); nie jest pełnym korektorem języka polskiego.
- Nie zmienia znaczenia, intencji, faktów, czasu, aspektu, stylu ani tonu.
- Niepewne, niejednoznaczne albo kolidujące przypadki pozostają bez
  automatycznej korekty.
- `correct()` stosuje tylko kwalifikowane zachowania; pozostałe znaleziska
  można wybrać jawnie przez `CorrectionResult.apply_suggestions()`.
- Runtime działa offline i nie wymaga sieci, modelu, procesu Java ani
  instalacji dodatkowych usług.
- Wspierane są zwykłe napisy Pythona oraz indeksy Unicode `[start, end)`; Polis
  nie zachowuje struktury dokumentów biurowych i nie dostarcza GUI.

Historyczne badania nie rozszerzają tych ograniczeń. Ich pełny stan jest
odtwarzalny z lokalizacji wskazanej przez
[manifest archiwum v2](project/v2-research-archive-manifest.md).
Opcjonalne badania nad modelem nigdy nie blokują wydania runtime'u. Ścieżka
wydania runtime'u nie wymaga modelu, procesu Java, usługi sieciowej, korpusu
badawczego ani zużytego holdoutu.
