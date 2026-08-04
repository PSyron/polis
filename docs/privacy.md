# Gwarancje prywatności

Polis jest przeznaczony do analizy lokalnej. Analizowany tekst nie opuszcza
urządzenia użytkownika i nie jest wysyłany do usług sieciowych.

Obecne gwarancje:

- `polis.analyzer.Analyzer` i reguły deterministyczne działają w całości
  w procesie Polis.
- CLI korzysta ze standardowego wejścia albo tekstu przekazanego w argumencie;
  nie utrwala go ani nie wysyła.
- `PolisError.context` celowo zawiera wyłącznie metadane operacji (`operation`,
  `backend`, `path`, `finding_ids`), nigdy analizowane fragmenty, pełne prompty
  ani surowe payloady odpowiedzi.
- Wyniki specjalistyczne zawierają wyłącznie stabilny identyfikator backendu,
  wersje operacji i protokołu, status, liczbę sugestii oraz liczbę wywołań.
  Nigdy nie przenoszą tekstu źródłowego, kandydatów, promptów, propozycji ani
  surowych odpowiedzi.
- `[vendored_language_tool]` przesyła tylko jedno zdanie do jednego stale
  działającego procesu potomnego przez lokalne stdin/stdout. Proces potomny nie
  otwiera gniazd sieciowych, a Polis nie pobiera ani nie aktualizuje jego
  artefaktów Java.

## Domyślne zachowanie operacyjne

- Wyjątki są typowane i stabilne (`code`, `retryable`, `context`), aby ich
  lokalna obsługa była jawna.
- W przypadku awarii lokalnego backendu problemy transportu lub protokołu są
  mapowane na ustrukturyzowane błędy operacyjne zamiast ujawniać szczegóły
  wewnętrzne backendu.
- Awarie opcjonalnego specjalisty używają stałej diagnostyki chroniącej
  prywatność i zachowują ukończone znaleziska deterministyczne. Wstrzyknięcie
  zależności nie zezwala na zdalny transport: adapter produkcyjny musi osobno
  wymuszać wykonanie wyłącznie lokalne.
- Awarie vendored stdio ujawniają tylko diagnostykę na poziomie operacji; błędy
  nie zawierają tekstu żądania, payloadów odpowiedzi, kandydatów ani poprawek.
  Usunięcie `[vendored_language_tool]` usuwa tę opcjonalną granicę procesu.

## Zalecane praktyki użytkownika

Podczas testowania i pisania skryptów:

- nie zapisuj w logach pełnych tekstów użytkownika na poziomie `DEBUG`;
- nie przechowuj plików tymczasowych z wrażliwym tekstem w ścieżkach
  dostępnych do odczytu dla wszystkich użytkowników;
- rotuj tymczasowe pliki robocze, gdy przechwytujesz wejście lub wyjście CLI.

## Stan audytu

Dowody dotyczące prywatności i zależności na potrzeby wydania zawiera
[audyt prywatności i zależności](privacy-audit.md). Dokumentuje on kontrole przy
zablokowanej sieci, skanowanie artefaktów, stan wykrywania sekretów oraz ryzyka
rezydualne.
