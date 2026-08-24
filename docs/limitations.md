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
- Opcjonalne extra `morphology` rozszerza wąsko ograniczone rodziny review-only,
  w tym lokalną zgodę przymiotnika z rzeczownikiem oraz zamkniętą tabelę rekcji
  `szukać`, `używać`, `ufać`, `interesować się` i `do`; nie stanowi ogólnej
  obsługi polskiej fleksji, zgody ani rekcji. Rekcja przyjmuje tylko jednoznaczny
  rzeczownik pospolity albo grupę `przymiotnik + rzeczownik` i abstainuje dla
  nazw własnych, zaimków, wołacza, koordynacji, elipsy (`...` i `…`),
  niezgodnej liczby lub rodzaju w grupie przymiotnik–rzeczownik, niepełnych danych
  oraz dryftu providera. Morfeusz2 1.99.15 nie ma
  opublikowanego sdistu ani kół Linux arm64/musl; jego koła obejmują macOS
  universal2, manylinux 2.28 x86_64 oraz Windows amd64.
- Dryft tożsamości opcjonalnego providera jest obserwowalny przez
  `Analyzer.morphology_status` oraz jednorazowy `UserWarning`, ale nadal
  uruchamia abstencję reguł zależnych od morfologii; nie oznacza to ogólnej
  obsługi polskiej morfologii ani automatycznej akceptacji innego słownika.
- Wspierane są zwykłe napisy Pythona oraz indeksy Unicode `[start, end)`; Polis
  nie zachowuje struktury dokumentów biurowych i nie dostarcza GUI.

Historyczne badania nie rozszerzają tych ograniczeń. Ich pełny stan jest
odtwarzalny z lokalizacji wskazanej przez
[manifest archiwum v2](project/v2-research-archive-manifest.md).
Opcjonalne badania nad modelem nigdy nie blokują wydania runtime'u. Ścieżka
wydania runtime'u nie wymaga modelu, procesu Java, usługi sieciowej, korpusu
badawczego ani zużytego holdoutu.
