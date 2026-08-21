# Kwalifikacja niezależnych od providera błędów pisowni v1 (#402)

## Wynik

Kwalifikacja obejmuje dokładnie sześć zamkniętych powierzchni. Wszystkie
uzyskały decyzję `accept: deterministic provider-absent`, ponieważ forma
docelowa i minimalny zakres są jednoznaczne, a publiczny, projektowy materiał
spełnia minima dowodowe. `PI-TYPO-01` jest zaimplementowany przez #404 jako
review-only; pozostałe pięć wierszy nie ma jeszcze implementacji runtime.

| Kolejność | Wiersz | Wejście | Minimalny cel | Proponowane źródło | Behavior version |
| ---: | --- | --- | --- | --- | --- |
| 1 | `PI-TYPO-01` | `coniemiara` | `co niemiara` | `rule:spelling.co_niemiara` | `spelling-co-niemiara/1.0` |
| 2 | `PI-TYPO-02` | `złodzieji` | `złodziei` | `rule:spelling.zlodzieji` | `spelling-zlodzieji/1.0` |
| 3 | `PI-TYPO-03` | `conieco` | `co nieco` | `rule:spelling.co_nieco` | `spelling-co-nieco/1.0` |
| 4 | `PI-TYPO-04` | `invitro` | `in vitro` | `rule:spelling.in_vitro` | `spelling-in-vitro/1.0` |
| 5 | `PI-TYPO-05` | `na przeciwko` | `naprzeciwko` | `rule:spelling.naprzeciwko_spacing` | `spelling-naprzeciwko-spacing/1.0` |
| 6 | `PI-TYPO-06` | `niewiem` | `nie wiem` | `rule:spelling.nie_wiem` | `spelling-nie-wiem/1.0` |

Każdy przyszły finding ma kategorię `spelling`, severity `suggestion`,
minimalny półotwarty zakres `[start, end)` względem oryginalnego tekstu i
wymaga jawnego `AnalysisResult.apply()`. Kwalifikacja nie dodaje żadnego
wpisu do automatic correction policy.

## Dowody publiczne

Korpus
`tests/fixtures/v1/provider_independent_spelling_qualification.json` jest
autorskim materiałem CC0 Pawła Cyronia. Nie kopiuje przykładów z raportu
częstości, danych prywatnych, holdoutów ani zamkniętych korpusów. Zawiera 144
przypadki:

- 48 przypadków pozytywnych i 54 dokładne expected findings;
- 96 poprawnych hard negatives;
- dla każdego wiersza: 8 przypadków pozytywnych, 9 expected findings,
  16 hard negatives i 4 kontrolowane pary;
- dla każdego wiersza obie strony wszystkich siedmiu strat #364:
  `simple-local`, `sentence-internal`, `multi-sentence`,
  `repeated-occurrence`, `unicode-and-case`,
  `quotation-or-literal` i `conflict-or-abstention`;
- dla każdego wiersza dokładne warianty lowercase, inicjalny i ALL CAPS wraz
  z odpowiadającym casing sugestii;
- identyczną decyzję dla profilu `provider-absent` i profilu z Morfeuszem,
  ponieważ żaden kandydat nie korzysta z providera.

Manifest wiąże kompletny uporządkowany zbiór ID przypadków i kanoniczny digest
corpusu. Tożsamości wynoszą:

- canonical corpus SHA-256:
  `a82a4c93338e9bde8ea011f89d47010642a74ed43800cec53b8f298c6b46f727`;
- ordered case-ID SHA-256:
  `44e0adf2322307827329285da4b474083e332eb656164a331b5a87741ec66168`;
- qualification matrix SHA-256:
  `b0486476564de67b3e9e40a4026ad1fa422121c17146e6ebc58331875aaa906e`.

Raport o błędach w internecie z 2024 roku służy wyłącznie do ustawienia
kolejności pięciu pierwszych powierzchni. Nie jest źródłem normy ani
przykładów gold. Normę i formy docelowe wiążą wskazane w macierzy materiały
NCK, WSJP PAN i RJP 2026. `niewiem` jest projektowym kandydatem zamkniętym,
nie wierszem rankingu raportu.

## Granica fail-closed

Późniejsza reguła może przyjąć tylko dokładną, lokalną powierzchnię. Musi
zachować spójny casing i oryginalne offsety, obsłużyć powtórzenia oraz wiele
zdań, a także abstainować dla:

- cytatu metajęzykowego i literalnego przytoczenia;
- kodu, flag CLI, adresów URL i e-mail, ścieżek oraz identyfikatorów;
- dopasowania wewnątrz dłuższego tokenu lub technicznego złożenia;
- mieszanego alfabetu, przerwanej interpunkcją powierzchni i zakresu przez
  granicę zdania;
- nazwy własnej lub produktowej, niejednoznacznego casing i konfliktu z inną
  poprawką.

Brak providera, obecność Morfeusza lub dryf jego wersji nie mogą zmienić
wyniku. Konflikt albo niepełna informacja oznaczają brak sugestii.

## Kolejny etap

Po zamknięciu #402 należy tworzyć dzieci w kolejności rankingu. Każdy
zaakceptowany wiersz otrzymuje osobne issue, krótkotrwałą gałąź, jeden skupiony
commit i osobny PR. Następny wiersz można rozpocząć dopiero po zamknięciu
poprzedniego. `PI-TYPO-01`: `coniemiara` → `co niemiara` jest ukończony przez
#404. Następną dozwoloną implementacją jest więc wyłącznie `PI-TYPO-02`:
`złodzieji` → `złodziei`.

Macierz #368 pozostaje niezmienna i nadal opisuje swój historyczny wynik zero
zaakceptowanych rodzin RJP/v4. #402 jest nową kwalifikacją zamkniętych
powierzchni i nie zmienia tamtej decyzji.

## Weryfikacja

```console
uv run --locked --extra dev python -m scripts.provider_independent_spelling_qualification \\
  validate \\
  --evidence tests/fixtures/v1/provider_independent_spelling_qualification.json \\
  --manifest tests/fixtures/v1/provider_independent_spelling_qualification.manifest.json \\
  --matrix docs/provider-independent-spelling-qualification-v1.json
uv run --locked --extra dev pytest -q -k provider_independent_spelling_qualification
```

Poprawny wynik raportuje 6 zaakceptowanych wierszy, 144 przypadki, 54 expected
findings i 96 hard negatives. Nie jest to deklaracja pełnego wykrywania
błędów pisowni ani całej polszczyzny.
