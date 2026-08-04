# Lista kontrolna przeglądu roli dla korpusu bezpieczeństwa zdań v2

Ta lista kontrolna reguluje wszystkie 240 rekordów w
`polis_polish_correction_safety_corpus_v2`. Generowanie kandydatów i automatyczna
walidacja nie mogą udzielić zatwierdzenia. Zgodnie z zaakceptowanym
doprecyzowaniem w issue #119 rola `Polis architecture owner` może zatwierdzić
pełny skrót kandydata i zmienić rekordy z `pending-human-review` na
`human-reviewed`. Zapis roli jest granicą upoważnienia, a nie wskazaniem osoby.

Wykonaj przegląd kanonicznego pliku JSON. Dla każdego rekordu potwierdź wszystkie
poniższe punkty przed zapisaniem zatwierdzenia wszystkich przypadków.

## Poprawność

- Wejście jest wiarygodnym polskim zdaniem i zawiera deklarowany problem albo
  jest w pełni poprawne, gdy warstwą jest `hard_negative`.
- Oczekiwane wyjście jest gramatyczne i zachowuje oryginalne znaczenie, rejestr,
  wielkość liter oraz nieobjęte zmianą formatowanie.

## Kategoria

- Zadeklarowana warstwa jest głównym zjawiskiem sprawdzanym przez przypadek.
- Przypadki pozytywne należą do dokładnie jednej z kategorii `inflection`,
  `syntax` albo `punctuation`; przypadki chronione należą do `hard_negative`.

## Minimalność

- Każde pozytywne oczekiwane wyjście zmienia wyłącznie najmniejszy uzasadniony
  fragment.
- Sugestia nie przepisuje poprawnego otaczającego tekstu.
- Każdy trudny przypadek negatywny nie ma edycji i zachowuje wejście bez zmian.

## Przesunięcia

- Każda edycja używa półotwartego zakresu Unicode `[start, end)` w oryginalnym
  wejściu.
- `input[start:end]` jest dokładnie równe zapisanemu oryginalnemu fragmentowi.
- Zakresy encji pokrywają dokładnie zapisaną kontrolowaną formę powierzchniową.

## Rekonstrukcja

- Zastosowanie zadeklarowanej edycji do oryginalnego wejścia dokładnie odtwarza
  oczekiwane wyjście.
- Edycje nie nakładają się i nie zależą od wcześniej zmodyfikowanego napisu.

## Obsługa nazw własnych

- Nazwy osób i miejsc zachowują zamierzoną pisownię, wielkość liter i odmianę.
- Każda kontrolowana forma powierzchniowa nazwy ma kompletny zakres encji
  i kanoniczny identyfikator.
- Żaden zwykły wyraz rozpoczynający zdanie wielką literą nie jest błędnie
  oznaczony jako encja.

## Składnia i szyk wyrazów

- Zgodność podmiotu z orzeczeniem, rekcja, negacja i kwantyfikacja są oceniane
  w kontekście pełnego zdania.
- Nacechowany, ale gramatyczny szyk wyrazów nie jest normalizowany wyłącznie ze
  względów stylistycznych.

## Proweniencja

- Zdanie jest autorskim, syntetycznym polskim tekstem projektu utworzonym dla
  issue #119.
- Nie zostało skopiowane, sparafrazowane ani wyprowadzone z korpusu v3, korpusu
  bezpieczeństwa v1, przykładów promptów, zasobów do dostrajania, danych testowych
  E2E ani tekstu prywatnego.

## Licencjonowanie

- Przypadek może zostać wydany na licencji CC0-1.0.
- Nie osadzono cytatu podmiotu trzeciego, rekordu zbioru danych ani tekstu
  objętego ograniczeniami.

## Izolacja

- Przypisanie do części deweloperskiej lub holdoutu pozostaje bez zmian podczas
  przeglądu.
- Przypadek nie wprowadza ponownie użytego wejścia, znormalizowanego szablonu,
  kombinacji encji, kanonicznego identyfikatora encji ani rodziny bliskich
  duplikatów językowych z zastrzeżonego zasobu.
- Treść ani wyniki holdoutu korpusu bezpieczeństwa v1 na poziomie przypadku nie
  wpłynęły na kandydata.

## Zatwierdzenie i zamrożenie

Zatwierdzenie obejmuje wszystko albo nic i musi wskazywać:

- identyfikator korpusu `polis_polish_correction_safety_corpus_v2`;
- wszystkie 240 przypadków;
- SHA-256 kanonicznego JSON-u kandydata;
- rolę recenzenta `Polis architecture owner`;
- datę przeglądu w formacie ISO-8601;
- wersję listy kontrolnej `safety-corpus-review-v2`.

Nie twórz manifestu zatwierdzenia, nie ustawiaj `holdout_state` na `frozen`, nie
dodawaj metadanych `human-reviewed` ani nie zapisuj zamrożonego skrótu, dopóki
każdy przypadek nie przejdzie tej listy kontrolnej. Ten przegląd nie wytwarza wyniku
jakości dla części deweloperskiej ani holdoutu i nie upoważnia do dostępu do
holdoutu.

## Zapisane zatwierdzenie

Rola `Polis architecture owner` ukończyła wyczerpujący przegląd wszystkich
przypadków 2026-08-02, korzystając z wersji listy kontrolnej
`safety-corpus-review-v2`. Zatwierdzenie wiąże SHA-256 kanonicznego JSON-u
kandydata
`c64f009f14f0cde8390a46acc24660305534576bc897f70e281ffebbbbca6f53`
z SHA-256 zamrożonego kanonicznego JSON-u
`53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29`.
Zatwierdzenie obejmuje wszystkie 240 przypadków i nie wytwarza wyniku jakości
dla części deweloperskiej ani holdoutu.
