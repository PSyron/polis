# Gwarancje segmentacji

## Przeznaczenie

`polis.segmentation` udostępnia stabilne obiekty zakresów dla segmentacji akapitów
i zdań. Każdy zakres przechowuje przesunięcia w konwencji półotwartej
`[start, end)` względem oryginalnego wejścia oraz dokładny wycinek `text` z tego
zakresu.

## API

- `segment_paragraphs(text: str) -> tuple[Paragraph, ...]`
- `segment_sentences(text: str) -> tuple[Sentence, ...]`
- `Segment(start: int, end: int, text: str)`
- `Paragraph(start: int, end: int, text: str)`
- `Sentence(start: int, end: int, text: str)`

Oczekuje się, że `text` jest oryginalnym napisem Pythona zdekodowanym z UTF-8.
Przesunięcia są indeksami Pythona liczonymi w punktach kodowych Unicode.

## Zachowanie parsera

- Akapity są rozdzielane na granicach pustych wierszy (w tym przy zakończeniach
  wierszy CRLF i z mieszaną białą spacją).
- Granice zdań są wykrywane na podstawie znaków interpunkcyjnych (`.`, `?`, `!`)
  i prostych znaków zamykających, takich jak interpunkcja, cudzysłowy i prawe
  nawiasy.
- Skróty z niewielkiej listy heurystycznej (`np`, `itd`, `itp`, `m.in`, `dr`, ...)
  nie są dzielone jako końcowe granice zdań.
- Kropki dziesiętne (cyfra, kropka, cyfra), na przykład `3.14`, nie są traktowane
  jako końce zdań.
- Wycinki segmentów po połączeniu w kolejności implementacji odtwarzają oryginalne
  wejście.

## Generowana bariera strukturalna

Issue #125 uruchamia ograniczony syntetyczny generator Unicode z issue #123 dla
obu segmenterów. Sprawdza uporządkowane, ciągłe i ograniczone zakresy punktów
kodowych Unicode w konwencji półotwartej `[start, end)`, dokładne wycinki źródła
oraz dokładne odtworzenie oryginalnego źródła. Przebieg obejmujący 64 przypadki
pokrywa zadeklarowane przez generator rodziny ASCII, polskich znaków
diakrytycznych, znaków spoza BMP, znaków łączących, LF, CRLF, interpunkcji
i cudzysłowów, w tym jawny przypadek pustego wejścia.

Błędy zgłaszają wyłącznie stabilny identyfikator niezmiennika oraz
deterministyczne metadane powtórzenia, nigdy wygenerowany tekst źródłowy. Jest to
bariera strukturalna: nie zmienia heurystyk segmentacji, nie zastępuje autorskich
regresji językowych ani nie deklaruje pokrycia językowego. Kontrakt generatora
i powtórzenia opisuje
[`docs/development/generative-invariants.md`](development/generative-invariants.md).

## Ograniczenia i znane zastrzeżenia

- Jest to deterministyczna heurystyka, a nie pełny model językowy.
- W miarę rozszerzania pokrycia przypadki brzegowe z wieloma spacjami i mieszaną
  interpunkcją powinny otrzymywać dedykowane testy.
- Heurystyka nie obiecuje rozstrzygać każdej niejednoznacznej granicy zdania
  w polskiej prozie, a jedynie te wymagane dla milestone'u `M1-01`.
