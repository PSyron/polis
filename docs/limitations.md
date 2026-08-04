# Znane ograniczenia i granica produktu

- Bieżący runtime obejmuje niewielki zestaw reguł deterministycznych i ścieżkę
  atrapowego backendu lokalnego.
- Polis jest kompletnym runtime'em offline bez modelu. Żaden element wsparcia
  produkcyjnego nie czeka na kwalifikację modelu, a opcjonalne badania nad
  modelem nigdy nie blokują wydania runtime'u. Ścieżka wydania runtime'u nie
  wymaga modelu, procesu Java, usługi sieciowej, korpusu badawczego ani zużytego
  holdoutu.
- Integracja generowania lokalnego jest dostępna przez ścieżkę atrapowego
  transportu. Żaden przetestowany model lokalny nie został zakwalifikowany do
  poprawek ani sugestii produkcyjnych; naprawione dowody, prompty
  specjalistyczne, porównanie środowisk wykonawczych i prace nad adapterami
  pozostają opcjonalnymi dowodami badawczymi.
- Silnik specjalistyczny i granica routera z #60 są zaimplementowane i
  przetestowane przy użyciu wstrzykniętych atrap. Żaden domyślny router nie
  identyfikuje pozostałych problemów składniowych ani fleksyjnych, a dla
  wspieranego runtime'u nie skonfigurowano rzeczywistego backendu
  specjalistycznego.
- Router kategorii dla pojedynczego zdania z #69 jest eksperymentalny i nie jest
  podłączony do domyślnego analizatora. Jego najlepsza konfiguracja, Qwen3 1.7B
  MLX, osiągnęła w zbiorze deweloperskim zaledwie precyzję 0.571 i czułość 0.160
  dla składni. Bielik 1.5B i Qwen3 0.6B nie wygenerowały żadnych dokładnych
  poprawek składniowych. Żadna konfiguracja nie została zakwalifikowana, a
  holdout corpus-v3 pozostaje nieotwarty dla tego eksperymentu.
- Issue #70 zakwalifikowało pięć identyfikatorów reguł interpunkcyjnych
  LanguageTool dla zdań przy precyzji 1.00 i czułości 0.038 na jednorazowym
  holdoucie. `source-policy 1.1` jest historycznym zapisem kwalifikacji
  wszystkich pięciu sprawdzonych identyfikatorów. Aktywna `source-policy 1.2`
  zachowuje wyłącznie to członkostwo przy dokładnej tożsamości zachowania
  `check.allowlisted_comma` / `pl-6.8-five-rule-comma/1.0`. Nadal jest to wąski
  zakres interpunkcji, który nie poprawia składni ani fleksji.
- Router fleksji kontekstowej dla pojedynczego zdania osiągnął precyzję 1.00 i
  czułość 0.667 dla obsługiwanych przypadków na jednorazowym holdoucie oraz jest
  dostępny przez opcjonalną lokalną konfigurację stdio. Zwraca wyłącznie
  sugestie do przeglądu;
  nie są obsługiwane niejednoznaczności imion, zgoda czasownika, większość
  związków rządu ani jakiekolwiek zachowanie dla akapitów.
- Issue #74 ponownie przetestowało przypięty model Qwen3 1.7B MLX z ogólnym
  weryfikatorem, listą kontrolną dotyczącą dowodów wraz z weryfikatorem oraz
  rozdzielonymi diagnozą i korektą. Najlepsza precyzja wyniosła 1.00 przy
  zaledwie 0.04 czułości dla składni; najlepsza czułość wyniosła 0.16 przy
  precyzji 0.571. Żadna ścieżka nie została zakwalifikowana, holdout pozostaje
  nieotwarty, a żaden rzeczywisty model nie jest włączony dla sugestii
  składniowych w zdaniach.
- Issue #75 dodaje deterministyczne sugestie do przeglądu wyłącznie dla trzech
  konstrukcji na początku zdania: brakującego `się` po `On/Ona/Ono boi` lub
  `Nie spodziewaliśmy` oraz brakującego `tym` w `Im …, bardziej …`. Zbiór
  deweloperski dał 3 poprawne poprawki i żadnych wyników fałszywie dodatnich,
  przy precyzji 1.00. Jednorazowy holdout obejmujący 142 zdania nie zawierał
  żadnej kwalifikującej się konstrukcji, dlatego nie powstały żadne poprawki i
  nie można było ustalić niewakuicznej precyzji. Te źródła nie są stosowane
  automatycznie, nie uogólniają się na inne czasowniki zwrotne ani błędy szyku i
  wstrzymują się od działania na wejściu wielozdaniowym.
- Bramka bezpieczeństwa zdań corpus-v3 uruchamiana na zainstalowanym pakiecie
  nie została zakwalifikowana, a jej jednorazowy holdout jest zużyty. Niezależny
  `polis_polish_correction_safety_corpus_v1` na licencji CC0-1.0 został
  zamrożony i sprawdzony przez właściciela. Issue #115 zakwalifikowało jego
  80-przypadkowy podział deweloperski, po czym dokładnie raz uruchomiło
  niezależny holdout obejmujący 160 przypadków. Holdout zakończył się
  niepowodzeniem: precyzja automatyczna i trafność korekty wyniosły `1.00`,
  lecz kanał do przeglądu dał `0 TP / 2 FP` i precyzję `0.00` wobec wymaganego
  `0.90`. Holdout jest zużyty i nie wolno go ponownie uruchamiać ani używać do
  dostrajania. Korpus nie zastępuje corpus-v3 ani szerszych opcjonalnych prac
  badawczych śledzonych w #85, a #76 pozostaje otwarte.
- Ocenione rozszerzenie zgodności nominalnej osiągnęło czułość fleksji do
  przeglądu `18/20` w zbiorze deweloperskim, lecz kompletne źródło do przeglądu
  dało `0 TP / 2 FP` na jednorazowym holdoucie. Po tym wyniku rozszerzenie
  usunięto z aktywnego runtime'u. Nie wybrano zamiennika ani nie dostrajano go na
  podstawie zużytych rekordów; zgodność podmiotu zbiorowego i kwantyfikującego
  pozostaje nieobsługiwana.
- Issue #119 przygotowuje `polis_polish_correction_safety_corpus_v2` jako
  niezależny zasób kwalifikacyjny na licencji CC0-1.0. Wszystkie 240 przypadków
  zostało sprawdzonych przez uprawnioną rolę `Polis architecture owner` i
  zamrożonych z kanonicznym skrótem JSON SHA-256
  `53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29`.
  Nie daje to wyniku jakości dla zbioru deweloperskiego ani holdoutu, nie odwraca
  nieudanego wyniku #115 i nie kwalifikuje #76. Nadal wymagana jest osobna
  jednorazowa bramka. Ta praca pozostaje odrębna od #85 i #90.
- Issue #146 uruchomiło 80 przypadków deweloperskich w dwóch stabilnych
  powtórzeniach przy niezmienionych bramkach dla pojedynczych zdań i nie zostało
  zakwalifikowane. Precyzja automatyczna i trafność korekty wyniosły `1.00`, a
  czułość `0.3333333333333333`; kanał do przeglądu nie zaproponował żadnych
  poprawek i nie spełnił wymaganej bramki niewakuicznej precyzji. Poprawność
  strukturalna wyniosła `1.00`, a obie liczby chronionych przypadków negatywnych
  wyniosły zero. Skrót SHA-256 raportu zbiorczego to
  `7485c543a5abcfe45096cfc9334b59cf4c5dd510186c6318a44d0c38cdeb1141`.
  Nie istnieje zamrożona bramka, znacznik jest nieobecny, a holdout nie został
  zarezerwowany, zmaterializowany ani uruchomiony. Zbiór deweloperski nie będzie
  ponownie uruchamiany ani używany do dostrajania. #76 pozostaje otwarte, a
  `Task 6` jest zabronione. Wynik nie kwalifikuje modelu produkcyjnego ani
  zachowania dla akapitów.
- Adaptery dokumentów DOCX/ODT/RTF nie należą jeszcze do zakresu tego
  repozytorium.
- GUI nie jest dołączone.
- Polis nie wykonuje szerokiego przepisywania stylistycznego; poprawki są
  ograniczone i celowo zachowawcze.
- Domyślna instalacja nie zawiera modelu produkcyjnego ani zależności od
  LanguageTool. Korpusy badawcze, narzędzia uruchamiające benchmarki, zasoby
  treningowe i dowody z holdoutów pozostają procesami dostępnymi wyłącznie w
  repozytorium; nie ustanawiają wsparcia produkcyjnego, a opcjonalne badania nad
  modelem nigdy nie blokują wydania runtime'u.
- Domyślny runtime Polis nie wymaga OpenJDK, procesu LanguageTool, modelu ani
  dostępu do sieci. Opcjonalna ścieżka LanguageTool dla pojedynczego zdania,
  budowana z dostarczonych źródeł, wymaga OpenJDK i jawnego lokalnego zbudowania
  przypiętego podzbioru 6.8. Ponownie wykorzystuje ona jedną trwałą maszynę JVM
  obsługiwaną przez stdio; benchmark #77 zmierzył łącznie 441,483,264 bajty RSS
  Pythona i Javy, zimny start 938.60 ms oraz 5.08 ms dla rozgrzanego p95.
  Artefakty Java nie są dołączone do wheel ani sdist, a Polis ich nie pobiera.
- Starszy opcjonalny tryb HTTP nadal wymaga osobno uruchomionego procesu
  LanguageTool 6.8 na interfejsie loopback. Nie można jednocześnie włączyć obu
  trybów.
- Reguła LanguageTool jest synchroniczna. Zarówno `analyze()`, jak i
  `analyze_async()` mogą czekać do upływu skonfigurowanego limitu czasu, a reguła
  obejmuje wyłącznie pięć sprawdzonych identyfikatorów reguł brakującego
  przecinka.
- Zbudowany ze źródeł podzbiór pięciu reguł LanguageTool nie jest ogólnym
  korektorem języka polskiego. Tylko te zakwalifikowane znaleziska przecinkowe są
  automatyczne przy aktywnej `source-policy 1.2`, gdy pasuje ich pełna
  tożsamość zachowania; `source-policy 1.1` pozostaje historycznym zapisem
  kwalifikacji. Fleksja kontekstowa podlega przeglądowi, działa tylko dla
  pojedynczych zdań i ogranicza się do wąskich konstrukcji, a zachowanie dla
  akapitów nie przeszło bramki wydania M5.
- `polis.evaluation` zachowuje zgodność importów dla istniejących narzędzi
  pomocniczych ewaluatora w bieżącej linii 0.x, ale nie jest głównym API analizy
  runtime'u. Duże korpusy, holdouty, raporty, eksperymenty i zasoby treningowe są
  wykluczone z artefaktów wheel i dystrybucji źródłowej.
- Architektura hybrydowa z
  [ADR-0008](architecture/decisions/0008-hybrid-correction-policy.md) jest
  zaimplementowana jako bazowe zachowanie dostarczania w #60.
  `Analyzer.correct()` i `correct_async()` korzystają ze wspólnej ścieżki
  orkiestracji, stosują wersjonowaną politykę źródeł dla reguł
  deterministycznych, pozostawiają każdą poprawkę modelu do przeglądu oraz
  ujawniają stan opcjonalnej sugestii, faktyczną liczbę wywołań i obowiązującą
  wersję polityki. Polityka `1.2` wymusza dokładną tożsamość zachowania; nie
  kwalifikuje kolejnej reguły, funkcji LanguageTool ani modelu.
  [ADR-0020](architecture/decisions/0020-runtime-first-product-charter.md)
  zastępuje wyłącznie ścieżkę krytyczną wymagającą modelu; nie przepisuje
  opisanych wyżej nieudanych wyników kwalifikacji.

## Uwagi o trafności i polityce

System jest z założenia zachowawczy:

- pominięte znaleziska są preferowane zamiast agresywnego przepisywania,
- nierozstrzygalne poprawki nie są stosowane,
- wybór poprawek jest jawny.

Zapoznaj się ze znanymi ograniczeniami w `docs/quality-baseline.md` i planowaniem
wydania w `docs/project/ROADMAP.md`.
